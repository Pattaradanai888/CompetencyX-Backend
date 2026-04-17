import json

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from assessments.models import AssessmentSession, TopicMastery
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
        )
        self.qa_interest_option = self._add_role_option(
            role_question_1,
            key='qa',
            label='Improving quality with test strategy and automation',
            display_order=2,
            weights={self.qa_role.slug: 4.0},
        )

        role_question_2 = Question.objects.create(
            code='role-working-style',
            stage=Question.Stage.ROLE,
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
        )
        self.qa_style_option = self._add_role_option(
            role_question_2,
            key='ship-safely',
            label='Making delivery safer with tests and predictable releases',
            display_order=2,
            weights={self.qa_role.slug: 3.0},
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

    def _add_role_option(self, question, *, key, label, display_order, weights):
        option = QuestionOption.objects.create(question=question, key=key, label=label, display_order=display_order)
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

        first_answer = self.client.post(
            reverse('assessment-answer-submit', kwargs={'pk': payload['id']}),
            {'question_id': payload['current_question']['id'], 'option_id': self.qa_interest_option.id},
            format='json',
        )
        self.assertEqual(first_answer.status_code, status.HTTP_200_OK)
        second_question = first_answer.json()['current_question']
        self.assertEqual(first_answer.json()['best_fit_role']['slug'], self.qa_role.slug)

        second_answer = self.client.post(
            reverse('assessment-answer-submit', kwargs={'pk': payload['id']}),
            {'question_id': second_question['id'], 'option_id': self.qa_style_option.id},
            format='json',
        )
        self.assertEqual(second_answer.status_code, status.HTTP_200_OK)
        self.assertEqual(second_answer.json()['phase'], AssessmentSession.Phase.SKILL_ASSESSMENT)
        self.assertEqual(second_answer.json()['best_fit_role']['slug'], self.qa_role.slug)
        self.assertEqual(second_answer.json()['preferred_role']['slug'], self.backend_role.slug)
        self.assertEqual(second_answer.json()['role_alignment_status'], 'mismatch')
        self.assertIn('but you can still pursue Backend Engineer', second_answer.json()['guidance_summary'])
        self.assertEqual(second_answer.json()['current_question']['code'], 'backend-http-basics')

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
        self.assertNotIn('answers', results)
        self.assertEqual(TopicMastery.objects.filter(session_id=session_id).count(), 2)
        self.assertEqual(Recommendation.objects.filter(session_id=session_id).count(), 2)

    def test_role_inference_without_preferred_role_uses_best_fit_path(self):
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
        self.assertEqual(second_answer.json()['best_fit_role']['slug'], self.backend_role.slug)
        self.assertEqual(second_answer.json()['role_alignment_status'], 'aligned')
        self.assertEqual(second_answer.json()['current_question']['code'], 'backend-http-basics')

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
        self.assertEqual(len(history_response.json()['answers']), 4)
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
