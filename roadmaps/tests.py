from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase

from roadmaps.models import (
    Question,
    QuestionOption,
    QuestionRoleSignal,
    QuestionTopicSignal,
    RoadmapTopic,
    Role,
    TopicPrerequisite,
)
from roadmaps.seeds import _sync_questions


class SeedMvpContentTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_mvp_content')

    def test_seed_command_creates_catalog_and_is_idempotent(self):
        out = StringIO()

        call_command('seed_mvp_content', stdout=out)

        assert Role.objects.count() == 8
        assert RoadmapTopic.objects.count() == 24
        assert TopicPrerequisite.objects.count() == 16
        assert Question.objects.count() == 19
        assert QuestionOption.objects.count() == 65
        assert QuestionRoleSignal.objects.count() == 31
        assert QuestionTopicSignal.objects.count() == 48
        assert Role.objects.filter(slug='backend-engineer', is_active=True).exists()
        assert Question.objects.filter(code='backend-database-basics', topic__slug='databases').exists()

        first_run_output = out.getvalue()
        assert 'Seeded 8 roles, 24 topics, 19 questions, and 65 options.' in first_run_output

    def test_each_seeded_role_has_minimal_runnable_path(self):
        for role in Role.objects.order_by('slug'):
            assert role.topics.filter(is_active=True).count() == 3
            assert role.questions.filter(stage=Question.Stage.SKILL, is_active=True).count() == 2
            assert TopicPrerequisite.objects.filter(topic__role=role).count() == 2

    def test_role_inference_question_covers_all_seeded_roles(self):
        question = Question.objects.get(code='role-primary-interest')
        weighted_role_slugs = set(
            QuestionRoleSignal.objects.filter(question_option__question=question).values_list('role__slug', flat=True)
        )

        assert weighted_role_slugs == set(Role.objects.values_list('slug', flat=True))

    def test_seed_command_is_idempotent(self):
        call_command('seed_mvp_content')

        assert Role.objects.count() == 8
        assert RoadmapTopic.objects.count() == 24
        assert TopicPrerequisite.objects.count() == 16
        assert Question.objects.count() == 19
        assert QuestionOption.objects.count() == 65

    def test_load_curated_content_command_populates_external_metadata(self):
        call_command('load_curated_content')

        topic = RoadmapTopic.objects.get(role__slug='backend-engineer', slug='http')
        assert topic.external_source == 'roadmap.sh'
        assert topic.external_id == 'backend-http'
        assert topic.external_slug == 'http'

    def test_import_roadmap_snapshot_command_normalizes_raw_graph(self):
        snapshot_path = Path('data/upstream/roadmap_sh/backend-engineer.sample.json')
        role = Role.objects.get(slug='backend-engineer')
        role.topics.all().delete()

        call_command(
            'import_roadmap_snapshot',
            '--path',
            str(snapshot_path),
            '--role-slug',
            role.slug,
            '--source',
            'roadmap.sh',
            '--source-version',
            'sample-v1',
        )

        assert role.topics.count() == 3
        assert TopicPrerequisite.objects.filter(topic__role=role).count() == 2
        imported_topic = RoadmapTopic.objects.get(role=role, slug='http')
        assert imported_topic.external_source == 'roadmap.sh'
        assert imported_topic.source_version == 'sample-v1'

    def test_load_curated_content_rejects_legacy_option_fields(self):
        legacy_questions = {
            'role_questions': [],
            'skill_questions': [
                {
                    'code': 'backend-http-basics',
                    'role_slug': 'backend-engineer',
                    'topic_slug': 'http',
                    'question_type': 'yes_no_maybe',
                    'prompt': 'Legacy fixture',
                    'difficulty': 1,
                    'discrimination_score': 1.0,
                    'display_order': 1,
                    'options': [
                        {
                            'key': 'yes',
                            'label': 'Yes',
                            'display_order': 1,
                            'mastery_value': 1.0,
                            'topic_signals': [{'topic_slug': 'http', 'mastery_delta': 1.0}],
                        }
                    ],
                }
            ],
        }

        with self.assertRaisesMessage(
            ValueError,
            'Unsupported option seed field(s) for question "backend-http-basics": mastery_value',
        ):
            roles_by_slug = {role.slug: role for role in Role.objects.all()}
            topics_by_key = {
                (topic.role.slug, topic.slug): topic
                for topic in RoadmapTopic.objects.select_related('role')
            }
            _sync_questions(
                role_questions=legacy_questions['role_questions'],
                skill_questions=legacy_questions['skill_questions'],
                roles_by_slug=roles_by_slug,
                topics_by_key=topics_by_key,
            )
