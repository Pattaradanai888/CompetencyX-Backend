"""The assessment produces results without any reinforcement-learning machinery.

ADR-0003 removed the Q-learning policy: its reward was a function of the chosen
topic alone, so it converged on the topic the deterministic rule already picked,
at the cost of a database write per answer. ADR-0005 then removed the
``recommendations`` app that had housed it. These tests hold the surface those
removals left behind -- the results payload carries neither a persisted
per-path recommendation nor a catalog-derived gap list, and no Q-table survives
to be written to.
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

    def test_results_carry_no_gap_list_read_off_the_catalog(self):
        # "Focus next on X, Y, Z" used to name the first three curated topics
        # regardless of what was answered. A Recommendation is produced from
        # the answers with a reason, and lives on the skill-assessment state.
        session_id, _payload = self._complete_role_discovery()

        results = self.client.get(reverse('assessment-session-results', kwargs={'pk': session_id})).json()

        self.assertNotIn('preferred_role_gap_topics', results)
        self.assertNotIn('Focus next on', results['guidance_summary'])

    def test_history_carries_no_recommendations(self):
        session_id, _payload = self._complete_role_discovery()

        history_response = self.client.get(reverse('assessment-session-history', kwargs={'pk': session_id}))
        self.assertEqual(history_response.status_code, status.HTTP_200_OK)
        self.assertNotIn('recommendations', history_response.json())

    def test_a_full_assessment_leaves_no_q_learning_tables_to_write_to(self):
        self._complete_role_discovery()

        with connection.cursor() as cursor:
            table_names = set(connection.introspection.table_names(cursor))

        self.assertNotIn('recommendations_recommendation', table_names)
        self.assertNotIn('recommendations_recommendationqvalue', table_names)
        self.assertNotIn('assessments_skillassessmentquestionqvalue', table_names)
        self.assertNotIn('assessments_skillassessmentfeedbackevent', table_names)
