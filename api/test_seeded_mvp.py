from django.core.management import call_command
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from assessments.services.scoring_service import score_dimension_overlap
from roadmaps.models import Question, Role
from roadmaps.questionnaire import ROLE_PROFILE_WEIGHTS


def _score_roles_from_dimensions(dimension_scores: dict[str, float]) -> dict[str, float]:
    if not dimension_scores:
        return {}

    role_scores: dict[str, float] = {}
    for role_slug, profile in ROLE_PROFILE_WEIGHTS.items():
        role_scores[role_slug] = score_dimension_overlap(dimension_scores, profile)
    return role_scores


EXPECTED_SEEDED_ROLE_COUNT = 26
MIN_ROLE_QUESTION_COUNT = 46
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
        for role in Role.objects.filter(is_active=True)[:FULL_FLOW_SMOKE_ROLE_COUNT]:
            create_response = self.client.post(
                reverse('assessment-session-list'),
                {'preferred_role_slug': role.slug},
                format='json',
            )
            assert create_response.status_code == status.HTTP_201_CREATED
            payload = create_response.json()
            assert payload['preferred_role']['id'] == role.id

            current_question_payload = payload['current_question']
            while current_question_payload is not None:
                question = Question.objects.get(id=current_question_payload['id'])
                if question.stage == Question.Stage.ROLE:
                    profile = ROLE_PROFILE_WEIGHTS.get(role.slug, {})
                    scale_value = self._ideal_scale_for_profile(question, profile)
                    answer_data = {'question_id': question.id, 'scale_value': scale_value}
                else:
                    yes_option_id = question.options.get(key='yes').id
                    answer_data = {'question_id': question.id, 'option_id': yes_option_id}

                answer_response = self.client.post(
                    reverse('assessment-session-answers', kwargs={'pk': payload['id']}),
                    answer_data,
                    format='json',
                )
                assert answer_response.status_code == status.HTTP_200_OK
                payload = answer_response.json()
                current_question_payload = payload['current_question']

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

    def test_seeded_backend_answer_path_resolves_to_recommendations(self):
        backend_profile = set(ROLE_PROFILE_WEIGHTS['backend-developer'])
        create_response = self.client.post(reverse('assessment-session-list'), {}, format='json')
        assert create_response.status_code == status.HTTP_201_CREATED
        payload = create_response.json()

        while payload['current_question'] is not None and payload['current_question']['stage'] == Question.Stage.ROLE:
            current_question = Question.objects.get(id=payload['current_question']['id'])
            scale_value = self._scale_for_profile(current_question, backend_profile)
            answer_response = self.client.post(
                reverse('assessment-session-answers', kwargs={'pk': payload['id']}),
                {'question_id': current_question.id, 'scale_value': scale_value},
                format='json',
            )
            assert answer_response.status_code == status.HTTP_200_OK
            payload = answer_response.json()

        assert payload['phase'] == 'recommendation_ready'
        assert payload['role_resolution_status'] == 'resolved'
        assert payload['best_fit_role'] is not None

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
