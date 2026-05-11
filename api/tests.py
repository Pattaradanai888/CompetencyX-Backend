import json

from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from assessments.models import Answer, AssessmentSession, QuestionBanditStat, QuestionSelectionEvent, TopicMastery
from assessments.role_inference import _get_selectable_role_candidates
from assessments.services import get_current_question
from recommendations.models import Recommendation
from roadmaps.models import Question, QuestionOption, QuestionTopicSignal, RoadmapTopic, Role, TopicPrerequisite
from roadmaps.questionnaire import ROLE_PROFILE_WEIGHTS, SWEBOK_KNOWLEDGE_AREAS


class AssessmentFlowTests(APITestCase):
    backend_profile = set(ROLE_PROFILE_WEIGHTS['backend-developer'])
    qa_profile = set(ROLE_PROFILE_WEIGHTS['qa-engineer'])

    def setUp(self):
        self.backend_role = Role.objects.create(
            slug='backend-developer',
            name='Backend Developer',
            description='Builds APIs and backend services.',
        )
        self.qa_role = Role.objects.create(
            slug='qa-engineer',
            name='QA Engineer',
            description='Improves quality with testing and release validation.',
        )
        self.frontend_role = Role.objects.create(
            slug='frontend-developer',
            name='Frontend Developer',
            description='Builds web user interfaces.',
        )
        self.backend_http = RoadmapTopic.objects.create(role=self.backend_role, slug='http', title='HTTP Fundamentals', display_order=1)
        self.backend_databases = RoadmapTopic.objects.create(role=self.backend_role, slug='databases', title='Databases', display_order=2)
        self.backend_apis = RoadmapTopic.objects.create(role=self.backend_role, slug='apis', title='API Design', display_order=3)
        self.qa_design = RoadmapTopic.objects.create(role=self.qa_role, slug='test-design', title='Test Design', display_order=1)
        self.qa_automation = RoadmapTopic.objects.create(role=self.qa_role, slug='test-automation', title='Test Automation', display_order=2)
        self.qa_release = RoadmapTopic.objects.create(role=self.qa_role, slug='release-quality', title='Release Quality', display_order=3)
        TopicPrerequisite.objects.create(topic=self.backend_databases, prerequisite=self.backend_http, required_mastery_threshold=0.7)
        TopicPrerequisite.objects.create(topic=self.backend_apis, prerequisite=self.backend_databases, required_mastery_threshold=0.7)
        TopicPrerequisite.objects.create(topic=self.qa_automation, prerequisite=self.qa_design, required_mastery_threshold=0.7)
        TopicPrerequisite.objects.create(topic=self.qa_release, prerequisite=self.qa_automation, required_mastery_threshold=0.7)

        self._add_role_questions()
        self._add_skill_question(
            code='backend-http-basics',
            role=self.backend_role,
            topic=self.backend_http,
            prompt='Are you comfortable with HTTP methods and status codes?',
            display_order=11,
        )
        self._add_skill_question(
            code='backend-database-basics',
            role=self.backend_role,
            topic=self.backend_databases,
            prompt='Can you write basic SQL queries and explain joins?',
            display_order=12,
            discrimination_score=2.0,
        )
        self._add_skill_question(
            code='qa-test-design',
            role=self.qa_role,
            topic=self.qa_design,
            prompt='Can you derive useful test cases from requirements?',
            display_order=21,
        )
        self._add_skill_question(
            code='qa-test-automation',
            role=self.qa_role,
            topic=self.qa_automation,
            prompt='Have you written or maintained automated tests?',
            display_order=22,
            discrimination_score=2.0,
        )

    def _add_role_questions(self):
        dimensions = [
            *(dimension for dimension, _label in SWEBOK_KNOWLEDGE_AREAS),
            *(dimension for dimension, _label in SWEBOK_KNOWLEDGE_AREAS),
        ]
        for display_order, dimension in enumerate(dimensions, start=1):
            Question.objects.create(
                code=f'role-core-{display_order:02d}',
                stage=Question.Stage.ROLE,
                item_group=Question.ItemGroup.CORE,
                question_type=Question.Type.LIKERT_5,
                prompt=f'Role trait prompt {display_order}',
                trait_positive_dimension=dimension,
                agree_dimension_signals={dimension: 1.0},
                disagree_dimension_signals={'people_product': 1.0},
                display_order=display_order,
                discrimination_score=3.0,
            )

    def _add_skill_question(self, *, code, role, topic, prompt, display_order, discrimination_score=1.5):  # noqa: PLR0913
        question = Question.objects.create(
            code=code,
            stage=Question.Stage.SKILL,
            question_type=Question.Type.YES_NO_MAYBE,
            prompt=prompt,
            role=role,
            topic=topic,
            display_order=display_order,
            discrimination_score=discrimination_score,
        )
        for option_key, mastery_delta, option_order in (('yes', 1.0, 1), ('maybe', 0.5, 2), ('no', 0.0, 3)):
            option = QuestionOption.objects.create(
                question=question,
                key=option_key,
                label=option_key.capitalize(),
                display_order=option_order,
            )
            QuestionTopicSignal.objects.create(question_option=option, topic=topic, mastery_delta=mastery_delta)
        return question

    def _scale_for_profile(self, question, profile_dimensions):
        agree_dimensions = set(question.agree_dimension_signals or {})
        disagree_dimensions = set(question.disagree_dimension_signals or {})
        if agree_dimensions & profile_dimensions:
            return 2
        if disagree_dimensions & profile_dimensions:
            return -2
        return 0

    def _answer_remaining_core_questions(self, session_id, payload, *, profile_dimensions=None):
        profile_dimensions = profile_dimensions or self.backend_profile
        current_question = payload['current_question']
        while current_question is not None and current_question['stage'] == Question.Stage.ROLE:
            question = Question.objects.get(id=current_question['id'])
            if question.item_group != Question.ItemGroup.CORE:
                break
            response = self.client.post(
                reverse('assessment-answer-submit', kwargs={'pk': session_id}),
                {'question_id': question.id, 'scale_value': self._scale_for_profile(question, profile_dimensions)},
                format='json',
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            payload = response.json()
            current_question = payload['current_question']
        return payload

    def _answer_current_skill_question(self, session_id, payload, option_key='yes'):
        question = Question.objects.get(id=payload['current_question']['id'])
        option_id = question.options.get(key=option_key).id
        response = self.client.post(
            reverse('assessment-answer-submit', kwargs={'pk': session_id}),
            {'question_id': question.id, 'option_id': option_id},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return response.json()

    def test_health_endpoint(self):
        response = self.client.get(reverse('health-check'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {'status': 'ok'})

    def test_openapi_schema_and_swagger_endpoints(self):
        schema_response = self.client.get(reverse('api-schema'), HTTP_ACCEPT='application/json')
        self.assertEqual(schema_response.status_code, status.HTTP_200_OK)
        schema_payload = json.loads(schema_response.content)
        self.assertEqual(schema_payload['info']['title'], 'CompetencyX API')
        self.assertEqual(schema_payload['openapi'], '3.0.3')
        self.assertEqual(schema_payload['paths']['/api/health/']['get']['operationId'], 'healthCheck')
        self.assertEqual(schema_payload['paths']['/api/catalog/roles/']['get']['operationId'], 'listCatalogRoles')
        self.assertEqual(
            schema_payload['paths']['/api/assessment-sessions/{id}/answers/']['post']['operationId'],
            'submitAssessmentAnswer',
        )
        self.assertIn('AssessmentSession', schema_payload['components']['schemas'])

    def test_catalog_roles_and_topics(self):
        roles_response = self.client.get(reverse('role-list'))
        self.assertEqual(roles_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(roles_response.json()), 3)

        topics_response = self.client.get(reverse('role-topic-list', kwargs={'role_slug': self.backend_role.slug}))
        self.assertEqual(topics_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(topics_response.json()), 3)
        self.assertEqual(topics_response.json()[1]['prerequisites'][0]['topic_id'], self.backend_http.id)

    def test_role_likert_question_shape_and_submission_contract(self):
        create_response = self.client.post(reverse('assessment-session-create'), {'profile': {'current_stage': 'beginner'}}, format='json')
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        question_payload = create_response.json()['current_question']
        self.assertEqual(question_payload['question_type'], Question.Type.LIKERT_5)
        self.assertEqual(question_payload['options'], [])
        self.assertEqual([choice['value'] for choice in question_payload['response_scale']], [2, 1, 0, -1, -2])

        option_response = self.client.post(
            reverse('assessment-answer-submit', kwargs={'pk': create_response.json()['id']}),
            {'question_id': question_payload['id'], 'option_id': 999},
            format='json',
        )
        self.assertEqual(option_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('scale_value', option_response.json()['option_id'][0])

        bad_scale_response = self.client.post(
            reverse('assessment-answer-submit', kwargs={'pk': create_response.json()['id']}),
            {'question_id': question_payload['id'], 'scale_value': 3},
            format='json',
        )
        self.assertEqual(bad_scale_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Use one of', bad_scale_response.json()['scale_value'][0])

    def test_skill_questions_still_require_option_id(self):
        create_response = self.client.post(reverse('assessment-session-create'), {}, format='json')
        payload = self._answer_remaining_core_questions(create_response.json()['id'], create_response.json())
        skill_question = payload['current_question']

        scale_response = self.client.post(
            reverse('assessment-answer-submit', kwargs={'pk': payload['id']}),
            {'question_id': skill_question['id'], 'scale_value': 2},
            format='json',
        )

        self.assertEqual(scale_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('option_id', scale_response.json()['scale_value'][0])

    def test_preferred_role_is_preserved_while_best_fit_can_differ(self):
        create_response = self.client.post(
            reverse('assessment-session-create'),
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

        question = Question.objects.get(id=payload['current_question']['id'])
        first_answer = self.client.post(
            reverse('assessment-answer-submit', kwargs={'pk': payload['id']}),
            {'question_id': question.id, 'scale_value': self._scale_for_profile(question, self.qa_profile)},
            format='json',
        )
        self.assertEqual(first_answer.status_code, status.HTTP_200_OK)
        self.assertIsNone(first_answer.json()['best_fit_role'])
        self.assertEqual(first_answer.json()['best_fit_confidence'], 0.0)
        self.assertEqual(first_answer.json()['role_resolution_status'], 'in_progress')
        self.assertEqual(first_answer.json()['role_alignment_status'], 'unknown')

        final_payload = self._answer_remaining_core_questions(payload['id'], first_answer.json(), profile_dimensions=self.qa_profile)
        self.assertEqual(final_payload['phase'], AssessmentSession.Phase.SKILL_ASSESSMENT)
        self.assertEqual(final_payload['best_fit_role']['slug'], self.qa_role.slug)
        self.assertEqual(final_payload['preferred_role']['slug'], self.backend_role.slug)
        self.assertEqual(final_payload['role_alignment_status'], 'mismatch')
        self.assertEqual(final_payload['current_question']['code'], 'backend-http-basics')

    def test_completed_results_return_dual_path_recommendations(self):
        create_response = self.client.post(reverse('assessment-session-create'), {'preferred_role_slug': self.backend_role.slug}, format='json')
        session_id = create_response.json()['id']
        payload = self._answer_remaining_core_questions(session_id, create_response.json(), profile_dimensions=self.qa_profile)
        payload = self._answer_current_skill_question(session_id, payload, option_key='yes')
        payload = self._answer_current_skill_question(session_id, payload, option_key='maybe')

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
        self.assertEqual(TopicMastery.objects.filter(session_id=session_id).count(), 2)
        self.assertEqual(Recommendation.objects.filter(session_id=session_id).count(), 2)

    def test_role_inference_without_preferred_role_does_not_resolve_before_core_traits_complete(self):
        create_response = self.client.post(reverse('assessment-session-create'), {'profile': {'current_stage': 'beginner'}}, format='json')
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        payload = create_response.json()

        for _index in range(4):
            question = Question.objects.get(id=payload['current_question']['id'])
            response = self.client.post(
                reverse('assessment-answer-submit', kwargs={'pk': payload['id']}),
                {'question_id': question.id, 'scale_value': self._scale_for_profile(question, self.backend_profile)},
                format='json',
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            payload = response.json()

        self.assertEqual(payload['milestones']['answered_role_questions'], 4)
        self.assertIsNone(payload['best_fit_role'])
        self.assertEqual(payload['role_resolution_status'], 'in_progress')
        self.assertEqual(payload['phase'], AssessmentSession.Phase.ROLE_DISCOVERY)

    def test_low_confidence_role_session_can_fall_back_to_best_fit_when_questions_are_exhausted(self):
        create_response = self.client.post(reverse('assessment-session-create'), {'profile': {'current_stage': 'beginner'}}, format='json')
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)

        final_payload = self._answer_remaining_core_questions(create_response.json()['id'], create_response.json())
        self.assertEqual(final_payload['phase'], AssessmentSession.Phase.SKILL_ASSESSMENT)
        self.assertEqual(final_payload['status'], AssessmentSession.Status.IN_PROGRESS)
        self.assertEqual(final_payload['role_resolution_status'], 'resolved')
        self.assertEqual(final_payload['best_fit_role']['slug'], self.backend_role.slug)
        self.assertEqual(final_payload['current_question']['code'], 'backend-http-basics')

    def test_role_insights_hide_ranked_candidates_until_core_profile_is_complete(self):
        create_response = self.client.post(reverse('assessment-session-create'), {'profile': {'current_stage': 'beginner'}}, format='json')
        session_id = create_response.json()['id']
        current_question = create_response.json()['current_question']
        answer_response = self.client.post(
            reverse('assessment-answer-submit', kwargs={'pk': session_id}),
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

    def test_answer_submission_rejects_out_of_order_question(self):
        create_response = self.client.post(reverse('assessment-session-create'), {'preferred_role_slug': self.backend_role.slug}, format='json')
        session_id = create_response.json()['id']
        backend_question = Question.objects.get(code='backend-http-basics')
        maybe_option_id = backend_question.options.get(key='maybe').id

        answer_response = self.client.post(
            reverse('assessment-answer-submit', kwargs={'pk': session_id}),
            {'question_id': backend_question.id, 'option_id': maybe_option_id},
            format='json',
        )

        self.assertEqual(answer_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Out-of-order submission', answer_response.json()['question_id'][0])
        self.assertEqual(TopicMastery.objects.filter(session_id=session_id).count(), 0)

    def test_history_returns_answers_and_recommendations_after_completion(self):
        create_response = self.client.post(reverse('assessment-session-create'), {'preferred_role_slug': self.backend_role.slug}, format='json')
        session_id = create_response.json()['id']
        payload = self._answer_remaining_core_questions(session_id, create_response.json())
        payload = self._answer_current_skill_question(session_id, payload, option_key='yes')
        self._answer_current_skill_question(session_id, payload, option_key='maybe')

        history_response = self.client.get(reverse('assessment-session-history', kwargs={'pk': session_id}))
        self.assertEqual(history_response.status_code, status.HTTP_200_OK)
        self.assertEqual(history_response.json()['status'], AssessmentSession.Status.COMPLETED)
        self.assertEqual(len(history_response.json()['answers']), 38)
        self.assertEqual(history_response.json()['answers'][0]['scale_value'], 0)
        self.assertEqual(len(history_response.json()['recommendations']), 1)

    def test_assessment_flow_emits_info_logs_for_survey_and_calculation(self):
        with self.assertLogs('assessments.services', level='INFO') as captured_logs:
            create_response = self.client.post(
                reverse('assessment-session-create'),
                {'preferred_role_slug': self.backend_role.slug, 'profile': {'current_stage': 'beginner'}},
                format='json',
            )
            self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
            session_id = create_response.json()['id']
            current_question = create_response.json()['current_question']
            answer_response = self.client.post(
                reverse('assessment-answer-submit', kwargs={'pk': session_id}),
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
        self.assertIn('assessment.mastery_recomputed', joined_logs)
        self.assertIn('assessment.phase_updated', joined_logs)

    def test_role_selection_event_records_reward_for_core_sequence(self):
        create_response = self.client.post(reverse('assessment-session-create'), {'profile': {'current_stage': 'beginner'}}, format='json')
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        session_id = create_response.json()['id']
        current_question = create_response.json()['current_question']

        selection_event = QuestionSelectionEvent.objects.get(session_id=session_id, chosen_question_id=current_question['id'])
        self.assertEqual(selection_event.policy_mode, QuestionSelectionEvent.PolicyMode.CORE_SEQUENCE)
        self.assertEqual(selection_event.heuristic_question_id, current_question['id'])
        self.assertEqual(selection_event.candidate_question_codes[:2], ['role-core-01', 'role-core-02'])
        self.assertEqual(len(selection_event.candidate_scores), 36)
        self.assertIsNotNone(selection_event.selection_score)
        self.assertIsNone(selection_event.answered_at)

        answer_response = self.client.post(
            reverse('assessment-answer-submit', kwargs={'pk': session_id}),
            {'question_id': current_question['id'], 'scale_value': 2},
            format='json',
        )
        self.assertEqual(answer_response.status_code, status.HTTP_200_OK)

        selection_event.refresh_from_db()
        self.assertIsNotNone(selection_event.answered_at)
        self.assertIsNotNone(selection_event.reward)
        self.assertFalse(QuestionBanditStat.objects.filter(question_id=current_question['id'], stage=Question.Stage.ROLE).exists())

    def test_role_info_gain_prefers_higher_expected_information_question(self):
        session = AssessmentSession.objects.create(profile={})

        selected_question = get_current_question(session)

        self.assertEqual(selected_question.code, 'role-core-01')
        selection_event = QuestionSelectionEvent.objects.get(session=session, chosen_question=selected_question)
        candidate_scores = {candidate['question_code']: candidate['selection_score'] for candidate in selection_event.candidate_scores}
        self.assertGreater(candidate_scores['role-core-01'], candidate_scores['role-core-02'])

    @override_settings(ASSESSMENT_BANDIT_POLICY_MODE='live_bandit')
    def test_live_bandit_keeps_skill_selection_within_eligible_candidates(self):
        create_response = self.client.post(reverse('assessment-session-create'), {}, format='json')
        payload = self._answer_remaining_core_questions(create_response.json()['id'], create_response.json())
        session = AssessmentSession.objects.get(id=payload['id'])

        QuestionBanditStat.objects.create(
            question=Question.objects.get(code='backend-http-basics'),
            stage=Question.Stage.SKILL,
            pulls=5,
            cumulative_reward=4.5,
            mean_reward=0.9,
        )
        QuestionBanditStat.objects.create(
            question=Question.objects.get(code='backend-database-basics'),
            stage=Question.Stage.SKILL,
            pulls=5,
            cumulative_reward=0.5,
            mean_reward=0.1,
        )
        QuestionBanditStat.objects.create(
            question=Question.objects.get(code='qa-test-design'),
            stage=Question.Stage.SKILL,
            pulls=5,
            cumulative_reward=5.0,
            mean_reward=1.0,
        )

        selected_question = get_current_question(session)

        self.assertEqual(selected_question.code, 'backend-http-basics')

    def test_role_question_selection_stops_after_static_core_profile(self):
        session = AssessmentSession.objects.create(profile={})
        for question in Question.objects.filter(stage=Question.Stage.ROLE, item_group=Question.ItemGroup.CORE).order_by('display_order'):
            Answer.objects.create(session=session, question=question, scale_value=self._scale_for_profile(question, self.backend_profile))

        broad_question = Question.objects.create(
            code='role-broad-unit-follow-up',
            stage=Question.Stage.ROLE,
            question_type=Question.Type.LIKERT_5,
            prompt='I enjoy broad follow-up work.',
            trait_positive_dimension='construction',
            agree_dimension_signals={'construction': 1.0},
            disagree_dimension_signals={'management': 1.0},
            display_order=31,
            discrimination_score=4.0,
        )

        candidates = _get_selectable_role_candidates(
            session,
            list(
                Question.objects.filter(stage=Question.Stage.ROLE, is_active=True).exclude(
                    id__in=session.answers.values_list('question_id', flat=True)
                )
            ),
        )
        self.assertIn(broad_question, Question.objects.filter(stage=Question.Stage.ROLE))
        self.assertEqual(candidates, [])
