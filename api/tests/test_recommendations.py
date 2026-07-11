from django.test import override_settings
from django.urls import reverse
from rest_framework import status

from assessments.models import AssessmentSession
from recommendations.models import Recommendation, RecommendationQValue

from .base import AssessmentFlowTestCase


class RecommendationTests(AssessmentFlowTestCase):
    def test_completed_results_return_dual_path_recommendations(self):
        create_response = self.client.post(reverse('assessment-session-list'), {'preferred_role_slug': self.backend_role.slug}, format='json')
        session_id = create_response.json()['id']
        payload = self._answer_remaining_core_questions(session_id, create_response.json(), profile_dimensions=self.qa_profile)

        self.assertEqual(payload['phase'], AssessmentSession.Phase.RECOMMENDATION_READY)
        self.assertIsNone(payload['current_question'])

        results_response = self.client.get(reverse('assessment-session-results', kwargs={'pk': session_id}))
        self.assertEqual(results_response.status_code, status.HTTP_200_OK)
        results = results_response.json()
        self.assertEqual(results['preferred_role']['slug'], self.backend_role.slug)
        self.assertEqual(results['best_fit_role']['slug'], self.qa_role.slug)
        self.assertEqual(results['role_alignment_status'], 'mismatch')
        self.assertEqual(results['preferred_path_recommendation']['role_slug'], self.backend_role.slug)
        self.assertEqual(results['best_fit_path_recommendation']['role_slug'], self.qa_role.slug)
        self.assertEqual(Recommendation.objects.filter(session_id=session_id).count(), 2)

    @override_settings(
        ASSESSMENT_RECOMMENDATION_POLICY='q_learning',
        ASSESSMENT_RECOMMENDATION_Q_EPSILON=0.0,
        ASSESSMENT_RECOMMENDATION_Q_ALPHA=0.5,
        ASSESSMENT_RECOMMENDATION_Q_GAMMA=0.6,
    )
    def test_completed_results_can_use_q_learning_recommendations(self):
        create_response = self.client.post(reverse('assessment-session-list'), {'preferred_role_slug': self.backend_role.slug}, format='json')
        session_id = create_response.json()['id']
        self._answer_remaining_core_questions(session_id, create_response.json(), profile_dimensions=self.qa_profile)

        results_response = self.client.get(reverse('assessment-session-results', kwargs={'pk': session_id}))
        self.assertEqual(results_response.status_code, status.HTTP_200_OK)
        results = results_response.json()

        self.assertEqual(results['preferred_path_recommendation']['policy_type'], Recommendation.PolicyType.Q_LEARNING)
        self.assertEqual(results['best_fit_path_recommendation']['policy_type'], Recommendation.PolicyType.Q_LEARNING)
        self.assertEqual(RecommendationQValue.objects.count(), 2)
        self.assertTrue(
            RecommendationQValue.objects.filter(
                role=self.backend_role,
                path_kind=Recommendation.PathKind.PREFERRED,
                topic=self.backend_http,
                update_count=1,
            ).exists(),
        )

    @override_settings(
        ASSESSMENT_RECOMMENDATION_POLICY='q_learning',
        ASSESSMENT_RECOMMENDATION_Q_EPSILON=0.0,
        ASSESSMENT_RECOMMENDATION_Q_ALPHA=0.5,
        ASSESSMENT_RECOMMENDATION_Q_GAMMA=0.6,
    )
    def test_completed_survey2_applies_delayed_feedback_to_q_learning_recommendations(self):
        create_response = self.client.post(reverse('assessment-session-list'), {'preferred_role_slug': self.backend_role.slug}, format='json')
        session_id = create_response.json()['id']
        self._answer_remaining_core_questions(session_id, create_response.json(), profile_dimensions=self.qa_profile)

        results_response = self.client.get(reverse('assessment-session-results', kwargs={'pk': session_id}))
        self.assertEqual(results_response.status_code, status.HTTP_200_OK)

        feedback_payload = {
            'completed': True,
            'answers': {
                'psp-plan-estimate': 4,
                'psp-plan-compare': 4,
                'psp-quality-defects': 4,
                'psp-quality-review': 4,
                'sdlc-req-criteria': 4,
                'sdlc-design-tradeoffs': 4,
                'sdlc-dev-conventions': 4,
                'sdlc-test-strategy': 4,
                'sdlc-release-checklist': 4,
                'sdlc-maintain-debug': 4,
                'sdlc-collab-blockers': 4,
            },
            'completed_at': '2026-05-08T20:00:00Z',
        }

        save_response = self.client.post(
            reverse('assessment-session-survey2', kwargs={'pk': session_id}),
            feedback_payload,
            format='json',
        )
        self.assertEqual(save_response.status_code, status.HTTP_200_OK)

        backend_q_value = RecommendationQValue.objects.get(
            role=self.backend_role,
            path_kind=Recommendation.PathKind.PREFERRED,
            topic=self.backend_http,
        )
        qa_q_value = RecommendationQValue.objects.get(
            role=self.qa_role,
            path_kind=Recommendation.PathKind.BEST_FIT,
            topic=self.qa_design,
        )
        self.assertEqual(backend_q_value.update_count, 2)
        self.assertEqual(qa_q_value.update_count, 2)
        self.assertTrue(backend_q_value.last_reward > 0.0)
        self.assertTrue(qa_q_value.last_reward > 0.0)
        self.assertEqual(
            Recommendation.objects.filter(
                session_id=session_id,
                policy_type=Recommendation.PolicyType.Q_LEARNING,
                feedback_reward_applied=True,
            ).count(),
            2,
        )

        repeat_response = self.client.post(
            reverse('assessment-session-survey2', kwargs={'pk': session_id}),
            feedback_payload,
            format='json',
        )
        self.assertEqual(repeat_response.status_code, status.HTTP_200_OK)
        backend_q_value.refresh_from_db()
        qa_q_value.refresh_from_db()
        self.assertEqual(backend_q_value.update_count, 2)
        self.assertEqual(qa_q_value.update_count, 2)
        self.assertTrue(
            RecommendationQValue.objects.filter(
                role=self.qa_role,
                path_kind=Recommendation.PathKind.BEST_FIT,
                topic=self.qa_design,
                update_count=2,
            ).exists(),
        )
