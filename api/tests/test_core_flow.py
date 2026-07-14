import json

from django.urls import reverse
from rest_framework import status

from assessments.models import AssessmentSession
from roadmaps.models import Question

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
