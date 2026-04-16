import json

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from assessments.models import AssessmentSession, TopicMastery
from recommendations.models import Recommendation
from roadmaps.models import Question, QuestionOption, RoadmapTopic, Role, TopicPrerequisite


class AssessmentFlowTests(APITestCase):
    def setUp(self):
        self.backend_role = Role.objects.create(
            slug='backend-engineer',
            name='Backend Engineer',
            description='Builds APIs and backend services.',
        )
        self.frontend_role = Role.objects.create(
            slug='frontend-engineer',
            name='Frontend Engineer',
            description='Builds web user interfaces.',
        )
        self.http_topic = RoadmapTopic.objects.create(
            role=self.backend_role,
            slug='http',
            title='HTTP Fundamentals',
            display_order=1,
        )
        self.apis_topic = RoadmapTopic.objects.create(
            role=self.backend_role,
            slug='apis',
            title='API Design',
            display_order=2,
        )
        TopicPrerequisite.objects.create(
            topic=self.apis_topic,
            prerequisite=self.http_topic,
            required_mastery_threshold=0.7,
        )

        role_question = Question.objects.create(
            code='role-http-interest',
            stage=Question.Stage.ROLE,
            question_type=Question.Type.SINGLE_CHOICE,
            prompt='Which kind of work sounds more interesting?',
            display_order=1,
            discrimination_score=2.0,
        )
        QuestionOption.objects.create(
            question=role_question,
            key='api',
            label='Designing APIs and integrations',
            display_order=1,
            role_weights={'backend-engineer': 2, 'frontend-engineer': 0},
        )
        QuestionOption.objects.create(
            question=role_question,
            key='ui',
            label='Building polished interfaces',
            display_order=2,
            role_weights={'backend-engineer': 0, 'frontend-engineer': 2},
        )

        skill_question_1 = Question.objects.create(
            code='http-basics',
            stage=Question.Stage.SKILL,
            question_type=Question.Type.YES_NO_MAYBE,
            prompt='Are you comfortable with HTTP methods and status codes?',
            role=self.backend_role,
            topic=self.http_topic,
            display_order=1,
        )
        QuestionOption.objects.create(
            question=skill_question_1,
            key='yes',
            label='Yes',
            display_order=1,
            mastery_value=1.0,
        )
        QuestionOption.objects.create(
            question=skill_question_1,
            key='maybe',
            label='Maybe',
            display_order=2,
            mastery_value=0.5,
        )
        QuestionOption.objects.create(
            question=skill_question_1,
            key='no',
            label='No',
            display_order=3,
            mastery_value=0.0,
        )

        skill_question_2 = Question.objects.create(
            code='api-design',
            stage=Question.Stage.SKILL,
            question_type=Question.Type.YES_NO_MAYBE,
            prompt='Have you built or documented a REST API before?',
            role=self.backend_role,
            topic=self.apis_topic,
            display_order=2,
        )
        QuestionOption.objects.create(
            question=skill_question_2,
            key='yes',
            label='Yes',
            display_order=1,
            mastery_value=1.0,
        )
        QuestionOption.objects.create(
            question=skill_question_2,
            key='maybe',
            label='Maybe',
            display_order=2,
            mastery_value=0.5,
        )
        QuestionOption.objects.create(
            question=skill_question_2,
            key='no',
            label='No',
            display_order=3,
            mastery_value=0.0,
        )

    def test_health_endpoint(self):
        response = self.client.get(reverse('health-check'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {'status': 'ok'})

    def test_openapi_schema_and_swagger_endpoints(self):
        schema_response = self.client.get(
            reverse('api-schema'),
            HTTP_ACCEPT='application/json',
        )
        self.assertEqual(schema_response.status_code, status.HTTP_200_OK)
        schema_payload = json.loads(schema_response.content)
        self.assertEqual(schema_payload['info']['title'], 'CompetencyX API')
        self.assertEqual(schema_payload['openapi'], '3.0.3')

        swagger_response = self.client.get(reverse('api-swagger-ui'))
        self.assertEqual(swagger_response.status_code, status.HTTP_200_OK)
        self.assertIn('swagger-ui', swagger_response.content.decode().lower())

    def test_catalog_roles_and_topics(self):
        roles_response = self.client.get(reverse('role-list'))
        self.assertEqual(roles_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(roles_response.json()), 2)

        topics_response = self.client.get(reverse('role-topic-list', kwargs={'role_slug': self.backend_role.slug}))
        self.assertEqual(topics_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(topics_response.json()), 2)
        self.assertEqual(
            topics_response.json()[1]['prerequisites'][0]['topic_id'],
            self.http_topic.id,
        )

    def test_assessment_session_flow_with_selected_role_generates_mastery_and_recommendation(self):
        create_response = self.client.post(
            reverse('assessment-session-create'),
            {
                'selected_role_slug': self.backend_role.slug,
                'profile': {'education_level': 'student'},
            },
            format='json',
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        session_id = create_response.json()['id']
        self.assertEqual(create_response.json()['phase'], AssessmentSession.Phase.SKILL_ASSESSMENT)
        current_question = create_response.json()['current_question']
        self.assertEqual(current_question['code'], 'http-basics')

        yes_option_id = Question.objects.get(code='http-basics').options.get(key='yes').id
        answer_response = self.client.post(
            reverse('assessment-answer-submit', kwargs={'pk': session_id}),
            {
                'question_id': current_question['id'],
                'option_id': yes_option_id,
                'response_time_ms': 1200,
                'confidence_indicator': 'high',
            },
            format='json',
        )
        self.assertEqual(answer_response.status_code, status.HTTP_200_OK)
        self.assertEqual(answer_response.json()['current_question']['code'], 'api-design')
        self.assertEqual(TopicMastery.objects.filter(session_id=session_id).count(), 1)

        maybe_option_id = Question.objects.get(code='api-design').options.get(key='maybe').id
        final_response = self.client.post(
            reverse('assessment-answer-submit', kwargs={'pk': session_id}),
            {
                'question_id': Question.objects.get(code='api-design').id,
                'option_id': maybe_option_id,
            },
            format='json',
        )
        self.assertEqual(final_response.status_code, status.HTTP_200_OK)
        self.assertEqual(final_response.json()['phase'], AssessmentSession.Phase.RECOMMENDATION_READY)
        self.assertIsNone(final_response.json()['current_question'])
        self.assertEqual(final_response.json()['latest_recommendation']['topic_slug'], 'apis')
        self.assertEqual(Recommendation.objects.filter(session_id=session_id).count(), 1)

    def test_role_inference_flow_without_selected_role(self):
        create_response = self.client.post(
            reverse('assessment-session-create'),
            {'profile': {'current_stage': 'beginner'}},
            format='json',
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        question = create_response.json()['current_question']
        selected_option_id = Question.objects.get(code='role-http-interest').options.get(key='api').id

        answer_response = self.client.post(
            reverse('assessment-answer-submit', kwargs={'pk': create_response.json()['id']}),
            {'question_id': question['id'], 'option_id': selected_option_id},
            format='json',
        )
        self.assertEqual(answer_response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            answer_response.json()['inferred_role']['slug'],
            self.backend_role.slug,
        )
        self.assertGreater(answer_response.json()['role_confidence'], 0.0)

    def test_answer_submission_rejects_out_of_order_question(self):
        create_response = self.client.post(
            reverse('assessment-session-create'),
            {'selected_role_slug': self.backend_role.slug},
            format='json',
        )
        session_id = create_response.json()['id']

        api_design_question = Question.objects.get(code='api-design')
        maybe_option_id = api_design_question.options.get(key='maybe').id
        answer_response = self.client.post(
            reverse('assessment-answer-submit', kwargs={'pk': session_id}),
            {'question_id': api_design_question.id, 'option_id': maybe_option_id},
            format='json',
        )

        self.assertEqual(answer_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Out-of-order submission', answer_response.json()['question_id'][0])
        self.assertEqual(TopicMastery.objects.filter(session_id=session_id).count(), 0)

    def test_next_question_prefers_higher_discrimination_when_topic_uncertainty_matches(self):
        Question.objects.create(
            code='http-scenario-analysis',
            stage=Question.Stage.SKILL,
            question_type=Question.Type.YES_NO_MAYBE,
            prompt='Can you reason through HTTP caching, idempotency, and REST constraints?',
            role=self.backend_role,
            topic=self.http_topic,
            display_order=99,
            discrimination_score=3.5,
        )
        advanced_http_question = Question.objects.get(code='http-scenario-analysis')
        QuestionOption.objects.create(
            question=advanced_http_question,
            key='yes',
            label='Yes',
            display_order=1,
            mastery_value=1.0,
        )
        QuestionOption.objects.create(
            question=advanced_http_question,
            key='maybe',
            label='Maybe',
            display_order=2,
            mastery_value=0.5,
        )
        QuestionOption.objects.create(
            question=advanced_http_question,
            key='no',
            label='No',
            display_order=3,
            mastery_value=0.0,
        )

        create_response = self.client.post(
            reverse('assessment-session-create'),
            {'selected_role_slug': self.backend_role.slug},
            format='json',
        )

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(create_response.json()['current_question']['code'], 'http-scenario-analysis')

    def test_results_and_history_endpoints_return_session_snapshot(self):
        create_response = self.client.post(
            reverse('assessment-session-create'),
            {'selected_role_slug': self.backend_role.slug},
            format='json',
        )
        session_id = create_response.json()['id']

        http_question = create_response.json()['current_question']
        http_yes_option_id = Question.objects.get(code='http-basics').options.get(key='yes').id
        first_answer_response = self.client.post(
            reverse('assessment-answer-submit', kwargs={'pk': session_id}),
            {'question_id': http_question['id'], 'option_id': http_yes_option_id},
            format='json',
        )
        self.assertEqual(first_answer_response.status_code, status.HTTP_200_OK)

        api_question = first_answer_response.json()['current_question']
        api_maybe_option_id = Question.objects.get(code='api-design').options.get(key='maybe').id
        second_answer_response = self.client.post(
            reverse('assessment-answer-submit', kwargs={'pk': session_id}),
            {'question_id': api_question['id'], 'option_id': api_maybe_option_id},
            format='json',
        )
        self.assertEqual(second_answer_response.status_code, status.HTTP_200_OK)

        results_response = self.client.get(
            reverse('assessment-session-results', kwargs={'pk': session_id}),
        )
        self.assertEqual(results_response.status_code, status.HTTP_200_OK)
        self.assertEqual(results_response.json()['milestones']['answered_skill_questions'], 2)
        self.assertEqual(len(results_response.json()['answers']), 2)
        self.assertEqual(len(results_response.json()['recommendations']), 1)
        self.assertEqual(results_response.json()['recommendations'][0]['topic_slug'], 'apis')

        history_response = self.client.get(
            reverse('assessment-session-history', kwargs={'pk': session_id}),
        )
        self.assertEqual(history_response.status_code, status.HTTP_200_OK)
        self.assertEqual(history_response.json()['status'], AssessmentSession.Status.COMPLETED)
        self.assertEqual(
            [answer['question_code'] for answer in history_response.json()['answers']],
            ['http-basics', 'api-design'],
        )
        self.assertEqual(history_response.json()['recommendations'][0]['topic_slug'], 'apis')
