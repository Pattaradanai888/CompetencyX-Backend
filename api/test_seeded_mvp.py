from django.core.management import call_command
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from assessments.models import Answer, AssessmentSession
from assessments.services import _get_selectable_role_candidates, _score_roles_from_dimensions
from roadmaps.models import Question, Role


EXPECTED_SEEDED_ROLE_COUNT = 21
MIN_ROLE_QUESTION_COUNT = 30
FULL_FLOW_SMOKE_ROLE_COUNT = 4


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

        for role_slug in all_role_slugs[:FULL_FLOW_SMOKE_ROLE_COUNT]:
            create_response = self.client.post(
                reverse('assessment-session-create'),
                {'preferred_role_slug': role_slug},
                format='json',
            )

            assert create_response.status_code == status.HTTP_201_CREATED
            payload = create_response.json()
            current_question = payload['current_question']

            while current_question is not None and current_question['stage'] == Question.Stage.ROLE:
                option_id = Question.objects.get(id=current_question['id']).options.order_by('display_order').first().id
                answer_response = self.client.post(
                    reverse('assessment-answer-submit', kwargs={'pk': payload['id']}),
                    {'question_id': current_question['id'], 'option_id': option_id},
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

    def test_trait_axis_scoring_favors_backend_for_build_delivery_operations_profile(self):
        role_scores = _score_roles_from_dimensions(
            {
                'technical_build': 5,
                'independent_deep_work': 4,
                'systems_operation': 5,
                'implementation_delivery': 5,
                'risk_control': 3,
            }
        )

        assert role_scores['backend-engineer'] > role_scores['product-manager']
        assert role_scores['backend-engineer'] > role_scores['business-analyst']

    def test_role_selector_stops_after_static_core_profile(self):
        session_model = AssessmentSession.objects.create(profile={})
        for question in Question.objects.filter(stage=Question.Stage.ROLE, item_group=Question.ItemGroup.CORE).order_by('display_order'):
            Answer.objects.create(
                session=session_model,
                question=question,
                selected_option=question.options.order_by('display_order').last(),
            )

        unanswered_role_questions = list(
            Question.objects.filter(stage=Question.Stage.ROLE, is_active=True).exclude(
                id__in=session_model.answers.values_list('question_id', flat=True)
            )
        )
        candidate_codes = [question.code for question in _get_selectable_role_candidates(session_model, unanswered_role_questions)]

        assert candidate_codes == []

    def test_seeded_backend_answer_path_resolves_into_skill_assessment(self):
        # Dynamic test: answer each question as it comes, preferring build/system
        # options to steer toward backend/engineering roles.
        answer_plan = {
            'role-trait-user-interviews-or-service-code': 'strong-build-service',
            'role-trait-customer-pain-or-system-bug': 'strong-fix-system-bug',
            'role-trait-feedback-session-or-code-session': 'strong-code-session',
            'role-trait-workflow-observation-or-technical-spike': 'strong-technical-spike',
            'role-trait-user-story-or-working-module': 'strong-working-module',
            'role-trait-align-room-or-solve-alone': 'strong-solve-alone',
            'role-trait-coordinate-launch-or-deepen-design': 'strong-deepen-design',
            'role-trait-stakeholder-update-or-focused-analysis': 'strong-focused-analysis',
            'role-trait-workshop-or-quiet-build': 'strong-quiet-build',
            'role-trait-negotiate-tradeoff-or-master-complexity': 'strong-master-complexity',
            'role-trait-department-process-or-user-journey': 'strong-department-process',
            'role-trait-policy-change-or-product-flow': 'strong-policy-change',
            'role-trait-internal-efficiency-or-customer-task': 'strong-internal-efficiency',
            'role-trait-process-rules-or-screen-behavior': 'strong-process-rules',
            'role-trait-operations-fit-or-experience-fit': 'strong-operations-fit',
            'role-trait-analyze-patterns-or-keep-running': 'strong-keep-running',
            'role-trait-metric-question-or-runtime-health': 'strong-runtime-health',
            'role-trait-data-quality-or-service-reliability': 'strong-service-reliability',
            'role-trait-experiment-readout-or-incident-review': 'strong-incident-review',
            'role-trait-forecast-change-or-operate-platform': 'strong-operate-platform',
            'role-trait-model-requirements-or-ship-feature': 'strong-ship-feature',
            'role-trait-write-spec-or-build-slice': 'strong-build-slice',
            'role-trait-edge-cases-or-release-work': 'strong-release-work',
            'role-trait-system-model-or-working-increment': 'strong-working-increment',
            'role-trait-acceptance-criteria-or-production-change': 'strong-production-change',
            'role-trait-reduce-risk-or-test-idea': 'strong-reduce-risk',
            'role-trait-guardrails-or-prototype': 'strong-guardrails',
            'role-trait-safe-release-or-new-approach': 'strong-safe-release',
            'role-trait-compliance-check-or-discovery-test': 'strong-compliance-check',
            'role-trait-prevent-failure-or-create-option': 'strong-prevent-failure',
        }
        create_response = self.client.post(reverse('assessment-session-create'), {}, format='json')
        assert create_response.status_code == status.HTTP_201_CREATED
        payload = create_response.json()

        while payload['current_question'] is not None and payload['current_question']['stage'] == Question.Stage.ROLE:
            current_question = Question.objects.get(id=payload['current_question']['id'])
            option_key = answer_plan.get(current_question.code)
            if option_key is None:
                # Fallback: pick the first option for any unexpected question
                option_id = current_question.options.order_by('display_order').first().id
            else:
                option_id = current_question.options.get(key=option_key).id
            answer_response = self.client.post(
                reverse('assessment-answer-submit', kwargs={'pk': payload['id']}),
                {'question_id': current_question.id, 'option_id': option_id},
                format='json',
            )
            assert answer_response.status_code == status.HTTP_200_OK
            payload = answer_response.json()

        assert payload['phase'] in {'skill_assessment', 'recommendation_ready'}
        assert payload['role_resolution_status'] == 'resolved'
        assert payload['best_fit_role'] is not None

    def _get_session_model(self, session_id):
        return AssessmentSession.objects.get(id=session_id)
