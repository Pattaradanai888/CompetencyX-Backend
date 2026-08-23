"""The assessment produces results without any reinforcement-learning machinery.

ADR-0003 removed the Q-learning policy: its reward was a function of the chosen
topic alone, so it converged on the topic the deterministic rule already picked,
at the cost of a database write per answer. These tests hold the surface that
removal left behind -- the results payload no longer carries a persisted
per-path recommendation, and no Q-table survives to be written to.
"""

from django.db import connection
from django.urls import reverse
from rest_framework import status

from assessments.models import AssessmentSession

from .base import AssessmentFlowTestCase


class RecommendationRemovalTests(AssessmentFlowTestCase):
    def _complete_role_discovery(self):
        create_response = self.client.post(reverse('assessment-session-list'), {'preferred_role_slug': self.backend_role.slug}, format='json')
        session_id = create_response.json()['id']
        payload = self._answer_remaining_core_questions(session_id, create_response.json(), profile_dimensions=self.qa_profile)
        return session_id, payload

    def test_completed_results_carry_no_persisted_path_recommendations(self):
        session_id, payload = self._complete_role_discovery()

        self.assertEqual(payload['phase'], AssessmentSession.Phase.RECOMMENDATION_READY)
        self.assertIsNone(payload['current_question'])

        results_response = self.client.get(reverse('assessment-session-results', kwargs={'pk': session_id}))
        self.assertEqual(results_response.status_code, status.HTTP_200_OK)
        results = results_response.json()

        self.assertEqual(results['preferred_role']['slug'], self.backend_role.slug)
        self.assertEqual(results['best_fit_role']['slug'], self.qa_role.slug)
        self.assertEqual(results['role_alignment_status'], 'mismatch')
        self.assertNotIn('preferred_path_recommendation', results)
        self.assertNotIn('best_fit_path_recommendation', results)

    def test_history_carries_no_recommendations(self):
        session_id, _payload = self._complete_role_discovery()

        history_response = self.client.get(reverse('assessment-session-history', kwargs={'pk': session_id}))
        self.assertEqual(history_response.status_code, status.HTTP_200_OK)
        self.assertNotIn('recommendations', history_response.json())

    def test_a_full_assessment_leaves_no_q_learning_tables_to_write_to(self):
        session_id, _payload = self._complete_role_discovery()

        self.client.post(
            reverse('assessment-session-skill-assessment', kwargs={'pk': session_id}),
            {
                'completed': True,
                'answers': {'psp-plan-estimate': 4, 'psp-quality-defects': 2},
                'completed_at': '2026-05-08T20:00:00Z',
            },
            format='json',
        )

        with connection.cursor() as cursor:
            table_names = set(connection.introspection.table_names(cursor))

        self.assertNotIn('recommendations_recommendation', table_names)
        self.assertNotIn('recommendations_recommendationqvalue', table_names)
        self.assertNotIn('assessments_skillassessmentquestionqvalue', table_names)
        self.assertNotIn('assessments_skillassessmentfeedbackevent', table_names)
