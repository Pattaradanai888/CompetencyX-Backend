from django.urls import reverse
from rest_framework import status

from assessments.models import AssessmentSession
from assessments.services.role_inference_service import get_next_role_question, get_role_inference_snapshot
from assessments.services.scoring_service import ROLE_CANDIDATE_COUNT, ROLE_DISCOVERY_MIN_QUESTIONS, ROLE_DISCOVERY_WARMUP_CODES, build_role_shares
from roadmaps.models import Question

from .base import AssessmentFlowTestCase


class RoleInferenceTests(AssessmentFlowTestCase):
    def test_role_shares_uses_uniform_fallback_for_zero_evidence(self):
        distribution = build_role_shares({'backend-developer': 0.0, 'qa-engineer': 0.0}, ['backend-developer', 'qa-engineer'])

        self.assertEqual(distribution, {'backend-developer': 0.5, 'qa-engineer': 0.5})

    def test_role_shares_concentrate_on_strong_evidence(self):
        distribution = build_role_shares({'backend-developer': 5.0, 'qa-engineer': 0.0}, ['backend-developer', 'qa-engineer'])

        self.assertGreater(distribution['backend-developer'], 0.95)
        self.assertLess(distribution['qa-engineer'], 0.05)

    def test_preferred_role_is_preserved_while_best_fit_can_differ(self):
        create_response = self.client.post(
            reverse('assessment-session-list'),
            {'preferred_role_slug': self.backend_role.slug, 'profile': {'education_level': 'student'}},
            format='json',
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        payload = create_response.json()
        self.assertEqual(payload['phase'], AssessmentSession.Phase.ROLE_DISCOVERY)
        self.assertEqual(payload['preferred_role']['slug'], self.backend_role.slug)
        self.assertIsNone(payload['best_fit_role'])
        self.assertNotIn('mastery_scores', payload)
        self.assertNotIn('top_role_candidates', payload)
        self.assertNotIn('discrimination_score', payload['current_question'])
        self.assertEqual(payload['current_question']['stage'], Question.Stage.ROLE)
        self.assertTrue(payload['current_question']['code'].startswith('role-core-'))

        question = Question.objects.get(id=payload['current_question']['id'])
        first_answer = self.client.post(
            reverse('assessment-session-answers', kwargs={'pk': payload['id']}),
            {'question_id': question.id, 'scale_value': self._scale_for_profile(question, self.qa_profile)},
            format='json',
        )
        self.assertEqual(first_answer.status_code, status.HTTP_200_OK)
        self.assertIsNone(first_answer.json()['best_fit_role'])
        self.assertEqual(first_answer.json()['best_fit_confidence'], 0.0)
        self.assertEqual(first_answer.json()['role_resolution_status'], 'in_progress')
        self.assertEqual(first_answer.json()['role_alignment_status'], 'unknown')

        final_payload = self._answer_remaining_core_questions(payload['id'], first_answer.json(), profile_dimensions=self.qa_profile)
        self.assertEqual(final_payload['phase'], AssessmentSession.Phase.RECOMMENDATION_READY)
        self.assertEqual(final_payload['status'], AssessmentSession.Status.COMPLETED)
        self.assertEqual(final_payload['best_fit_role']['slug'], self.qa_role.slug)
        self.assertEqual(final_payload['preferred_role']['slug'], self.backend_role.slug)
        self.assertEqual(final_payload['role_alignment_status'], 'mismatch')
        self.assertIsNone(final_payload['current_question'])

    def test_current_role_is_saved_separately_from_target_role(self):
        create_response = self.client.post(
            reverse('assessment-session-list'),
            {
                'current_role_slug': self.frontend_role.slug,
                'preferred_role_slug': self.backend_role.slug,
                'profile': {'education_level': 'student'},
            },
            format='json',
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        payload = create_response.json()
        self.assertEqual(payload['preferred_role']['slug'], self.backend_role.slug)
        self.assertEqual(payload['current_role']['slug'], self.frontend_role.slug)
        self.assertEqual(payload['phase'], AssessmentSession.Phase.ROLE_DISCOVERY)
        self.assertEqual(payload['current_question']['stage'], Question.Stage.ROLE)
        self.assertIn('currently a', payload['guidance_summary'].lower())

    def test_role_inference_without_preferred_role_does_not_resolve_before_core_traits_complete(self):
        create_response = self.client.post(reverse('assessment-session-list'), {'profile': {'current_stage': 'beginner'}}, format='json')
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        payload = create_response.json()

        for _index in range(4):
            question = Question.objects.get(id=payload['current_question']['id'])
            response = self.client.post(
                reverse('assessment-session-answers', kwargs={'pk': payload['id']}),
                {'question_id': question.id, 'scale_value': self._scale_for_profile(question, self.backend_profile)},
                format='json',
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            payload = response.json()

        self.assertEqual(payload['milestones']['answered_role_questions'], 4)
        self.assertIsNone(payload['best_fit_role'])
        self.assertEqual(payload['role_resolution_status'], 'in_progress')
        self.assertEqual(payload['phase'], AssessmentSession.Phase.ROLE_DISCOVERY)

    def test_with_three_active_roles_the_survey_ends_at_the_floor(self):
        create_response = self.client.post(reverse('assessment-session-list'), {'profile': {'current_stage': 'beginner'}}, format='json')
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)

        final_payload = self._answer_remaining_core_questions(create_response.json()['id'], create_response.json())
        self.assertEqual(final_payload['phase'], AssessmentSession.Phase.RECOMMENDATION_READY)
        self.assertEqual(final_payload['status'], AssessmentSession.Status.COMPLETED)
        self.assertEqual(final_payload['milestones']['answered_role_questions'], ROLE_DISCOVERY_MIN_QUESTIONS)
        self.assertIn(final_payload['role_resolution_status'], {'resolved', 'low_confidence'})
        self.assertEqual(final_payload['best_fit_role']['slug'], self.backend_role.slug)
        self.assertIsNone(final_payload['current_question'])

    def test_zero_margin_session_completes_as_low_confidence(self):
        create_response = self.client.post(reverse('assessment-session-list'), {'profile': {'current_stage': 'beginner'}}, format='json')
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)

        final_payload = self._answer_remaining_core_questions(create_response.json()['id'], create_response.json(), profile_dimensions=set())
        session = AssessmentSession.objects.get(id=final_payload['id'])
        snapshot = get_role_inference_snapshot(session)

        self.assertEqual(final_payload['phase'], AssessmentSession.Phase.RECOMMENDATION_READY)
        self.assertEqual(final_payload['status'], AssessmentSession.Status.COMPLETED)
        self.assertEqual(final_payload['role_resolution_status'], 'low_confidence')
        self.assertIsNotNone(final_payload['best_fit_role'])
        self.assertEqual(final_payload['best_fit_confidence'], 0.0)
        self.assertEqual(snapshot['score_margin'], 0.0)
        self.assertIsNone(final_payload['current_question'])

    def test_tie_break_items_share_the_pool_and_are_asked_when_they_separate_the_leaders(self):
        tie_break_question = Question.objects.create(
            code='role-tie-backend-frontend',
            stage=Question.Stage.ROLE,
            item_group=Question.ItemGroup.TIE_BREAK,
            question_type=Question.Type.LIKERT_5,
            prompt='I like work where I see the result on screen straight away.',
            agree_dimension_signals={'web_frontend': 1.0},
            disagree_dimension_signals={'server_backend': 1.0},
            discriminates_between=['backend-developer', 'frontend-developer'],
            display_order=101,
            discrimination_score=4.5,
        )
        create_response = self.client.post(reverse('assessment-session-list'), {}, format='json')
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)

        self.assertEqual(create_response.json()['current_question']['id'], tie_break_question.id)

    def test_warm_up_items_are_asked_first_in_their_fixed_order(self):
        for offset, code in enumerate(reversed(ROLE_DISCOVERY_WARMUP_CODES[:2])):
            Question.objects.create(
                code=code,
                stage=Question.Stage.ROLE,
                question_type=Question.Type.LIKERT_5,
                prompt=f'Warm-up {code}',
                agree_dimension_signals={'construction': 1.0},
                disagree_dimension_signals={'management': 1.0},
                display_order=200 + offset,
            )
        create_response = self.client.post(reverse('assessment-session-list'), {}, format='json')
        session_id = create_response.json()['id']
        first = create_response.json()['current_question']
        self.assertEqual(first['code'], ROLE_DISCOVERY_WARMUP_CODES[0])

        answer_response = self.client.post(
            reverse('assessment-session-answers', kwargs={'pk': session_id}),
            {'question_id': first['id'], 'scale_value': 1},
            format='json',
        )
        self.assertEqual(answer_response.json()['current_question']['code'], ROLE_DISCOVERY_WARMUP_CODES[1])

    def test_role_insights_hide_ranked_candidates_until_core_profile_is_complete(self):
        create_response = self.client.post(reverse('assessment-session-list'), {'profile': {'current_stage': 'beginner'}}, format='json')
        session_id = create_response.json()['id']
        current_question = create_response.json()['current_question']
        answer_response = self.client.post(
            reverse('assessment-session-answers', kwargs={'pk': session_id}),
            {'question_id': current_question['id'], 'scale_value': 2},
            format='json',
        )
        self.assertEqual(answer_response.status_code, status.HTTP_200_OK)

        insights = self.client.get(reverse('assessment-session-insights', kwargs={'pk': session_id}))
        self.assertEqual(insights.status_code, status.HTTP_200_OK)
        self.assertIsNone(insights.json()['best_fit_role'])
        self.assertEqual(insights.json()['best_fit_confidence'], 0.0)
        self.assertEqual(insights.json()['role_resolution_status'], 'in_progress')
        self.assertEqual(insights.json()['ranked_roles'], [])
        self.assertEqual(insights.json()['role_candidates'], [])

    def test_completed_session_shows_its_role_candidates(self):
        create_response = self.client.post(reverse('assessment-session-list'), {}, format='json')
        session_id = create_response.json()['id']
        self._answer_remaining_core_questions(session_id, create_response.json(), profile_dimensions=self.qa_profile)

        insights = self.client.get(reverse('assessment-session-insights', kwargs={'pk': session_id})).json()
        self.assertEqual(len(insights['role_candidates']), ROLE_CANDIDATE_COUNT)
        self.assertEqual(insights['role_candidates'], insights['ranked_roles'][:ROLE_CANDIDATE_COUNT])
        self.assertEqual(insights['role_candidates'][0]['slug'], self.qa_role.slug)

    def test_no_role_question_is_served_once_the_survey_is_complete(self):
        create_response = self.client.post(reverse('assessment-session-list'), {}, format='json')
        session_id = create_response.json()['id']
        self._answer_remaining_core_questions(session_id, create_response.json())

        session = AssessmentSession.objects.get(id=session_id)
        self.assertTrue(get_role_inference_snapshot(session)['is_complete'])
        self.assertIsNone(get_next_role_question(session))
        self.assertGreater(Question.objects.filter(stage=Question.Stage.ROLE).exclude(answers__session=session).count(), 0)
