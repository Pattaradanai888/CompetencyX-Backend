import re
import shutil
from collections import Counter
from io import StringIO
from pathlib import Path
from unittest.mock import patch

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
from roadmaps.questionnaire import CORE_ROLE_DIMENSIONS, ROLE_PROFILE_WEIGHTS, ROLE_TRAIT_AXES
from roadmaps.seeds import _sync_questions, load_curated_catalog


class SeedMvpContentTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_mvp_content')

    def test_seed_command_creates_catalog_and_is_idempotent(self):
        out = StringIO()
        _roles_data, _topics_data, questions_data = load_curated_catalog()
        expected_question_count = len(questions_data['role_questions']) + len(questions_data['skill_questions'])
        expected_option_count = sum(len(question['options']) for question in questions_data['role_questions'] + questions_data['skill_questions'])
        expected_role_signal_count = sum(
            len(option.get('role_signals', {})) for question in questions_data['role_questions'] for option in question['options']
        )
        expected_topic_signal_count = sum(
            len(option.get('topic_signals', [])) for question in questions_data['skill_questions'] for option in question['options']
        )

        call_command('seed_mvp_content', stdout=out)

        expected_role_count = len(load_curated_catalog()[0]['roles'])
        expected_topic_count = len(load_curated_catalog()[1]['topics'])
        expected_prereq_count = sum(len(topic.get('prerequisites', [])) for topic in load_curated_catalog()[1]['topics'])
        assert Role.objects.count() == expected_role_count
        assert RoadmapTopic.objects.count() == expected_topic_count
        assert TopicPrerequisite.objects.count() == expected_prereq_count
        assert Question.objects.count() == expected_question_count
        assert QuestionOption.objects.count() == expected_option_count
        assert QuestionRoleSignal.objects.count() == expected_role_signal_count
        assert QuestionTopicSignal.objects.count() == expected_topic_signal_count
        assert Role.objects.filter(slug='backend-engineer', is_active=True).exists()
        assert Question.objects.filter(code='backend-database-basics', topic__slug='databases').exists()

        first_run_output = out.getvalue()
        assert (
            f'Seeded {expected_role_count} roles, {expected_topic_count} topics, '
            f'{expected_question_count} questions, and {expected_option_count} options.'
        ) in first_run_output

    def test_each_seeded_role_has_minimal_runnable_path(self):
        for role in Role.objects.order_by('slug'):
            assert role.topics.filter(is_active=True).count() == 3
            assert role.questions.filter(stage=Question.Stage.SKILL, is_active=True).count() == 2
            assert TopicPrerequisite.objects.filter(topic__role=role).count() == 2

    def test_role_question_bank_covers_all_seeded_roles(self):
        assert set(ROLE_PROFILE_WEIGHTS) == set(Role.objects.values_list('slug', flat=True))

    def test_seed_command_is_idempotent(self):
        _roles_data, _topics_data, questions_data = load_curated_catalog()
        expected_question_count = len(questions_data['role_questions']) + len(questions_data['skill_questions'])
        expected_option_count = sum(len(question['options']) for question in questions_data['role_questions'] + questions_data['skill_questions'])

        call_command('seed_mvp_content')

        expected_role_count = len(load_curated_catalog()[0]['roles'])
        expected_topic_count = len(load_curated_catalog()[1]['topics'])
        expected_prereq_count = sum(len(topic.get('prerequisites', [])) for topic in load_curated_catalog()[1]['topics'])
        assert Role.objects.count() == expected_role_count
        assert RoadmapTopic.objects.count() == expected_topic_count
        assert TopicPrerequisite.objects.count() == expected_prereq_count
        assert Question.objects.count() == expected_question_count
        assert QuestionOption.objects.count() == expected_option_count

    def test_load_curated_content_removes_stale_questions(self):
        stale_question = Question.objects.create(
            code='stale-question',
            stage=Question.Stage.ROLE,
            question_type=Question.Type.SINGLE_CHOICE,
            prompt='Stale prompt',
            display_order=999,
        )
        QuestionOption.objects.create(
            question=stale_question,
            key='stale-option',
            label='Stale Option',
            display_order=1,
        )

        call_command('load_curated_content')

        assert not Question.objects.filter(code='stale-question').exists()

    def test_load_curated_catalog_merges_split_question_fragments(self):
        temp_dir = Path.cwd() / '.tmp-load-curated-catalog-test'
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        try:
            content_dir = temp_dir / 'content'
            (content_dir / 'questions' / 'role').mkdir(parents=True)
            (content_dir / 'questions' / 'skill').mkdir(parents=True)

            (content_dir / 'roles.yaml').write_text(
                (
                    'roles:\n'
                    '  - slug: backend-engineer\n'
                    '    name: Backend Engineer\n'
                    '    description: Builds APIs and backend services.\n'
                    '  - slug: cybersecurity-engineer\n'
                    '    name: Cybersecurity Engineer\n'
                    '    description: Protects systems and data.\n'
                    '  - slug: data-engineer\n'
                    '    name: Data Engineer\n'
                    '    description: Builds data pipelines and models.\n'
                    '  - slug: devops-engineer\n'
                    '    name: DevOps Engineer\n'
                    '    description: Automates delivery and operations.\n'
                    '  - slug: frontend-engineer\n'
                    '    name: Frontend Engineer\n'
                    '    description: Builds web user interfaces.\n'
                    '  - slug: full-stack-engineer\n'
                    '    name: Full-Stack Engineer\n'
                    '    description: Works across the stack.\n'
                    '  - slug: mobile-engineer\n'
                    '    name: Mobile Engineer\n'
                    '    description: Builds mobile app experiences.\n'
                    '  - slug: qa-test-engineer\n'
                    '    name: QA / Test Engineer\n'
                    '    description: Improves quality with testing and release validation.\n'
                ),
                encoding='utf-8',
            )
            (content_dir / 'topics.yaml').write_text(
                ('topics:\n  - role_slug: backend-engineer\n    slug: http\n    title: HTTP Fundamentals\n    display_order: 1\n'),
                encoding='utf-8',
            )
            (content_dir / 'questions' / 'role' / 'discovery.yaml').write_text(
                (
                    'role_questions:\n'
                    '  - code: role-primary-interest\n'
                    '    item_group: core\n'
                    '    question_type: single_choice\n'
                    '    prompt: Which work sounds most interesting?\n'
                    '    difficulty: 1\n'
                    '    discrimination_score: 3.0\n'
                    '    display_order: 1\n'
                    '    options:\n'
                    '      - key: backend\n'
                    '        label: Designing APIs and backend services\n'
                    '        display_order: 1\n'
                    '        dimension_signals: {technical_build: 1}\n'
                    '        role_signals: {backend-engineer: 4, full-stack-engineer: 1}\n'
                ),
                encoding='utf-8',
            )
            (content_dir / 'questions' / 'skill' / 'backend-engineer.yaml').write_text(
                (
                    'skill_questions:\n'
                    '  - code: backend-http-basics\n'
                    '    role_slug: backend-engineer\n'
                    '    topic_slug: http\n'
                    '    question_type: yes_no_maybe\n'
                    '    prompt: Are you comfortable with HTTP?\n'
                    '    difficulty: 1\n'
                    '    discrimination_score: 1.8\n'
                    '    display_order: 21\n'
                    '    options:\n'
                    '      - key: "yes"\n'
                    '        label: Yes\n'
                    '        display_order: 1\n'
                    '        topic_signals: [{topic_slug: http, mastery_delta: 1.0}]\n'
                ),
                encoding='utf-8',
            )

            with (
                patch('roadmaps.seeds.CURATED_CONTENT_DIR', content_dir),
                patch('roadmaps.seeds.QUESTION_BANK_DIR', content_dir / 'questions'),
                patch('roadmaps.seeds.LEGACY_QUESTION_FILE', content_dir / 'questions.yaml'),
                patch('roadmaps.seeds.validate_curated_catalog'),
            ):
                roles_data, topics_data, questions_data = load_curated_catalog()
        finally:
            if temp_dir.exists():
                shutil.rmtree(temp_dir)

        assert len(roles_data['roles']) == 8
        assert len(topics_data['topics']) == 1
        assert len(questions_data['role_questions']) == 1
        assert len(questions_data['skill_questions']) == 1

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
            topics_by_key = {(topic.role.slug, topic.slug): topic for topic in RoadmapTopic.objects.select_related('role')}
            _sync_questions(
                role_questions=legacy_questions['role_questions'],
                skill_questions=legacy_questions['skill_questions'],
                roles_by_slug=roles_by_slug,
                topics_by_key=topics_by_key,
            )

    def test_validate_question_catalog_command_reports_success(self):
        out = StringIO()
        _roles_data, _topics_data, questions_data = load_curated_catalog()
        expected_question_count = len(questions_data['role_questions']) + len(questions_data['skill_questions'])

        call_command('validate_question_catalog', stdout=out)

        expected_role_count = len(load_curated_catalog()[0]['roles'])
        expected_topic_count = len(load_curated_catalog()[1]['topics'])
        assert f'Validated {expected_role_count} roles, {expected_topic_count} topics, and {expected_question_count} questions.' in out.getvalue()

    def test_role_question_catalog_options_define_scoring_signals(self):
        _roles_data, _topics_data, questions_data = load_curated_catalog()

        assert all(
            option.get('dimension_signals') or option.get('role_signals')
            for question in questions_data['role_questions']
            for option in question['options']
        )

    def test_role_question_catalog_core_questions_measure_trait_axes_without_role_signals(self):
        _roles_data, _topics_data, questions_data = load_curated_catalog()

        endpoint_to_axis = {endpoint: axis for axis in ROLE_TRAIT_AXES for endpoint in axis}
        axis_question_counts = Counter()
        core_questions = sorted(
            [question for question in questions_data['role_questions'] if question.get('item_group', 'core') == 'core'],
            key=lambda question: question['display_order'],
        )

        assert len(core_questions) == 30
        assert [question['display_order'] for question in core_questions] == list(range(1, 31))
        observed_axis_order = []
        for question in core_questions:
            question_axes = set()
            endpoint_weights = Counter()
            assert len(question['options']) == 4
            for option in question['options']:
                assert option.get('role_signals') in (None, {})
                dimension_signals = option.get('dimension_signals', {})
                assert len(dimension_signals) == 1
                endpoint, weight = next(iter(dimension_signals.items()))
                assert float(weight) in {1.0, 2.0}
                endpoint_weights[endpoint] += float(weight)
                question_axes.add(endpoint_to_axis[endpoint])
            assert len(question_axes) == 1
            axis = next(iter(question_axes))
            assert set(endpoint_weights.values()) == {3.0}
            observed_axis_order.append(axis)
            axis_question_counts[axis] += 1

        assert dict(axis_question_counts) == dict.fromkeys(ROLE_TRAIT_AXES, 5)
        assert observed_axis_order == list(ROLE_TRAIT_AXES) * 5

    def test_every_role_has_trait_profile(self):
        roles_data, _topics_data, _questions_data = load_curated_catalog()

        role_slugs = {role['slug'] for role in roles_data['roles']}
        assert set(ROLE_PROFILE_WEIGHTS) == role_slugs
        assert all(ROLE_PROFILE_WEIGHTS[role_slug] for role_slug in role_slugs)

    def test_role_question_catalog_core_bank_covers_required_dimensions(self):
        _roles_data, _topics_data, questions_data = load_curated_catalog()

        covered_dimensions = set()
        for question in questions_data['role_questions']:
            if question.get('item_group', 'core') != 'core':
                continue
            for option in question['options']:
                covered_dimensions.update(option.get('dimension_signals', {}).keys())

        assert CORE_ROLE_DIMENSIONS.issubset(covered_dimensions)

    def test_role_question_catalog_core_dimensions_are_balanced(self):
        _roles_data, _topics_data, questions_data = load_curated_catalog()

        dimension_totals = Counter()
        for question in questions_data['role_questions']:
            if question.get('item_group', 'core') != 'core':
                continue
            for option in question['options']:
                for dimension_key, weight in option.get('dimension_signals', {}).items():
                    dimension_totals[dimension_key] += float(weight)

        assert CORE_ROLE_DIMENSIONS.issubset(dimension_totals)
        assert max(dimension_totals.values()) - min(dimension_totals.values()) <= 8

    def test_role_question_catalog_core_wording_is_beginner_friendly(self):
        _roles_data, _topics_data, questions_data = load_curated_catalog()

        word_pattern = re.compile(r"[A-Za-z0-9]+(?:[-'][A-Za-z0-9]+)?")
        long_prompts = {}
        long_labels = {}
        banned_terms = ('api contract', 'observability', 'runtime dependencies', 'interfaces', 'erp modules', 'technical standards')
        jargon_labels = {}

        for question in questions_data['role_questions']:
            if question.get('item_group', 'core') == 'core':
                prompt_word_count = len(word_pattern.findall(question['prompt']))
                if prompt_word_count > 16:
                    long_prompts[question['code']] = prompt_word_count
                for option in question['options']:
                    label_word_count = len(word_pattern.findall(option['label']))
                    if label_word_count > 12:
                        long_labels[(question['code'], option['key'])] = label_word_count

            for option in question['options']:
                label = option['label'].lower()
                matched_terms = [term for term in banned_terms if term in label]
                if matched_terms:
                    jargon_labels[(question['code'], option['key'])] = matched_terms

        assert long_prompts == {}
        assert long_labels == {}
        assert jargon_labels == {}

    def test_role_question_catalog_uses_static_core_only_for_role_discovery(self):
        _roles_data, _topics_data, questions_data = load_curated_catalog()

        assert [question.get('item_group', 'core') for question in questions_data['role_questions']] == ['core'] * 30
