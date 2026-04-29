import json

from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from assessments.models import Answer, AssessmentSession, QuestionBanditStat, QuestionSelectionEvent, TopicMastery
from assessments.services import _get_selectable_role_candidates, get_current_question
from recommendations.models import Recommendation
from roadmaps.models import (
    Question,
    QuestionOption,
    QuestionRoleSignal,
    QuestionTopicSignal,
    RoadmapTopic,
    Role,
    TopicPrerequisite,
)


class AssessmentFlowTests(APITestCase):
    def _create_skill_question_config(self, **config):
        return {'discrimination_score': 1.5, **config}

    def setUp(self):
        self.backend_role = Role.objects.create(
            slug='backend-engineer',
            name='Backend Engineer',
            description='Builds APIs and backend services.',
        )
        self.qa_role = Role.objects.create(
            slug='qa-test-engineer',
            name='QA / Test Engineer',
            description='Improves quality with testing and release validation.',
        )
        self.frontend_role = Role.objects.create(
            slug='frontend-engineer',
            name='Frontend Engineer',
            description='Builds web user interfaces.',
        )
        self.backend_http = RoadmapTopic.objects.create(role=self.backend_role, slug='http', title='HTTP Fundamentals', display_order=1)
        self.backend_databases = RoadmapTopic.objects.create(
            role=self.backend_role,
            slug='databases',
            title='Databases',
            display_order=2,
        )
        self.backend_apis = RoadmapTopic.objects.create(role=self.backend_role, slug='apis', title='API Design', display_order=3)
        self.qa_design = RoadmapTopic.objects.create(role=self.qa_role, slug='test-design', title='Test Design', display_order=1)
        self.qa_automation = RoadmapTopic.objects.create(
            role=self.qa_role,
            slug='test-automation',
            title='Test Automation',
            display_order=2,
        )
        self.qa_release = RoadmapTopic.objects.create(
            role=self.qa_role,
            slug='release-quality',
            title='Release Quality',
            display_order=3,
        )
        TopicPrerequisite.objects.create(topic=self.backend_databases, prerequisite=self.backend_http, required_mastery_threshold=0.7)
        TopicPrerequisite.objects.create(topic=self.backend_apis, prerequisite=self.backend_databases, required_mastery_threshold=0.7)
        TopicPrerequisite.objects.create(topic=self.qa_automation, prerequisite=self.qa_design, required_mastery_threshold=0.7)
        TopicPrerequisite.objects.create(topic=self.qa_release, prerequisite=self.qa_automation, required_mastery_threshold=0.7)

        role_question_1 = Question.objects.create(
            code='role-primary-interest',
            stage=Question.Stage.ROLE,
            item_group=Question.ItemGroup.CORE,
            question_type=Question.Type.SINGLE_CHOICE,
            prompt='Which work sounds most interesting?',
            display_order=1,
            discrimination_score=3.0,
        )
        self.backend_interest_option = self._add_role_option(
            role_question_1,
            key='backend',
            label='Designing APIs and backend services',
            display_order=1,
            weights={self.backend_role.slug: 4.0},
            dimension_signals={'technical_build': 1},
        )
        self.qa_interest_option = self._add_role_option(
            role_question_1,
            key='qa',
            label='Improving quality with test strategy and automation',
            display_order=2,
            weights={self.qa_role.slug: 4.0},
            dimension_signals={'risk_control': 1},
        )

        role_question_2 = Question.objects.create(
            code='role-working-style',
            stage=Question.Stage.ROLE,
            item_group=Question.ItemGroup.CORE,
            question_type=Question.Type.SINGLE_CHOICE,
            prompt='Which working style sounds most satisfying?',
            display_order=2,
            discrimination_score=2.5,
        )
        self.backend_style_option = self._add_role_option(
            role_question_2,
            key='system-backbone',
            label='Building the system backbone that powers features',
            display_order=1,
            weights={self.backend_role.slug: 3.0, self.frontend_role.slug: 1.0},
            dimension_signals={'systems_operation': 1},
        )
        self.qa_style_option = self._add_role_option(
            role_question_2,
            key='ship-safely',
            label='Making delivery safer with tests and predictable releases',
            display_order=2,
            weights={self.qa_role.slug: 3.0},
            dimension_signals={'risk_control': 1},
        )

        backend_trait_cycle = (
            'technical_build',
            'independent_deep_work',
            'business_process',
            'systems_operation',
            'implementation_delivery',
            'risk_control',
        )
        qa_trait_cycle = (
            'technical_build',
            'independent_deep_work',
            'data_investigation',
            'requirements_modeling',
            'risk_control',
            'systems_operation',
        )
        for order in range(3, 31):
            cycle_index = (order - 3) % len(backend_trait_cycle)
            question = Question.objects.create(
                code=f'role-core-{order:02d}',
                stage=Question.Stage.ROLE,
                item_group=Question.ItemGroup.CORE,
                question_type=Question.Type.SINGLE_CHOICE,
                prompt=f'Core role trait prompt {order}',
                display_order=order,
                discrimination_score=2.0,
            )
            self._add_role_option(
                question,
                key='backend',
                label='Build and operate the technical system',
                display_order=1,
                weights={self.backend_role.slug: 2.0},
                dimension_signals={backend_trait_cycle[cycle_index]: 1},
            )
            self._add_role_option(
                question,
                key='qa',
                label='Check risks and expected behavior',
                display_order=2,
                weights={self.qa_role.slug: 2.0},
                dimension_signals={qa_trait_cycle[cycle_index]: 1},
            )

        self._add_skill_question(
            self._create_skill_question_config(
                code='backend-http-basics',
                role=self.backend_role,
                topic=self.backend_http,
                prompt='Are you comfortable with HTTP methods and status codes?',
                display_order=11,
            )
        )
        self._add_skill_question(
            self._create_skill_question_config(
                code='backend-database-basics',
                role=self.backend_role,
                topic=self.backend_databases,
                prompt='Can you write basic SQL queries and explain joins?',
                display_order=12,
                discrimination_score=2.0,
            )
        )
        self._add_skill_question(
            self._create_skill_question_config(
                code='qa-test-design',
                role=self.qa_role,
                topic=self.qa_design,
                prompt='Can you derive useful test cases from requirements?',
                display_order=21,
            )
        )
        self._add_skill_question(
            self._create_skill_question_config(
                code='qa-test-automation',
                role=self.qa_role,
                topic=self.qa_automation,
                prompt='Have you written or maintained automated tests?',
                display_order=22,
                discrimination_score=2.0,
            )
        )

    def _add_role_option(self, question, *, key, label, display_order, weights, dimension_signals=None):  # noqa: PLR0913
        option = QuestionOption.objects.create(
            question=question,
            key=key,
            label=label,
            display_order=display_order,
            dimension_signals=dimension_signals or {},
        )
        for role_slug, weight in weights.items():
            QuestionRoleSignal.objects.create(
                question_option=option,
                role=Role.objects.get(slug=role_slug),
                weight=weight,
            )
        return option

    def _add_skill_question(self, config):
        question = Question.objects.create(
            code=config['code'],
            stage=Question.Stage.SKILL,
            question_type=Question.Type.YES_NO_MAYBE,
            prompt=config['prompt'],
            role=config['role'],
            topic=config['topic'],
            display_order=config['display_order'],
            discrimination_score=config['discrimination_score'],
        )
        for option_key, mastery_delta, option_order in (('yes', 1.0, 1), ('maybe', 0.5, 2), ('no', 0.0, 3)):
            option = QuestionOption.objects.create(
                question=question,
                key=option_key,
                label=option_key.capitalize(),
                display_order=option_order,
            )
            QuestionTopicSignal.objects.create(question_option=option, topic=config['topic'], mastery_delta=mastery_delta)
        return question

    def _answer_remaining_core_questions(self, session_id, payload, *, option_key='backend'):
        current_question = payload['current_question']
        while current_question is not None and current_question['stage'] == Question.Stage.ROLE:
            question = Question.objects.get(id=current_question['id'])
            if question.item_group != Question.ItemGroup.CORE:
                break
            option = question.options.filter(key=option_key).first()
            if option is None:
                option_order = 2 if option_key == 'qa' else 1
                option = question.options.get(display_order=option_order)
            response = self.client.post(
                reverse('assessment-answer-submit', kwargs={'pk': session_id}),
                {'question_id': question.id, 'option_id': option.id},
                format='json',
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            payload = response.json()
            current_question = payload['current_question']
        return payload

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
        self.assertIn('409', schema_payload['paths']['/api/assessment-sessions/{id}/history/']['get']['responses'])
        self.assertIn('AssessmentSession', schema_payload['components']['schemas'])

        swagger_response = self.client.get(reverse('api-swagger-ui'))
        self.assertEqual(swagger_response.status_code, status.HTTP_200_OK)
        self.assertIn('swagger-ui', swagger_response.content.decode().lower())

    def test_catalog_roles_and_topics(self):
        roles_response = self.client.get(reverse('role-list'))
        self.assertEqual(roles_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(roles_response.json()), 3)

        topics_response = self.client.get(reverse('role-topic-list', kwargs={'role_slug': self.backend_role.slug}))
        self.assertEqual(topics_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(topics_response.json()), 3)
        self.assertEqual(topics_response.json()[1]['prerequisites'][0]['topic_id'], self.backend_http.id)

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
        self.assertNotIn('mastery_scores', payload)
        self.assertNotIn('top_role_candidates', payload)
        self.assertNotIn('discrimination_score', payload['current_question'])

        first_answer = self.client.post(
            reverse('assessment-answer-submit', kwargs={'pk': payload['id']}),
            {'question_id': payload['current_question']['id'], 'option_id': self.qa_interest_option.id},
            format='json',
        )
        self.assertEqual(first_answer.status_code, status.HTTP_200_OK)
        second_question = first_answer.json()['current_question']
        self.assertIsNone(first_answer.json()['best_fit_role'])
        self.assertEqual(first_answer.json()['best_fit_confidence'], 0.0)

        second_answer = self.client.post(
            reverse('assessment-answer-submit', kwargs={'pk': payload['id']}),
            {'question_id': second_question['id'], 'option_id': self.qa_style_option.id},
            format='json',
        )
        self.assertEqual(second_answer.status_code, status.HTTP_200_OK)
        self.assertIsNone(second_answer.json()['best_fit_role'])
        self.assertEqual(second_answer.json()['preferred_role']['slug'], self.backend_role.slug)
        self.assertEqual(second_answer.json()['role_alignment_status'], 'unknown')
        self.assertIn('Complete the role-discovery profile', second_answer.json()['guidance_summary'])
        self.assertEqual(second_answer.json()['role_resolution_status'], 'in_progress')
        self.assertEqual(second_answer.json()['phase'], AssessmentSession.Phase.ROLE_DISCOVERY)
        self.assertEqual(second_answer.json()['current_question']['code'], 'role-core-03')

        final_payload = self._answer_remaining_core_questions(payload['id'], second_answer.json(), option_key='qa')
        self.assertEqual(final_payload['phase'], AssessmentSession.Phase.SKILL_ASSESSMENT)
        self.assertEqual(final_payload['current_question']['code'], 'backend-http-basics')

    def test_completed_results_return_dual_path_recommendations(self):
        create_response = self.client.post(
            reverse('assessment-session-create'),
            {'preferred_role_slug': self.backend_role.slug},
            format='json',
        )
        session_id = create_response.json()['id']

        current_question = create_response.json()['current_question']
        role_answers = [self.qa_interest_option.id, self.qa_style_option.id]
        for option_id in role_answers:
            answer_response = self.client.post(
                reverse('assessment-answer-submit', kwargs={'pk': session_id}),
                {'question_id': current_question['id'], 'option_id': option_id},
                format='json',
            )
            self.assertEqual(answer_response.status_code, status.HTTP_200_OK)
            current_question = answer_response.json()['current_question']

        answer_response = self.client.post(
            reverse('assessment-answer-submit', kwargs={'pk': session_id}),
            {'question_id': current_question['id'], 'option_id': Question.objects.get(id=current_question['id']).options.get(key='qa').id},
            format='json',
        )
        self.assertEqual(answer_response.status_code, status.HTTP_200_OK)
        final_role_payload = self._answer_remaining_core_questions(session_id, answer_response.json(), option_key='qa')
        current_question = final_role_payload['current_question']

        backend_yes = Question.objects.get(code='backend-http-basics').options.get(key='yes').id
        backend_maybe = Question.objects.get(code='backend-database-basics').options.get(key='maybe').id
        for option_id in (backend_yes, backend_maybe):
            answer_response = self.client.post(
                reverse('assessment-answer-submit', kwargs={'pk': session_id}),
                {'question_id': current_question['id'], 'option_id': option_id},
                format='json',
            )
            self.assertEqual(answer_response.status_code, status.HTTP_200_OK)
            current_question = answer_response.json()['current_question']

        final_payload = answer_response.json()
        self.assertEqual(final_payload['phase'], AssessmentSession.Phase.RECOMMENDATION_READY)
        self.assertIsNone(final_payload['current_question'])
        self.assertNotIn('latest_recommendation', final_payload)
        self.assertNotIn('top_role_candidates', final_payload)

        results_response = self.client.get(reverse('assessment-session-results', kwargs={'pk': session_id}))
        self.assertEqual(results_response.status_code, status.HTTP_200_OK)
        results = results_response.json()
        self.assertEqual(results['preferred_role']['slug'], self.backend_role.slug)
        self.assertEqual(results['best_fit_role']['slug'], self.qa_role.slug)
        self.assertEqual(results['role_alignment_status'], 'mismatch')
        self.assertEqual(results['preferred_path_recommendation']['path_kind'], 'preferred')
        self.assertEqual(results['preferred_path_recommendation']['role_slug'], self.backend_role.slug)
        self.assertEqual(results['preferred_path_recommendation']['topic_slug'], 'databases')
        self.assertEqual(results['best_fit_path_recommendation']['path_kind'], 'best_fit')
        self.assertEqual(results['best_fit_path_recommendation']['role_slug'], self.qa_role.slug)
        self.assertEqual(results['best_fit_path_recommendation']['topic_slug'], 'test-design')
        self.assertEqual([topic['slug'] for topic in results['preferred_role_gap_topics']], ['apis', 'databases', 'http'])
        self.assertIn('pillar_profile', results)
        self.assertIn('ranked_roles', results)
        self.assertNotIn('answers', results)
        self.assertEqual(TopicMastery.objects.filter(session_id=session_id).count(), 2)
        self.assertEqual(Recommendation.objects.filter(session_id=session_id).count(), 2)

    def test_role_inference_without_preferred_role_does_not_resolve_before_core_traits_complete(self):
        create_response = self.client.post(reverse('assessment-session-create'), {'profile': {'current_stage': 'beginner'}}, format='json')
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        payload = create_response.json()
        self.assertIsNone(payload['preferred_role'])

        first_answer = self.client.post(
            reverse('assessment-answer-submit', kwargs={'pk': payload['id']}),
            {'question_id': payload['current_question']['id'], 'option_id': self.backend_interest_option.id},
            format='json',
        )
        second_answer = self.client.post(
            reverse('assessment-answer-submit', kwargs={'pk': payload['id']}),
            {'question_id': first_answer.json()['current_question']['id'], 'option_id': self.backend_style_option.id},
            format='json',
        )
        self.assertEqual(second_answer.status_code, status.HTTP_200_OK)
        self.assertIsNone(second_answer.json()['best_fit_role'])
        self.assertEqual(second_answer.json()['best_fit_confidence'], 0.0)
        self.assertEqual(second_answer.json()['role_alignment_status'], 'unknown')
        payload = second_answer.json()
        for _index in range(2):
            current_question = payload['current_question']
            question = Question.objects.get(id=current_question['id'])
            payload = self.client.post(
                reverse('assessment-answer-submit', kwargs={'pk': payload['id']}),
                {'question_id': question.id, 'option_id': question.options.get(key='backend').id},
                format='json',
            ).json()
        self.assertEqual(payload['milestones']['answered_role_questions'], 4)
        self.assertIsNone(payload['best_fit_role'])
        self.assertEqual(payload['role_resolution_status'], 'in_progress')
        self.assertEqual(payload['phase'], AssessmentSession.Phase.ROLE_DISCOVERY)

    def test_role_discovery_keeps_asking_when_confidence_is_low(self):
        role_question_3 = Question.objects.create(
            code='role-ownership-style',
            stage=Question.Stage.ROLE,
            question_type=Question.Type.SINGLE_CHOICE,
            prompt='What kind of ownership feels best?',
            display_order=3,
            discrimination_score=2.4,
        )
        self._add_role_option(
            role_question_3,
            key='full-stack',
            label='Owning both UI and backend delivery',
            display_order=1,
            weights={self.backend_role.slug: 2.0, self.frontend_role.slug: 2.0},
        )
        self._add_role_option(
            role_question_3,
            key='backend-only',
            label='Owning backend systems and data flow',
            display_order=2,
            weights={self.backend_role.slug: 3.0, self.qa_role.slug: 1.0},
        )
        self._add_role_option(
            role_question_3,
            key='frontend-only',
            label='Owning interface details and visual polish',
            display_order=3,
            weights={self.frontend_role.slug: 3.0},
        )

        create_response = self.client.post(reverse('assessment-session-create'), {'profile': {'current_stage': 'beginner'}}, format='json')
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        current_question = create_response.json()['current_question']

        first_answer = self.client.post(
            reverse('assessment-answer-submit', kwargs={'pk': create_response.json()['id']}),
            {'question_id': current_question['id'], 'option_id': self.backend_interest_option.id},
            format='json',
        )
        self.assertEqual(first_answer.status_code, status.HTTP_200_OK)
        current_question = first_answer.json()['current_question']

        second_answer = self.client.post(
            reverse('assessment-answer-submit', kwargs={'pk': create_response.json()['id']}),
            {'question_id': current_question['id'], 'option_id': self.qa_style_option.id},
            format='json',
        )
        self.assertEqual(second_answer.status_code, status.HTTP_200_OK)
        self.assertEqual(second_answer.json()['phase'], AssessmentSession.Phase.ROLE_DISCOVERY)
        self.assertEqual(second_answer.json()['role_resolution_status'], 'in_progress')
        self.assertEqual(second_answer.json()['current_question']['code'], 'role-core-03')

    def test_low_confidence_role_session_can_fall_back_to_best_fit_when_questions_are_exhausted(self):
        create_response = self.client.post(
            reverse('assessment-session-create'),
            {'profile': {'current_stage': 'beginner'}},
            format='json',
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        session_id = create_response.json()['id']

        final_payload = self._answer_remaining_core_questions(session_id, create_response.json(), option_key='backend')
        self.assertEqual(final_payload['phase'], AssessmentSession.Phase.SKILL_ASSESSMENT)
        self.assertEqual(final_payload['status'], AssessmentSession.Status.IN_PROGRESS)
        self.assertEqual(final_payload['role_resolution_status'], 'resolved')
        self.assertEqual(final_payload['best_fit_role']['slug'], self.backend_role.slug)
        self.assertEqual(final_payload['current_question']['code'], 'backend-http-basics')

    def test_results_endpoint_rejects_unresolved_role_ambiguity_sessions(self):
        session = AssessmentSession.objects.create(
            profile={},
            phase=AssessmentSession.Phase.ROLE_AMBIGUITY,
            status=AssessmentSession.Status.IN_PROGRESS,
        )

        response = self.client.get(reverse('assessment-session-results', kwargs={'pk': session.id}))

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_resolved_role_session_still_exposes_ranked_candidates_via_insights(self):
        create_response = self.client.post(
            reverse('assessment-session-create'),
            {'profile': {'current_stage': 'beginner'}},
            format='json',
        )
        session_id = create_response.json()['id']
        payload = self._answer_remaining_core_questions(session_id, create_response.json(), option_key='backend')
        self.assertEqual(payload['role_resolution_status'], 'resolved')
        insights = self.client.get(reverse('assessment-session-insights', kwargs={'pk': session_id}))
        self.assertEqual(insights.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(insights.json()['ranked_roles']), 2)
        self.assertEqual(insights.json()['ranked_roles'][0]['slug'], payload['best_fit_role']['slug'])
        self.assertNotIn('not confident enough', payload['guidance_summary'])

    def test_role_insights_hide_ranked_candidates_until_core_profile_is_complete(self):
        create_response = self.client.post(
            reverse('assessment-session-create'),
            {'profile': {'current_stage': 'beginner'}},
            format='json',
        )
        session_id = create_response.json()['id']
        answer_response = self.client.post(
            reverse('assessment-answer-submit', kwargs={'pk': session_id}),
            {'question_id': create_response.json()['current_question']['id'], 'option_id': self.backend_interest_option.id},
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

    def test_history_endpoint_requires_completion(self):
        create_response = self.client.post(reverse('assessment-session-create'), {'preferred_role_slug': self.backend_role.slug}, format='json')
        response = self.client.get(reverse('assessment-session-history', kwargs={'pk': create_response.json()['id']}))
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_history_returns_answers_and_recommendations_after_completion(self):
        create_response = self.client.post(reverse('assessment-session-create'), {'preferred_role_slug': self.backend_role.slug}, format='json')
        session_id = create_response.json()['id']
        current_question = create_response.json()['current_question']

        for option_id in (self.backend_interest_option.id, self.backend_style_option.id):
            answer_response = self.client.post(
                reverse('assessment-answer-submit', kwargs={'pk': session_id}),
                {'question_id': current_question['id'], 'option_id': option_id},
                format='json',
            )
            current_question = answer_response.json()['current_question']

        role_payload = self._answer_remaining_core_questions(session_id, answer_response.json(), option_key='backend')
        current_question = role_payload['current_question']

        for option_id in (
            Question.objects.get(code='backend-http-basics').options.get(key='yes').id,
            Question.objects.get(code='backend-database-basics').options.get(key='maybe').id,
        ):
            answer_response = self.client.post(
                reverse('assessment-answer-submit', kwargs={'pk': session_id}),
                {'question_id': current_question['id'], 'option_id': option_id},
                format='json',
            )
            current_question = answer_response.json()['current_question']

        history_response = self.client.get(reverse('assessment-session-history', kwargs={'pk': session_id}))
        self.assertEqual(history_response.status_code, status.HTTP_200_OK)
        self.assertEqual(history_response.json()['status'], AssessmentSession.Status.COMPLETED)
        self.assertEqual(len(history_response.json()['answers']), 32)
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

            first_answer = self.client.post(
                reverse('assessment-answer-submit', kwargs={'pk': session_id}),
                {
                    'question_id': current_question['id'],
                    'option_id': self.backend_interest_option.id,
                    'response_time_ms': 4200,
                    'confidence_indicator': 'high',
                },
                format='json',
            )
            self.assertEqual(first_answer.status_code, status.HTTP_200_OK)
            second_question = first_answer.json()['current_question']

            second_answer = self.client.post(
                reverse('assessment-answer-submit', kwargs={'pk': session_id}),
                {
                    'question_id': second_question['id'],
                    'option_id': self.backend_style_option.id,
                    'response_time_ms': 3100,
                    'confidence_indicator': 'medium',
                },
                format='json',
            )
            self.assertEqual(second_answer.status_code, status.HTTP_200_OK)

        joined_logs = '\n'.join(captured_logs.output)
        self.assertIn('assessment.session_created', joined_logs)
        self.assertIn('assessment.answer_submission_received', joined_logs)
        self.assertIn('assessment.answer_recorded', joined_logs)
        self.assertIn('assessment.best_fit_recomputed', joined_logs)
        self.assertIn('assessment.mastery_recomputed', joined_logs)
        self.assertIn('assessment.phase_updated', joined_logs)

    def test_role_selection_event_records_reward_for_core_sequence(self):
        create_response = self.client.post(
            reverse('assessment-session-create'),
            {'profile': {'current_stage': 'beginner'}},
            format='json',
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        session_id = create_response.json()['id']
        current_question = create_response.json()['current_question']

        selection_event = QuestionSelectionEvent.objects.get(session_id=session_id, chosen_question_id=current_question['id'])
        self.assertEqual(selection_event.policy_mode, QuestionSelectionEvent.PolicyMode.INFO_GAIN)
        self.assertEqual(selection_event.heuristic_question_id, current_question['id'])
        self.assertEqual(selection_event.candidate_question_codes[:2], ['role-primary-interest', 'role-working-style'])
        self.assertEqual(len(selection_event.candidate_scores), 30)
        self.assertIsNotNone(selection_event.selection_score)
        self.assertIsNone(selection_event.answered_at)

        answer_response = self.client.post(
            reverse('assessment-answer-submit', kwargs={'pk': session_id}),
            {'question_id': current_question['id'], 'option_id': self.backend_interest_option.id},
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

        self.assertEqual(selected_question.code, 'role-primary-interest')
        selection_event = QuestionSelectionEvent.objects.get(session=session, chosen_question=selected_question)
        candidate_scores = {candidate['question_code']: candidate['selection_score'] for candidate in selection_event.candidate_scores}
        self.assertGreater(candidate_scores['role-primary-interest'], candidate_scores['role-working-style'])

    @override_settings(ASSESSMENT_BANDIT_POLICY_MODE='live_bandit')
    def test_live_bandit_keeps_skill_selection_within_eligible_candidates(self):
        session = AssessmentSession.objects.create(best_fit_role=self.backend_role, preferred_role=self.backend_role, profile={})
        role_question_1 = Question.objects.get(code='role-primary-interest')
        role_question_2 = Question.objects.get(code='role-working-style')
        role_answers = [
            (role_question_1, self.backend_interest_option),
            (role_question_2, self.backend_style_option),
        ]
        for question, option in role_answers:
            response = self.client.post(
                reverse('assessment-answer-submit', kwargs={'pk': session.id}),
                {'question_id': question.id, 'option_id': option.id},
                format='json',
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)
        self._answer_remaining_core_questions(session.id, response.json(), option_key='backend')

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

        selected_question = get_current_question(AssessmentSession.objects.get(id=session.id))

        self.assertEqual(selected_question.code, 'backend-http-basics')

    def test_role_info_gain_updates_next_question_after_new_role_evidence(self):
        session = AssessmentSession.objects.create(profile={})
        first_question = get_current_question(session)
        self.assertEqual(first_question.code, 'role-primary-interest')

        response = self.client.post(
            reverse('assessment-answer-submit', kwargs={'pk': session.id}),
            {'question_id': first_question.id, 'option_id': self.backend_interest_option.id},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        next_question = QuestionSelectionEvent.objects.filter(session=session, answered_at__isnull=True).latest('selected_at').chosen_question
        self.assertEqual(next_question.code, 'role-working-style')

    def test_role_question_selection_stops_after_static_core_profile(self):
        session = AssessmentSession.objects.create(profile={})
        QuestionRoleSignal.objects.filter(question_option__question__item_group=Question.ItemGroup.CORE).delete()
        core_questions = Question.objects.filter(stage=Question.Stage.ROLE, item_group=Question.ItemGroup.CORE).order_by('display_order')
        for index, question in enumerate(core_questions):
            option_order = 1 if index % 2 == 0 else 2
            Answer.objects.create(session=session, question=question, selected_option=question.options.get(display_order=option_order))
        backend_evidence_question = Question.objects.create(
            code='role-unit-backend-evidence',
            stage=Question.Stage.ROLE,
            question_type=Question.Type.SINGLE_CHOICE,
            prompt='Which contribution would you rather make?',
            display_order=1,
            discrimination_score=1.0,
        )
        self._add_role_option(
            backend_evidence_question,
            key='backend',
            label='Backend service behavior',
            display_order=1,
            weights={self.backend_role.slug: 4.0},
        )
        qa_evidence_question = Question.objects.create(
            code='role-unit-qa-evidence',
            stage=Question.Stage.ROLE,
            question_type=Question.Type.SINGLE_CHOICE,
            prompt='Which contribution would you rather make?',
            display_order=2,
            discrimination_score=1.0,
        )
        self._add_role_option(
            qa_evidence_question,
            key='qa',
            label='Quality evidence',
            display_order=1,
            weights={self.qa_role.slug: 4.0},
        )
        tie_break_question = Question.objects.create(
            code='role-backend-vs-system-unit-tie-break',
            stage=Question.Stage.ROLE,
            question_type=Question.Type.SINGLE_CHOICE,
            prompt='Which contribution would you rather make?',
            item_group=Question.ItemGroup.TIE_BREAK,
            discriminates_between=['system-architect', 'system-engineer'],
            display_order=3,
            discrimination_score=4.5,
        )
        self._add_role_option(
            tie_break_question,
            key='backend-service',
            label='Make the backend behavior correct and durable',
            display_order=1,
            weights={self.backend_role.slug: 4.0, self.qa_role.slug: 1.0},
        )
        self._add_role_option(
            tie_break_question,
            key='qa-evidence',
            label='Test the important cases and release risks',
            display_order=2,
            weights={self.qa_role.slug: 4.0, self.backend_role.slug: 1.0},
        )
        broad_question = Question.objects.create(
            code='role-broad-unit-follow-up',
            stage=Question.Stage.ROLE,
            question_type=Question.Type.SINGLE_CHOICE,
            prompt='Which broader work style fits?',
            display_order=4,
            discrimination_score=4.0,
        )
        self._add_role_option(
            broad_question,
            key='frontend',
            label='Improve the interface',
            display_order=1,
            weights={self.frontend_role.slug: 4.0},
        )
        self._add_role_option(
            broad_question,
            key='backend',
            label='Improve the backend',
            display_order=2,
            weights={self.backend_role.slug: 4.0},
        )

        candidates = _get_selectable_role_candidates(
            session,
            list(
                Question.objects.filter(stage=Question.Stage.ROLE, is_active=True).exclude(
                    id__in=session.answers.values_list('question_id', flat=True)
                )
            ),
        )
        self.assertEqual(candidates, [])

    def test_role_question_selection_excludes_followups_after_static_core_profile(self):
        session = AssessmentSession.objects.create(profile={})
        QuestionRoleSignal.objects.filter(question_option__question__item_group=Question.ItemGroup.CORE).delete()
        core_questions = Question.objects.filter(stage=Question.Stage.ROLE, item_group=Question.ItemGroup.CORE).order_by('display_order')
        for index, question in enumerate(core_questions):
            option_order = 1 if index % 2 == 0 else 2
            Answer.objects.create(session=session, question=question, selected_option=question.options.get(display_order=option_order))
        irrelevant_tie_break = Question.objects.create(
            code='role-qa-vs-frontend-unit-tie-break',
            stage=Question.Stage.ROLE,
            question_type=Question.Type.SINGLE_CHOICE,
            prompt='Which contribution would you rather make?',
            item_group=Question.ItemGroup.TIE_BREAK,
            discriminates_between=['not-a-top-role', self.frontend_role.slug],
            display_order=3,
            discrimination_score=4.5,
        )
        self._add_role_option(
            irrelevant_tie_break,
            key='qa',
            label='Validate release quality',
            display_order=1,
            weights={self.qa_role.slug: 4.0},
        )
        self._add_role_option(
            irrelevant_tie_break,
            key='frontend',
            label='Improve the user interface',
            display_order=2,
            weights={self.frontend_role.slug: 4.0},
        )
        broad_question = Question.objects.create(
            code='role-broad-unit-only-candidate',
            stage=Question.Stage.ROLE,
            question_type=Question.Type.SINGLE_CHOICE,
            prompt='Which broader work style fits?',
            display_order=4,
            discrimination_score=4.0,
        )
        self._add_role_option(
            broad_question,
            key='backend',
            label='Improve backend behavior',
            display_order=1,
            weights={self.backend_role.slug: 4.0},
        )
        self._add_role_option(
            broad_question,
            key='frontend',
            label='Improve interface behavior',
            display_order=2,
            weights={self.frontend_role.slug: 4.0},
        )

        candidates = _get_selectable_role_candidates(
            session,
            list(
                Question.objects.filter(stage=Question.Stage.ROLE, is_active=True).exclude(
                    id__in=session.answers.values_list('question_id', flat=True)
                )
            ),
        )

        self.assertEqual(candidates, [])
