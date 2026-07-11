from django.core.management import call_command
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from roadmaps.models import Question, RoadmapTopic, Role, TopicPrerequisite
from roadmaps.questionnaire import ROLE_PROFILE_WEIGHTS, SWEBOK_KNOWLEDGE_AREAS


class AssessmentFlowTestCase(APITestCase):
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
        call_command('seed_survey2_catalog')

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
                translations={'th': {'prompt': f'คำถามบทบาท {display_order}'}},
                trait_positive_dimension=dimension,
                agree_dimension_signals={dimension: 1.0},
                disagree_dimension_signals={'people_product': 1.0},
                display_order=display_order,
                discrimination_score=3.0,
            )

    def _scale_for_profile(self, question, profile_dimensions):
        agree_dimensions = set(question.agree_dimension_signals or {})
        disagree_dimensions = set(question.disagree_dimension_signals or {})
        if agree_dimensions & profile_dimensions:
            return 2
        if disagree_dimensions & profile_dimensions:
            return -2
        return 0

    def _answer_remaining_core_questions(self, session_id, payload, *, profile_dimensions=None):
        if profile_dimensions is None:
            profile_dimensions = self.backend_profile
        current_question = payload['current_question']
        while current_question is not None and current_question['stage'] == Question.Stage.ROLE:
            question = Question.objects.get(id=current_question['id'])
            if question.item_group != Question.ItemGroup.CORE:
                break
            response = self.client.post(
                reverse('assessment-session-answers', kwargs={'pk': session_id}),
                {'question_id': question.id, 'scale_value': self._scale_for_profile(question, profile_dimensions)},
                format='json',
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            payload = response.json()
            current_question = payload['current_question']
        return payload
