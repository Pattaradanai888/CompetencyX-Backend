from django.urls import reverse
from rest_framework import status

from assessments.models import AssessmentSession
from roadmaps.models import Question

from .base import AssessmentFlowTestCase


class SessionHistoryTests(AssessmentFlowTestCase):
    def test_answer_submission_rejects_out_of_order_question(self):
        create_response = self.client.post(reverse('assessment-session-list'), {'preferred_role_slug': self.backend_role.slug}, format='json')
        session_id = create_response.json()['id']
        current_question_id = create_response.json()['current_question']['id']
        later_question = (
            Question.objects.filter(stage=Question.Stage.ROLE, item_group=Question.ItemGroup.CORE).exclude(id=current_question_id).first()
        )

        answer_response = self.client.post(
            reverse('assessment-session-answers', kwargs={'pk': session_id}),
            {'question_id': later_question.id, 'scale_value': 2},
            format='json',
        )

        self.assertEqual(answer_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Out-of-order submission', answer_response.json()['question_id'][0])

    def test_history_returns_answers_after_completion(self):
        create_response = self.client.post(reverse('assessment-session-list'), {'preferred_role_slug': self.backend_role.slug}, format='json')
        session_id = create_response.json()['id']
        self._answer_remaining_core_questions(session_id, create_response.json())

        history_response = self.client.get(reverse('assessment-session-history', kwargs={'pk': session_id}))
        self.assertEqual(history_response.status_code, status.HTTP_200_OK)
        self.assertEqual(history_response.json()['status'], AssessmentSession.Status.COMPLETED)
        self.assertEqual(len(history_response.json()['answers']), Question.objects.filter(stage=Question.Stage.ROLE).count())
        self.assertEqual(history_response.json()['answers'][0]['scale_value'], 0)

    def test_results_and_history_require_completed_session(self):
        create_response = self.client.post(reverse('assessment-session-list'), {}, format='json')
        session_id = create_response.json()['id']

        results_response = self.client.get(reverse('assessment-session-results', kwargs={'pk': session_id}))
        history_response = self.client.get(reverse('assessment-session-history', kwargs={'pk': session_id}))

        self.assertEqual(results_response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(history_response.status_code, status.HTTP_409_CONFLICT)
        self.assertIn('completion', results_response.json()['detail'])
        self.assertIn('completion', history_response.json()['detail'])

    def test_assessment_flow_emits_info_logs_for_survey_and_calculation(self):
        with self.assertLogs('assessments.services', level='INFO') as captured_logs:
            create_response = self.client.post(
                reverse('assessment-session-list'),
                {'preferred_role_slug': self.backend_role.slug, 'profile': {'current_stage': 'beginner'}},
                format='json',
            )
            self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
            session_id = create_response.json()['id']
            current_question = create_response.json()['current_question']
            answer_response = self.client.post(
                reverse('assessment-session-answers', kwargs={'pk': session_id}),
                {
                    'question_id': current_question['id'],
                    'scale_value': 2,
                    'response_time_ms': 4200,
                    'confidence_indicator': 'high',
                },
                format='json',
            )
            self.assertEqual(answer_response.status_code, status.HTTP_200_OK)

        joined_logs = '\n'.join(captured_logs.output)
        self.assertIn('assessment.session_created', joined_logs)
        self.assertIn('assessment.answer_submission_received', joined_logs)
        self.assertIn('assessment.answer_recorded', joined_logs)
        self.assertIn('assessment.best_fit_recomputed', joined_logs)
        self.assertIn('assessment.phase_updated', joined_logs)
