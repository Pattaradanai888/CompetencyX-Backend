import json
from pathlib import Path

from django.urls import reverse
from rest_framework import status

from assessments.models import AssessmentSession
from roadmaps.models import Question
from roadmaps.seeds import import_external_roadmap_graph

from .base import AssessmentFlowTestCase


class CoreFlowTests(AssessmentFlowTestCase):
    def test_health_endpoint(self):
        response = self.client.get(reverse('health-check'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {'status': 'ok'})

    def test_openapi_schema_and_swagger_endpoints(self):
        schema_response = self.client.get(reverse('api-schema'), HTTP_ACCEPT='application/json')
        self.assertEqual(schema_response.status_code, status.HTTP_200_OK)
        schema_payload = json.loads(schema_response.content)
        self.assertEqual(schema_payload['info']['title'], 'CompetencyX API')
        self.assertEqual(schema_payload['openapi'], '3.0.3')
        self.assertEqual(schema_payload['paths']['/api/v1/health/']['get']['operationId'], 'healthCheck')
        self.assertEqual(schema_payload['paths']['/api/v1/catalog/roles/']['get']['operationId'], 'listCatalogRoles')
        self.assertEqual(
            schema_payload['paths']['/api/v1/assessment-sessions/{id}/answers/']['post']['operationId'],
            'submitAssessmentAnswer',
        )
        self.assertIn('AssessmentSession', schema_payload['components']['schemas'])

    def test_catalog_roles_and_topics(self):
        roles_response = self.client.get(reverse('role-list'))
        self.assertEqual(roles_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(roles_response.json()), 3)

        topics_response = self.client.get(reverse('role-topic-list', kwargs={'slug': self.backend_role.slug}))
        self.assertEqual(topics_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(topics_response.json()), 3)
        self.assertEqual(topics_response.json()[1]['prerequisites'][0]['topic_id'], self.backend_http.id)

    def test_role_roadmap_returns_ordered_topics_and_prerequisite_edges(self):
        response = self.client.get(reverse('role-roadmap', kwargs={'slug': self.backend_role.slug}))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = response.json()
        self.assertEqual(payload['role']['slug'], self.backend_role.slug)
        self.assertEqual(payload['role']['name'], self.backend_role.name)
        self.assertEqual(
            [topic['slug'] for topic in payload['topics']],
            ['http', 'databases', 'apis'],
        )
        self.assertEqual(
            [(edge['prerequisite'], edge['topic']) for edge in payload['prerequisite_edges']],
            [('http', 'databases'), ('databases', 'apis')],
        )
        self.assertEqual(payload['prerequisite_edges'][0]['required_mastery_threshold'], 0.7)

    def test_role_roadmap_excludes_inactive_topics(self):
        self.backend_databases.is_active = False
        self.backend_databases.save(update_fields=['is_active'])

        payload = self.client.get(reverse('role-roadmap', kwargs={'slug': self.backend_role.slug})).json()

        self.assertEqual([topic['slug'] for topic in payload['topics']], ['http', 'apis'])
        # The edge from the now-inactive topic is not walked, but the edge into `apis` survives.
        self.assertEqual([edge['topic'] for edge in payload['prerequisite_edges']], ['apis'])

    def test_role_roadmap_serves_the_imported_external_graph_with_provenance(self):
        import_external_roadmap_graph(
            snapshot_path=Path('data/upstream/roadmap_sh/backend-engineer.sample.json'),
            role=self.backend_role,
            source_url='https://roadmap.sh/backend',
        )

        payload = self.client.get(reverse('role-roadmap', kwargs={'slug': self.backend_role.slug})).json()

        self.assertEqual(len(payload['external_topics']), 3)
        first = payload['external_topics'][0]
        self.assertIn('title', first)
        self.assertIn('prerequisite_titles', first)
        self.assertEqual(payload['external_source']['source'], 'roadmap.sh')
        self.assertEqual(payload['external_source']['source_url'], 'https://roadmap.sh/backend')
        self.assertEqual(payload['external_source']['node_count'], 3)

    def test_role_roadmap_without_a_snapshot_returns_an_empty_external_graph(self):
        # A role with no vendored snapshot must degrade to its curated topics,
        # never fail, and never reach out to a third-party host.
        payload = self.client.get(reverse('role-roadmap', kwargs={'slug': self.qa_role.slug})).json()

        self.assertEqual(payload['external_topics'], [])
        self.assertIsNone(payload['external_source'])
        self.assertTrue(payload['topics'])

    def test_role_roadmap_unknown_slug_returns_404(self):
        response = self.client.get(reverse('role-roadmap', kwargs={'slug': 'no-such-role'}))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_role_roadmap_is_documented_in_the_openapi_schema(self):
        schema_payload = json.loads(self.client.get(reverse('api-schema'), HTTP_ACCEPT='application/json').content)
        operation = schema_payload['paths']['/api/v1/catalog/roles/{slug}/roadmap/']['get']

        self.assertEqual(operation['operationId'], 'retrieveRoleRoadmap')
        self.assertIn('404', operation['responses'])
        self.assertIn('RoleRoadmap', schema_payload['components']['schemas'])

    def test_role_likert_question_shape_and_submission_contract(self):
        create_response = self.client.post(reverse('assessment-session-list'), {'profile': {'current_stage': 'beginner'}}, format='json')
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        question_payload = create_response.json()['current_question']
        self.assertEqual(question_payload['question_type'], Question.Type.LIKERT_5)
        self.assertEqual(question_payload['options'], [])
        self.assertEqual([choice['value'] for choice in question_payload['response_scale']], [2, 1, 0, -1, -2])

        option_response = self.client.post(
            reverse('assessment-session-answers', kwargs={'pk': create_response.json()['id']}),
            {'question_id': question_payload['id'], 'option_id': 999},
            format='json',
        )
        self.assertEqual(option_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('scale_value', option_response.json()['option_id'][0])

        bad_scale_response = self.client.post(
            reverse('assessment-session-answers', kwargs={'pk': create_response.json()['id']}),
            {'question_id': question_payload['id'], 'scale_value': 3},
            format='json',
        )
        self.assertEqual(bad_scale_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Use one of', bad_scale_response.json()['scale_value'][0])

    def test_answer_submission_rejects_response_time_beyond_integer_range(self):
        # ``response_time_ms`` lands in a PostgreSQL integer column, which
        # rejects anything above 2**31 - 1 at insert time. SQLite (the test
        # backend) would store it happily, so the serializer must enforce the
        # bound before the value reaches the database.
        create_response = self.client.post(reverse('assessment-session-list'), {}, format='json')
        question_payload = create_response.json()['current_question']

        oversized_response = self.client.post(
            reverse('assessment-session-answers', kwargs={'pk': create_response.json()['id']}),
            {'question_id': question_payload['id'], 'scale_value': 1, 'response_time_ms': 2**31},
            format='json',
        )

        self.assertEqual(oversized_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('response_time_ms', oversized_response.json())

    def test_session_language_defaults_to_english_and_rejects_unknown_language(self):
        create_response = self.client.post(reverse('assessment-session-list'), {}, format='json')
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(create_response.json()['language'], AssessmentSession.Language.EN)

        invalid_response = self.client.post(reverse('assessment-session-list'), {'language': 'jp'}, format='json')

        self.assertEqual(invalid_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('language', invalid_response.json())

    def test_thai_session_localizes_role_question_ui_without_changing_answer_contract(self):
        create_response = self.client.post(reverse('assessment-session-list'), {'language': AssessmentSession.Language.TH}, format='json')
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        payload = create_response.json()
        self.assertEqual(payload['language'], AssessmentSession.Language.TH)
        self.assertEqual(payload['current_question']['prompt'], 'คำถามบทบาท 1')
        self.assertEqual(
            [choice['label'] for choice in payload['current_question']['response_scale']],
            ['เห็นด้วยอย่างยิ่ง', 'เห็นด้วย', 'เป็นกลาง', 'ไม่เห็นด้วย', 'ไม่เห็นด้วยอย่างยิ่ง'],
        )

        answer_response = self.client.post(
            reverse('assessment-session-answers', kwargs={'pk': payload['id']}),
            {'question_id': payload['current_question']['id'], 'scale_value': 2},
            format='json',
        )

        self.assertEqual(answer_response.status_code, status.HTTP_200_OK)

    def test_role_discovery_finishes_without_serving_skill_questions(self):
        create_response = self.client.post(reverse('assessment-session-list'), {}, format='json')
        payload = self._answer_remaining_core_questions(create_response.json()['id'], create_response.json())

        self.assertEqual(payload['phase'], AssessmentSession.Phase.RECOMMENDATION_READY)
        self.assertEqual(payload['status'], AssessmentSession.Status.COMPLETED)
        self.assertIsNone(payload['current_question'])
