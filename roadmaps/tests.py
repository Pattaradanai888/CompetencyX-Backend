from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from roadmaps.models import Question, QuestionOption, RoadmapTopic, Role, TopicPrerequisite


class SeedMvpContentTests(TestCase):
    def test_seed_command_creates_catalog_and_is_idempotent(self):
        out = StringIO()

        call_command('seed_mvp_content', stdout=out)

        assert Role.objects.count() == 8
        assert RoadmapTopic.objects.count() == 7
        assert TopicPrerequisite.objects.count() == 5
        assert Question.objects.count() == 9
        assert QuestionOption.objects.count() == 27
        assert Role.objects.filter(slug='backend-engineer', is_active=True).exists()
        assert Question.objects.filter(code='backend-api-design', topic__slug='apis').exists()

        first_run_output = out.getvalue()
        assert 'Seeded 8 roles, 7 topics, 9 questions, and 27 options.' in first_run_output

        call_command('seed_mvp_content')

        assert Role.objects.count() == 8
        assert RoadmapTopic.objects.count() == 7
        assert TopicPrerequisite.objects.count() == 5
        assert Question.objects.count() == 9
        assert QuestionOption.objects.count() == 27
