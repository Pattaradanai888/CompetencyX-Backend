from django.urls import reverse
from rest_framework import status

from assessments.models import (
    SkillAssessmentDimension,
    SkillAssessmentQuestion,
    SkillAssessmentQuestionQValue,
    SkillAssessmentRoleGuidance,
)

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
            {'completed': False, 'answers': {}, 'completed_at': None},
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

    def test_completed_skill_assessment_requires_all_catalog_questions(self):
        create_response = self.client.post(reverse('assessment-session-list'), {'preferred_role_slug': self.backend_role.slug}, format='json')
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        session_id = create_response.json()['id']

        save_response = self.client.post(
            reverse('assessment-session-skill-assessment', kwargs={'pk': session_id}),
            {'completed': True, 'answers': {'sdlc-req-criteria': 4}},
            format='json',
        )

        self.assertEqual(save_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('answers', save_response.json())

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

    def test_skill_assessment_state_save_updates_q_value_for_new_answers(self):
        create_response = self.client.post(reverse('assessment-session-list'), {'preferred_role_slug': self.backend_role.slug}, format='json')
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        session_id = create_response.json()['id']

        response = self.client.post(
            reverse('assessment-session-skill-assessment', kwargs={'pk': session_id}),
            {'answers': {'psp-plan-estimate': 5}},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(SkillAssessmentQuestionQValue.objects.filter(question_id='psp-plan-estimate').exists())

    def test_skill_assessment_state_save_applies_feedback_once_after_remove_and_readd(self):
        create_response = self.client.post(reverse('assessment-session-list'), {'preferred_role_slug': self.backend_role.slug}, format='json')
        session_id = create_response.json()['id']
        url = reverse('assessment-session-skill-assessment', kwargs={'pk': session_id})

        self.client.post(url, {'answers': {'psp-plan-estimate': 5}}, format='json')
        q_value = SkillAssessmentQuestionQValue.objects.get(question_id='psp-plan-estimate')
        self.assertEqual(q_value.update_count, 1)

        self.client.post(url, {'answers': {}}, format='json')
        response = self.client.post(url, {'answers': {'psp-plan-estimate': 5}}, format='json')

        q_value.refresh_from_db()
        self.assertEqual(q_value.update_count, 1)
        self.assertNotIn('_skill_assessment_feedback_applied_question_ids', response.json())

        session_response = self.client.get(reverse('assessment-session-detail', kwargs={'pk': session_id}))
        self.assertNotIn('_skill_assessment_feedback_applied_question_ids', session_response.json()['profile'])
