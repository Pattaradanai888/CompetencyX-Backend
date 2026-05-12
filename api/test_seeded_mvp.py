from django.core.management import call_command
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from assessments.models import Answer, AssessmentSession
from assessments.role_inference import _get_selectable_role_candidates, _score_roles_for_answer, _score_roles_from_dimensions
from assessments.services import get_current_question, submit_answer
from roadmaps.models import Question, Role
from roadmaps.questionnaire import ROLE_PROFILE_WEIGHTS


EXPECTED_SEEDED_ROLE_COUNT = 26
MIN_ROLE_QUESTION_COUNT = 36
FULL_FLOW_SMOKE_ROLE_COUNT = 1
IDEAL_SCALE_NEUTRAL_DELTA = 0.2


class SeededMvpFlowTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_mvp_content')

    def test_all_seeded_roles_are_exposed_in_catalog(self):
        response = self.client.get(reverse('role-list'))

        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == EXPECTED_SEEDED_ROLE_COUNT

    def test_seeded_roles_support_session_creation_and_smoke_flows(self):
        role_questions = list(Question.objects.filter(stage=Question.Stage.ROLE).order_by('display_order'))
        assert len(role_questions) >= MIN_ROLE_QUESTION_COUNT

        all_role_slugs = list(Role.objects.order_by('slug').values_list('slug', flat=True))
        for role_slug in all_role_slugs:
            create_response = self.client.post(
                reverse('assessment-session-create'),
                {'preferred_role_slug': role_slug},
                format='json',
            )
            assert create_response.status_code == status.HTTP_201_CREATED
            assert create_response.json()['preferred_role']['slug'] == role_slug

        for role_slug in ['backend-developer']:
            create_response = self.client.post(
                reverse('assessment-session-create'),
                {'preferred_role_slug': role_slug},
                format='json',
            )

            assert create_response.status_code == status.HTTP_201_CREATED
            payload = create_response.json()
            current_question = payload['current_question']

            while current_question is not None and current_question['stage'] == Question.Stage.ROLE:
                current_question_model = Question.objects.get(id=current_question['id'])
                scale_value = self._scale_for_profile(current_question_model, set(ROLE_PROFILE_WEIGHTS[role_slug]))
                answer_response = self.client.post(
                    reverse('assessment-answer-submit', kwargs={'pk': payload['id']}),
                    {'question_id': current_question['id'], 'scale_value': scale_value},
                    format='json',
                )
                assert answer_response.status_code == status.HTTP_200_OK
                payload = answer_response.json()
                current_question = payload['current_question']

            while current_question is not None and current_question['stage'] != Question.Stage.ROLE:
                yes_option_id = Question.objects.get(id=current_question['id']).options.get(key='yes').id
                answer_response = self.client.post(
                    reverse('assessment-answer-submit', kwargs={'pk': payload['id']}),
                    {'question_id': current_question['id'], 'option_id': yes_option_id},
                    format='json',
                )
                assert answer_response.status_code == status.HTTP_200_OK
                payload = answer_response.json()
                current_question = payload['current_question']

            assert payload['phase'] in {'recommendation_ready', 'skill_assessment'}

            while current_question is not None:
                yes_option_id = Question.objects.get(id=current_question['id']).options.get(key='yes').id
                answer_response = self.client.post(
                    reverse('assessment-answer-submit', kwargs={'pk': payload['id']}),
                    {'question_id': current_question['id'], 'option_id': yes_option_id},
                    format='json',
                )
                assert answer_response.status_code == status.HTTP_200_OK
                payload = answer_response.json()
                current_question = payload['current_question']

            assert payload['phase'] == 'recommendation_ready'
            results_response = self.client.get(reverse('assessment-session-results', kwargs={'pk': payload['id']}))
            assert results_response.status_code == status.HTTP_200_OK
            assert results_response.json()['preferred_path_recommendation'] is not None
            assert results_response.json()['preferred_path_recommendation']['topic_slug'] is not None

    def test_swebok_scoring_favors_backend_for_service_operations_profile(self):
        role_scores = _score_roles_from_dimensions(ROLE_PROFILE_WEIGHTS['backend-developer'])

        assert role_scores['backend-developer'] > role_scores['product-manager']
        assert role_scores['backend-developer'] > role_scores['ux-designer']

    def test_role_family_signals_move_fit_between_people_and_backend_roles(self):
        people_scores = _score_roles_from_dimensions({'requirements': 1.0, 'people_product': 2.0})
        backend_scores = _score_roles_from_dimensions({'architecture': 1.0, 'backend_platform': 2.0})

        assert people_scores['product-manager'] > people_scores['backend-developer']
        assert backend_scores['backend-developer'] > backend_scores['product-manager']

    def test_role_likelihood_calibration_recovers_seeded_roles(self):
        role_questions = list(Question.objects.filter(stage=Question.Stage.ROLE).order_by('display_order'))
        misses = {}

        for role_slug, profile in ROLE_PROFILE_WEIGHTS.items():
            role_scores = {}
            for question in role_questions:
                scale_value = self._ideal_scale_for_profile(question, profile)
                for candidate_slug, delta in _score_roles_for_answer(question, scale_value).items():
                    role_scores[candidate_slug] = role_scores.get(candidate_slug, 0.0) + delta

            ranked_slugs = [slug for slug, _score in sorted(role_scores.items(), key=lambda item: (-item[1], item[0]))]
            if ranked_slugs[0] != role_slug:
                misses[role_slug] = ranked_slugs[:3]

        assert misses == {}

    def test_live_role_discovery_paths_can_resolve_every_seeded_role(self):
        misses = self._collect_live_role_resolution_misses()

        miss_summary = ', '.join(
            f"{role_slug}->{details['resolved']} ({details['answered_role_questions']} q, {details['phase']})"
            for role_slug, details in sorted(misses.items())
        )
        assert misses == {}, miss_summary

    def test_live_role_discovery_paths_resolve_fragile_specialized_roles(self):
        misses = self._collect_live_role_resolution_misses(
            role_slugs=['devops-engineer', 'devsecops-engineer', 'server-side-game-developer']
        )

        miss_summary = ', '.join(
            f"{role_slug}->{details['resolved']} ({details['answered_role_questions']} q, {details['phase']})"
            for role_slug, details in sorted(misses.items())
        )
        assert misses == {}, miss_summary

    def test_role_selector_uses_tie_breaks_after_low_margin_core_profile(self):
        session_model = AssessmentSession.objects.create(profile={})
        for question in Question.objects.filter(stage=Question.Stage.ROLE, item_group=Question.ItemGroup.CORE).order_by('display_order'):
            Answer.objects.create(
                session=session_model,
                question=question,
                scale_value=0,
            )

        unanswered_role_questions = list(
            Question.objects.filter(stage=Question.Stage.ROLE, is_active=True).exclude(
                id__in=session_model.answers.values_list('question_id', flat=True)
            )
        )
        candidate_codes = [question.code for question in _get_selectable_role_candidates(session_model, unanswered_role_questions)]

        assert candidate_codes
        assert all(Question.objects.get(code=code).item_group == Question.ItemGroup.TIE_BREAK for code in candidate_codes)

    def test_seeded_backend_answer_path_resolves_into_skill_assessment(self):
        backend_profile = set(ROLE_PROFILE_WEIGHTS['backend-developer'])
        create_response = self.client.post(reverse('assessment-session-create'), {}, format='json')
        assert create_response.status_code == status.HTTP_201_CREATED
        payload = create_response.json()

        while payload['current_question'] is not None and payload['current_question']['stage'] == Question.Stage.ROLE:
            current_question = Question.objects.get(id=payload['current_question']['id'])
            scale_value = self._scale_for_profile(current_question, backend_profile)
            answer_response = self.client.post(
                reverse('assessment-answer-submit', kwargs={'pk': payload['id']}),
                {'question_id': current_question.id, 'scale_value': scale_value},
                format='json',
            )
            assert answer_response.status_code == status.HTTP_200_OK
            payload = answer_response.json()

        assert payload['phase'] in {'skill_assessment', 'recommendation_ready'}
        assert payload['role_resolution_status'] == 'resolved'
        assert payload['best_fit_role'] is not None

    def test_specialized_blockchain_role_requires_blockchain_tie_break_evidence(self):
        blockchain_profile = set(ROLE_PROFILE_WEIGHTS['blockchain-developer'])
        create_response = self.client.post(reverse('assessment-session-create'), {}, format='json')
        assert create_response.status_code == status.HTTP_201_CREATED
        payload = create_response.json()

        while payload['current_question'] is not None and payload['current_question']['stage'] == Question.Stage.ROLE:
            current_question = Question.objects.get(id=payload['current_question']['id'])
            if current_question.item_group == Question.ItemGroup.TIE_BREAK:
                break
            scale_value = self._scale_for_profile(current_question, blockchain_profile)
            answer_response = self.client.post(
                reverse('assessment-answer-submit', kwargs={'pk': payload['id']}),
                {'question_id': current_question.id, 'scale_value': scale_value},
                format='json',
            )
            assert answer_response.status_code == status.HTTP_200_OK
            payload = answer_response.json()

        assert payload['role_resolution_status'] == 'in_progress'
        assert payload['best_fit_role'] is None
        assert payload['best_fit_confidence'] == 0.0
        assert payload['current_question']['code'] == 'role-swebok-tie-08-blockchain-security'

        tie_break_question = Question.objects.get(id=payload['current_question']['id'])
        answer_response = self.client.post(
            reverse('assessment-answer-submit', kwargs={'pk': payload['id']}),
            {'question_id': tie_break_question.id, 'scale_value': 2},
            format='json',
        )
        assert answer_response.status_code == status.HTTP_200_OK
        payload = answer_response.json()

        assert payload['role_resolution_status'] == 'resolved'
        assert payload['best_fit_role']['slug'] == 'blockchain-developer'

    def test_weak_exhausted_role_path_stops_as_ambiguous(self):
        scale_values = [
            1, 2, 1, 2, 1, 0, 1, 0, -1, -2, 0, -1, 1, -1, -2, 1, 0, 2,
            -2, 2, -2, 1, -1, 1, 0, 1, 0, 1, 2, -1, 0, 1, 0, 1, 2, 1,
        ]
        tie_break_answers = {
            'role-swebok-tie-05-data-engineer-mlops': 0,
            'role-swebok-tie-04-ai-engineer-scientist': 1,
            'role-swebok-tie-06-mobile-platform': -1,
            'role-swebok-tie-12-game-client-server': -2,
            'role-swebok-tie-07-database-backend': 1,
            'role-swebok-tie-10-ux-product': -2,
        }
        create_response = self.client.post(reverse('assessment-session-create'), {}, format='json')
        assert create_response.status_code == status.HTTP_201_CREATED
        payload = create_response.json()

        for scale_value in scale_values:
            question = Question.objects.get(id=payload['current_question']['id'])
            assert question.item_group == Question.ItemGroup.CORE
            answer_response = self.client.post(
                reverse('assessment-answer-submit', kwargs={'pk': payload['id']}),
                {'question_id': question.id, 'scale_value': scale_value},
                format='json',
            )
            assert answer_response.status_code == status.HTTP_200_OK
            payload = answer_response.json()

        while payload['current_question'] is not None and payload['current_question']['stage'] == Question.Stage.ROLE:
            question = Question.objects.get(id=payload['current_question']['id'])
            scale_value = tie_break_answers.get(question.code, 0)
            answer_response = self.client.post(
                reverse('assessment-answer-submit', kwargs={'pk': payload['id']}),
                {'question_id': question.id, 'scale_value': scale_value},
                format='json',
            )
            assert answer_response.status_code == status.HTTP_200_OK
            payload = answer_response.json()

        assert payload['phase'] == AssessmentSession.Phase.ROLE_AMBIGUITY
        assert payload['role_resolution_status'] == 'ambiguous'
        assert payload['current_question'] is None
        assert payload['best_fit_role'] is None
        assert payload['best_fit_confidence'] == 0.0

    def _get_session_model(self, session_id):
        return AssessmentSession.objects.get(id=session_id)

    def _collect_live_role_resolution_misses(self, role_slugs=None):
        misses = {}
        selected_role_slugs = role_slugs or list(ROLE_PROFILE_WEIGHTS.keys())

        for role_slug in selected_role_slugs:
            profile = ROLE_PROFILE_WEIGHTS[role_slug]
            session = AssessmentSession.objects.create(profile={})
            trace = []

            while True:
                question = get_current_question(session)
                if question is None or question.stage != Question.Stage.ROLE:
                    break
                scale_value = self._ideal_scale_for_profile(question, profile)
                trace.append((question.code, question.item_group, scale_value))
                submit_answer(session=session, question=question, scale_value=scale_value)
                session.refresh_from_db()

            if session.best_fit_role is None or session.best_fit_role.slug != role_slug:
                misses[role_slug] = {
                    'resolved': session.best_fit_role.slug if session.best_fit_role else None,
                    'phase': session.phase,
                    'status': session.status,
                    'answered_role_questions': session.answers.filter(question__stage=Question.Stage.ROLE).count(),
                    'trace_tail': trace[-8:],
                }

        return misses

    def _scale_for_profile(self, question, profile_dimensions):
        agree_dimensions = set(question.agree_dimension_signals or {})
        disagree_dimensions = set(question.disagree_dimension_signals or {})
        if agree_dimensions & profile_dimensions:
            return 2
        if disagree_dimensions & profile_dimensions:
            return -2
        return 0

    def _ideal_scale_for_profile(self, question, profile):
        agree_score = sum(
            float(weight) * float(profile.get(dimension, 0.0)) for dimension, weight in (question.agree_dimension_signals or {}).items()
        )
        disagree_score = sum(
            float(weight) * float(profile.get(dimension, 0.0)) for dimension, weight in (question.disagree_dimension_signals or {}).items()
        )
        if abs(agree_score - disagree_score) < IDEAL_SCALE_NEUTRAL_DELTA:
            return 0
        return 2 if agree_score > disagree_score else -2
