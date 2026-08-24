from django.urls import reverse
from rest_framework import status

from assessments.models import (
    AssessableTopicSet,
    SkillAssessmentDimension,
    SkillAssessmentQuestion,
    SkillAssessmentRoleGuidance,
)
from assessments.services.topic_skill_assessment_service import sync_topic_skill_assessment_catalog
from roadmaps.models import ExternalRoadmapNode

from .base import AssessmentFlowTestCase


class SkillAssessmentTests(AssessmentFlowTestCase):
    def test_skill_assessment_state_can_be_saved_and_loaded_per_session(self):
        create_response = self.client.post(reverse('assessment-session-list'), {'preferred_role_slug': self.backend_role.slug}, format='json')
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        session_id = create_response.json()['id']

        initial_state_response = self.client.get(reverse('assessment-session-skill-assessment', kwargs={'pk': session_id}))
        self.assertEqual(initial_state_response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            initial_state_response.json(),
            {
                'completed': False,
                'answers': {},
                'completed_at': None,
                'topic_mastery': {},
                'topic_states': [],
                'recommended_topics': [],
                'next_topics': [],
                'readiness': {'targets': {}, 'overall_target': 0.0, 'overall_mastery': 0.0, 'assessed_count': 0},
                'progress': {'answered': 0, 'total': 11, 'remaining': 11, 'floor': 11, 'ceiling': 11, 'settled': False},
                'confidence': None,
            },
        )
        payload = {
            'completed': True,
            'answers': {
                'psp-plan-estimate': 4,
                'psp-plan-compare': 4,
                'psp-quality-defects': 3,
                'psp-quality-review': 4,
                'sdlc-req-criteria': 4,
                'sdlc-design-tradeoffs': 5,
                'sdlc-dev-conventions': 4,
                'sdlc-test-strategy': 3,
                'sdlc-release-checklist': 3,
                'sdlc-maintain-debug': 4,
                'sdlc-collab-blockers': 4,
            },
            'completed_at': '2000-01-01T00:00:00Z',
        }
        save_response = self.client.post(reverse('assessment-session-skill-assessment', kwargs={'pk': session_id}), payload, format='json')
        self.assertEqual(save_response.status_code, status.HTTP_200_OK)
        self.assertEqual(save_response.json()['completed'], True)
        self.assertNotEqual(save_response.json()['completed_at'], payload['completed_at'])
        self.assertEqual(save_response.json()['answers']['sdlc-design-tradeoffs'], 5)

        loaded_response = self.client.get(reverse('assessment-session-skill-assessment', kwargs={'pk': session_id}))
        self.assertEqual(loaded_response.status_code, status.HTTP_200_OK)
        self.assertEqual(loaded_response.json()['completed'], True)
        self.assertEqual(loaded_response.json()['answers'], payload['answers'])
        self.assertIsNotNone(loaded_response.json()['completed_at'])

        reopened_response = self.client.post(
            reverse('assessment-session-skill-assessment', kwargs={'pk': session_id}),
            {'completed': False, 'answers': payload['answers'], 'completed_at': '2000-01-01T00:00:00Z'},
            format='json',
        )
        self.assertEqual(reopened_response.status_code, status.HTTP_200_OK)
        self.assertIsNone(reopened_response.json()['completed_at'])

    def test_skill_assessment_state_rejects_invalid_answer_scale(self):
        create_response = self.client.post(reverse('assessment-session-list'), {'preferred_role_slug': self.backend_role.slug}, format='json')
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        session_id = create_response.json()['id']

        save_response = self.client.post(
            reverse('assessment-session-skill-assessment', kwargs={'pk': session_id}),
            {'answers': {'sdlc-req-criteria': 7}},
            format='json',
        )
        self.assertEqual(save_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('answers', save_response.json())

    def test_skill_assessment_catalog_returns_role_aware_psp_sdlc_questions(self):
        create_response = self.client.post(reverse('assessment-session-list'), {'preferred_role_slug': self.backend_role.slug}, format='json')
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        session_id = create_response.json()['id']

        response = self.client.get(reverse('assessment-session-skill-assessment-catalog', kwargs={'pk': session_id}))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = response.json()
        self.assertEqual(payload['version'], '2026-05-11.psp-sdlc-v1')
        self.assertEqual(len(payload['questions']), 11)
        self.assertIn('psp-quality', {dimension['key'] for dimension in payload['dimensions']})
        self.assertIn('sdlc-maintenance', {dimension['key'] for dimension in payload['dimensions']})
        self.assertTrue(any('API contracts' in guidance for guidance in payload['role_guidance']))

    def test_skill_assessment_catalog_questions_are_loaded_from_database(self):
        create_response = self.client.post(reverse('assessment-session-list'), {'preferred_role_slug': self.backend_role.slug}, format='json')
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        session_id = create_response.json()['id']

        skill_assessment_question = SkillAssessmentQuestion.objects.get(question_id='psp-plan-estimate')
        skill_assessment_question.prompt = 'Database-backed Skill Assessment prompt'
        skill_assessment_question.save(update_fields=['prompt', 'updated_at'])

        response = self.client.get(reverse('assessment-session-skill-assessment-catalog', kwargs={'pk': session_id}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = response.json()
        self.assertEqual(payload['questions'][0]['id'], 'psp-plan-estimate')
        self.assertEqual(payload['questions'][0]['prompt'], 'Database-backed Skill Assessment prompt')

    def test_skill_assessment_catalog_dimensions_and_role_guidance_are_loaded_from_database(self):
        create_response = self.client.post(reverse('assessment-session-list'), {'preferred_role_slug': self.backend_role.slug}, format='json')
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        session_id = create_response.json()['id']

        dimension = SkillAssessmentDimension.objects.get(dimension_key='psp-planning')
        dimension.label = 'Database-backed PSP Planning'
        dimension.low_score_action = 'Database-backed planning action'
        dimension.save(update_fields=['label', 'low_score_action', 'updated_at'])

        guidance = SkillAssessmentRoleGuidance.objects.filter(role=self.backend_role, display_order=1).first()
        guidance.guidance = 'Database-backed backend guidance'
        guidance.save(update_fields=['guidance', 'updated_at'])

        response = self.client.get(reverse('assessment-session-skill-assessment-catalog', kwargs={'pk': session_id}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = response.json()
        self.assertEqual(payload['dimensions'][0]['key'], 'psp-planning')
        self.assertEqual(payload['dimensions'][0]['label'], 'Database-backed PSP Planning')
        self.assertEqual(payload['dimensions'][0]['low_score_action'], 'Database-backed planning action')
        self.assertEqual(payload['role_guidance'][0], 'Database-backed backend guidance')

    def test_completed_skill_assessment_refuses_to_stop_before_the_floor(self):
        # The stop rule owns completion: for the eleven-item role-independent
        # catalog the floor is eleven, so one answer cannot complete the
        # assessment even though every remaining key is known.
        create_response = self.client.post(reverse('assessment-session-list'), {'preferred_role_slug': self.backend_role.slug}, format='json')
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        session_id = create_response.json()['id']

        save_response = self.client.post(
            reverse('assessment-session-skill-assessment', kwargs={'pk': session_id}),
            {'completed': True, 'answers': {'sdlc-req-criteria': 4}},
            format='json',
        )

        self.assertEqual(save_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('completed', save_response.json())

    def test_skill_assessment_next_question_returns_unanswered_question(self):
        create_response = self.client.post(reverse('assessment-session-list'), {'preferred_role_slug': self.backend_role.slug}, format='json')
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        session_id = create_response.json()['id']

        response = self.client.post(
            reverse('assessment-session-skill-assessment-next-question', kwargs={'pk': session_id}),
            {'answers': {'psp-plan-estimate': 4}},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = response.json()
        self.assertIn('next_question', payload)
        self.assertIsNotNone(payload['next_question'])
        self.assertNotEqual(payload['next_question']['id'], 'psp-plan-estimate')

    def test_next_question_selection_is_deterministic_and_follows_catalog_order(self):
        # Selection used to be epsilon-greedy over a learned Q-table whose
        # reward was agreement, so it learned to ask the items a respondent
        # already agrees with. ADR-0003 replaced it: the same answers produce
        # the same next question, in the catalog's own order, skipping
        # answered items and never repeating one.
        create_response = self.client.post(reverse('assessment-session-list'), {'preferred_role_slug': self.backend_role.slug}, format='json')
        session_id = create_response.json()['id']
        next_url = reverse('assessment-session-skill-assessment-next-question', kwargs={'pk': session_id})

        first = self.client.post(next_url, {'answers': {}}, format='json').json()
        second = self.client.post(next_url, {'answers': {}}, format='json').json()
        self.assertEqual(first['next_question'], second['next_question'])
        self.assertEqual(first['next_question']['id'], 'psp-plan-estimate')

        skip_answered = self.client.post(next_url, {'answers': {'psp-plan-estimate': 4}}, format='json').json()
        self.assertEqual(skip_answered['next_question']['id'], 'psp-plan-compare')

    def test_next_question_is_null_when_every_item_is_answered(self):
        create_response = self.client.post(reverse('assessment-session-list'), {'preferred_role_slug': self.backend_role.slug}, format='json')
        session_id = create_response.json()['id']
        next_url = reverse('assessment-session-skill-assessment-next-question', kwargs={'pk': session_id})

        everything = dict.fromkeys(SkillAssessmentQuestion.objects.filter(is_active=True, role__isnull=True).values_list('question_id', flat=True), 3)
        response = self.client.post(next_url, {'answers': everything}, format='json').json()

        self.assertIsNone(response['next_question'])
        self.assertEqual(response['progress']['remaining'], 0)

    def test_skill_assessment_state_survives_removing_and_readding_an_answer(self):
        create_response = self.client.post(reverse('assessment-session-list'), {'preferred_role_slug': self.backend_role.slug}, format='json')
        session_id = create_response.json()['id']
        url = reverse('assessment-session-skill-assessment', kwargs={'pk': session_id})

        self.client.post(url, {'answers': {'psp-plan-estimate': 5}}, format='json')
        cleared_response = self.client.post(url, {'answers': {}}, format='json')
        self.assertEqual(cleared_response.json()['answers'], {})

        response = self.client.post(url, {'answers': {'psp-plan-estimate': 5}}, format='json')
        self.assertEqual(response.json()['answers'], {'psp-plan-estimate': 5})

        # No per-answer learning bookkeeping leaks into the session (ADR-0003).
        self.assertNotIn('_skill_assessment_feedback_applied_question_ids', response.json())
        session_response = self.client.get(reverse('assessment-session-detail', kwargs={'pk': session_id}))
        self.assertNotIn('_skill_assessment_feedback_applied_question_ids', session_response.json()['profile'])


class SkillAssessmentCatalogFromTopicSetsTests(AssessmentFlowTestCase):
    """The catalog endpoint serves a role's authored Assessable Topic Sets.

    The fallback matters as much as the sets: a role with no imported roadmap
    must still be asked something, or the assessment comes back empty
    (ADR-0003).
    """

    def _session_for(self, role):
        response = self.client.post(reverse('assessment-session-list'), {'preferred_role_slug': role.slug}, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        return response.json()['id']

    def _catalog_for(self, role):
        response = self.client.get(reverse('assessment-session-skill-assessment-catalog', kwargs={'pk': self._session_for(role)}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return response.json()

    def test_catalog_serves_the_authored_sets_for_a_role_that_has_them(self):
        node = ExternalRoadmapNode.objects.create(
            role=self.backend_role,
            external_id='b1',
            slug='http',
            title='HTTP',
            node_type=ExternalRoadmapNode.NodeType.TOPIC,
            display_order=1,
        )
        topic_set = AssessableTopicSet.objects.create(
            set_key='backend-developer--internet-and-web-protocols',
            key='internet-and-web-protocols',
            role=self.backend_role,
            title='Internet and web protocols',
            title_th='อินเทอร์เน็ตและโปรโตคอลเว็บ',
            node_slugs=['http'],
            display_order=1,
        )
        topic_set.nodes.set([node])
        sync_topic_skill_assessment_catalog()

        payload = self._catalog_for(self.backend_role)

        self.assertEqual([question['id'] for question in payload['questions']], ['backend-developer--internet-and-web-protocols'])
        self.assertEqual(payload['questions'][0]['topic_title'], 'Internet and web protocols')
        self.assertIn('Internet and web protocols', payload['questions'][0]['prompt'])
        self.assertEqual([dimension['label'] for dimension in payload['dimensions']], ['Internet and web protocols'])

    def test_catalog_falls_back_to_the_role_independent_items_without_a_roadmap(self):
        sync_topic_skill_assessment_catalog()

        payload = self._catalog_for(self.qa_role)

        self.assertEqual(len(payload['questions']), 11)
        self.assertEqual(payload['questions'][0]['id'], 'psp-plan-estimate')
        self.assertEqual({question['topic_title'] for question in payload['questions']}, {''})
