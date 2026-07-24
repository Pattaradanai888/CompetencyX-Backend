import re
import shutil
from collections import Counter
from copy import deepcopy
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from assessments.models import Answer, AssessmentSession, SkillAssessmentDimension, SkillAssessmentQuestion, SkillAssessmentRoleGuidance
from roadmaps.models import (
    Question,
    QuestionOption,
    RoadmapTopic,
    Role,
    TopicPrerequisite,
)
from roadmaps.questionnaire import CORE_ROLE_DIMENSIONS, ROLE_PROFILE_WEIGHTS, SWEBOK_KNOWLEDGE_AREAS
from roadmaps.seeds import _sync_questions, load_curated_catalog, validate_curated_catalog


class SyncContentTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('sync_content')

    def test_sync_command_creates_all_catalogs_and_is_idempotent(self):
        out = StringIO()
        _roles_data, _topics_data, questions_data = load_curated_catalog()
        expected_question_count = len(questions_data['role_questions'])
        expected_option_count = 0

        call_command('sync_content', stdout=out)

        expected_role_count = len(load_curated_catalog()[0]['roles'])
        expected_topic_count = len(load_curated_catalog()[1]['topics'])
        expected_prereq_count = sum(len(topic.get('prerequisites', [])) for topic in load_curated_catalog()[1]['topics'])
        assert Role.objects.count() == expected_role_count
        assert RoadmapTopic.objects.count() == expected_topic_count
        assert TopicPrerequisite.objects.count() == expected_prereq_count
        assert Question.objects.count() == expected_question_count
        assert QuestionOption.objects.count() == expected_option_count
        assert SkillAssessmentDimension.objects.count() == 8
        assert SkillAssessmentQuestion.objects.count() == 11
        assert SkillAssessmentRoleGuidance.objects.count() == 14
        assert Role.objects.filter(slug='backend-developer', is_active=True).exists()
        assert Question.objects.filter(code='role-swebok-01-requirements', stage=Question.Stage.ROLE).exists()

        first_run_output = out.getvalue()
        assert (
            f'Seeded {expected_role_count} roles, {expected_topic_count} topics, '
            f'{expected_question_count} questions, and {expected_option_count} options.'
        ) in first_run_output

    def test_each_seeded_role_has_minimal_runnable_path(self):
        for role in Role.objects.order_by('slug'):
            assert role.topics.filter(is_active=True).count() == 3
            assert TopicPrerequisite.objects.filter(topic__role=role).count() == 2
        assert Question.objects.filter(stage='skill').count() == 0

    def test_role_question_bank_covers_all_seeded_roles(self):
        assert set(ROLE_PROFILE_WEIGHTS) == set(Role.objects.values_list('slug', flat=True))

    def test_sync_command_is_idempotent(self):
        _roles_data, _topics_data, questions_data = load_curated_catalog()
        expected_question_count = len(questions_data['role_questions'])
        expected_option_count = 0

        call_command('sync_content')

        expected_role_count = len(load_curated_catalog()[0]['roles'])
        expected_topic_count = len(load_curated_catalog()[1]['topics'])
        expected_prereq_count = sum(len(topic.get('prerequisites', [])) for topic in load_curated_catalog()[1]['topics'])
        assert Role.objects.count() == expected_role_count
        assert RoadmapTopic.objects.count() == expected_topic_count
        assert TopicPrerequisite.objects.count() == expected_prereq_count
        assert Question.objects.count() == expected_question_count
        assert QuestionOption.objects.count() == expected_option_count

    def test_sync_command_rolls_back_all_catalogs_on_failure(self):
        role = Role.objects.get(slug='backend-developer')
        role.name = 'Temporary Backend Name'
        role.save(update_fields=['name'])

        with (
            patch('api.management.commands.sync_content.sync_skill_assessment_catalog', side_effect=RuntimeError('sync failed')),
            self.assertRaisesMessage(RuntimeError, 'sync failed'),
        ):
            call_command('sync_content')

        role.refresh_from_db()
        assert role.name == 'Temporary Backend Name'

    def test_sync_content_deactivates_stale_questions_without_deleting_history(self):
        stale_question = Question.objects.create(
            code='stale-question',
            stage=Question.Stage.ROLE,
            question_type=Question.Type.SINGLE_CHOICE,
            prompt='Stale prompt',
            display_order=999,
        )
        stale_option = QuestionOption.objects.create(
            question=stale_question,
            key='stale-option',
            label='Stale Option',
            display_order=1,
        )
        session = AssessmentSession.objects.create()
        answer = Answer.objects.create(session=session, question=stale_question, selected_option=stale_option)

        call_command('sync_content')

        stale_question.refresh_from_db()
        answer.refresh_from_db()
        assert not stale_question.is_active
        assert answer.question_id == stale_question.id

    def test_sync_content_deactivates_stale_curated_topics(self):
        role = Role.objects.get(slug='backend-developer')
        stale_topic = RoadmapTopic.objects.create(
            role=role,
            slug='stale-curated-topic',
            title='Stale curated topic',
            display_order=999,
        )

        call_command('sync_content')

        stale_topic.refresh_from_db()
        assert not stale_topic.is_active

    def test_sync_content_deactivates_stale_skill_assessment_catalog_rows(self):
        role = Role.objects.get(slug='backend-developer')
        stale_dimension = SkillAssessmentDimension.objects.create(
            dimension_key='stale-dimension',
            label='Stale dimension',
            track=SkillAssessmentDimension.Track.PSP,
            low_score_action='Stale action',
        )
        stale_question = SkillAssessmentQuestion.objects.create(
            question_id='stale-skill-question',
            prompt='Stale skill question',
            dimension_key=stale_dimension.dimension_key,
        )
        stale_guidance = SkillAssessmentRoleGuidance.objects.create(role=role, guidance='Stale guidance', display_order=999)

        call_command('sync_content')

        stale_dimension.refresh_from_db()
        stale_question.refresh_from_db()
        stale_guidance.refresh_from_db()
        assert not stale_dimension.is_active
        assert not stale_question.is_active
        assert not stale_guidance.is_active

    def test_load_curated_catalog_merges_role_question_fragments_only(self):
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
                    '    question_type: likert_5\n'
                    '    prompt: I enjoy turning ideas into working technical parts.\n'
                    '    agree_dimension_signals: {construction: 1.0, application_build: 0.5}\n'
                    '    disagree_dimension_signals: {requirements: 1.0, people_product: 0.5}\n'
                    '    difficulty: 1\n'
                    '    discrimination_score: 3.0\n'
                    '    display_order: 1\n'
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
        assert len(questions_data['skill_questions']) == 0

    def test_sync_content_command_populates_swebok_role_metadata(self):
        call_command('sync_content')

        role = Role.objects.get(slug='backend-developer')
        assert role.swebok_source_version == 'SWEBOK V4.0'
        assert role.top_ka_codes == ['KA4', 'KA2', 'KA6']
        assert role.core_tasks[0]['ka_codes'] == ['KA2', 'KA4']

    def test_import_roadmap_snapshot_command_normalizes_raw_graph(self):
        snapshot_path = Path('data/upstream/roadmap_sh/backend-engineer.sample.json')
        role = Role.objects.get(slug='backend-developer')
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

    def test_load_curated_content_deactivates_legacy_skill_questions(self):
        role = Role.objects.get(slug='backend-developer')
        topic = RoadmapTopic.objects.filter(role=role).first()
        Question.objects.create(
            code='legacy-skill-question',
            stage='skill',
            role=role,
            topic=topic,
            question_type=Question.Type.YES_NO_MAYBE,
            prompt='Legacy skill prompt',
            difficulty=1,
            discrimination_score=1.0,
            display_order=999,
        )

        roles_by_slug = {role.slug: role for role in Role.objects.all()}
        topics_by_key = {(topic.role.slug, topic.slug): topic for topic in RoadmapTopic.objects.select_related('role')}
        _sync_questions(
            role_questions=load_curated_catalog()[2]['role_questions'],
            roles_by_slug=roles_by_slug,
            topics_by_key=topics_by_key,
        )

        assert not Question.objects.get(code='legacy-skill-question').is_active

    def test_load_curated_content_syncs_role_question_thai_translations(self):
        call_command('sync_content')

        role_questions = Question.objects.filter(stage=Question.Stage.ROLE).order_by('display_order')

        assert role_questions.count() == 58
        thai_translated = [q for q in role_questions if q.translations.get('th', {}).get('prompt')]
        assert len(thai_translated) == 48
        assert role_questions.get(code='role-swebok-01-requirements').translations['th']['prompt'] == (
            'ในช่วงท้าย Sprint ที่เวลาบีบคั้นแต่ Requirement ยังคลุมเครือ ฉันจะเลือกจัดเวิร์กช็อปเพื่อถอดโจทย์ปัญหาให้เคลียร์ แม้จะต้องแลกกับการเริ่มต้นเขียนโค้ดล่าช้ากว่ากำหนดก็ตาม'
        )
        assert Question.objects.filter(stage='skill').count() == 0

    def test_question_catalog_rejects_unsupported_translation_language(self):
        roles_data, topics_data, questions_data = load_curated_catalog()
        invalid_questions = deepcopy(questions_data)
        invalid_questions['role_questions'][0]['translations'] = {'fr': {'prompt': 'Bonjour'}}

        with self.assertRaisesMessage(
            ValueError,
            'Question "role-swebok-01-requirements" has unsupported translation language(s): fr',
        ):
            validate_curated_catalog(roles_data=roles_data, topics_data=topics_data, questions_data=invalid_questions)

    def test_question_catalog_rejects_unsupported_role_question_translation_fields(self):
        roles_data, topics_data, questions_data = load_curated_catalog()
        invalid_questions = deepcopy(questions_data)
        invalid_questions['role_questions'][0]['translations'] = {'th': {'prompt': 'Bonjour', 'label': 'Wrong field'}}

        with self.assertRaisesMessage(
            ValueError,
            'Question "role-swebok-01-requirements" has unsupported th translation field(s): label',
        ):
            validate_curated_catalog(roles_data=roles_data, topics_data=topics_data, questions_data=invalid_questions)

    def test_question_catalog_excludes_skill_questions_from_role_discovery(self):
        _roles_data, _topics_data, questions_data = load_curated_catalog()

        assert questions_data['skill_questions'] == []

    def test_validate_question_catalog_command_reports_success(self):
        out = StringIO()
        _roles_data, _topics_data, questions_data = load_curated_catalog()
        expected_question_count = len(questions_data['role_questions'])

        call_command('validate_question_catalog', stdout=out)

        expected_role_count = len(load_curated_catalog()[0]['roles'])
        expected_topic_count = len(load_curated_catalog()[1]['topics'])
        assert f'Validated {expected_role_count} roles, {expected_topic_count} topics, and {expected_question_count} questions.' in out.getvalue()

    def test_role_question_validation_rejects_unknown_signal_dimension(self):
        roles_data, topics_data, questions_data = load_curated_catalog()
        invalid_questions = deepcopy(questions_data)
        invalid_questions['role_questions'][0]['agree_signals'] = {'unknown_trait': 'primary'}

        with self.assertRaisesMessage(
            ValueError,
            'Role question "role-swebok-01-requirements" has unknown agree_signals: unknown_trait',
        ):
            validate_curated_catalog(roles_data=roles_data, topics_data=topics_data, questions_data=invalid_questions)

    def test_role_question_validation_rejects_role_options(self):
        roles_data, topics_data, questions_data = load_curated_catalog()
        invalid_questions = deepcopy(questions_data)
        invalid_questions['role_questions'][0]['options'] = [{'key': 'agree', 'label': 'Agree', 'display_order': 1}]

        with self.assertRaisesMessage(ValueError, 'Role question "role-swebok-01-requirements" must not define options.'):
            validate_curated_catalog(roles_data=roles_data, topics_data=topics_data, questions_data=invalid_questions)

    def test_role_question_validation_rejects_non_likert_role_question(self):
        roles_data, topics_data, questions_data = load_curated_catalog()
        invalid_questions = deepcopy(questions_data)
        invalid_questions['role_questions'][0]['question_type'] = Question.Type.SINGLE_CHOICE

        with self.assertRaisesMessage(ValueError, 'Role question "role-swebok-01-requirements" must use question_type "likert_5".'):
            validate_curated_catalog(roles_data=roles_data, topics_data=topics_data, questions_data=invalid_questions)

    def test_role_question_catalog_uses_likert_statements_without_options(self):
        _roles_data, _topics_data, questions_data = load_curated_catalog()

        assert all(
            question['question_type'] == Question.Type.LIKERT_5
            and question.get('options', []) == []
            and question.get('agree_signals')
            and question.get('disagree_signals')
            for question in questions_data['role_questions']
        )

    def test_role_question_catalog_core_questions_measure_swebok_knowledge_areas(self):
        _roles_data, _topics_data, questions_data = load_curated_catalog()

        core_questions = sorted(
            [question for question in questions_data['role_questions'] if question.get('item_group', 'core') == 'core'],
            key=lambda question: question['display_order'],
        )

        assert len(core_questions) == 46
        assert [question['display_order'] for question in core_questions] == list(range(1, 47))
        dimension_counts = Counter()
        for question in core_questions:
            signaled_dimensions = set(question['agree_signals']) | set(question['disagree_signals'])
            for dimension in signaled_dimensions & CORE_ROLE_DIMENSIONS:
                dimension_counts[dimension] += 1

        assert set(dimension_counts) == {dimension for dimension, _label in SWEBOK_KNOWLEDGE_AREAS}
        assert all(count >= 2 for count in dimension_counts.values())

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
            covered_dimensions.update((set(question['agree_signals']) | set(question['disagree_signals'])) & CORE_ROLE_DIMENSIONS)

        assert CORE_ROLE_DIMENSIONS.issubset(covered_dimensions)

    def test_role_question_catalog_core_dimensions_are_balanced(self):
        _roles_data, _topics_data, questions_data = load_curated_catalog()

        dimension_totals = Counter()
        for question in questions_data['role_questions']:
            if question.get('item_group', 'core') != 'core':
                continue
            signaled_dimensions = set(question['agree_signals']) | set(question['disagree_signals'])
            for dimension in signaled_dimensions & CORE_ROLE_DIMENSIONS:
                dimension_totals[dimension] += 1

        assert set(dimension_totals) == {dimension for dimension, _label in SWEBOK_KNOWLEDGE_AREAS}
        assert all(count >= 2 for count in dimension_totals.values())

    def test_role_question_catalog_core_wording_is_beginner_friendly(self):
        _roles_data, _topics_data, questions_data = load_curated_catalog()

        word_pattern = re.compile(r"[A-Za-z0-9]+(?:[-'][A-Za-z0-9]+)?")
        long_prompts = {}
        banned_terms = ('api contract', 'observability', 'runtime dependencies', 'interfaces', 'erp modules', 'technical standards')
        jargon_prompts = {}

        for question in questions_data['role_questions']:
            if question.get('item_group', 'core') == 'core':
                prompt_word_count = len(word_pattern.findall(question['prompt']))
                if prompt_word_count > 32:
                    long_prompts[question['code']] = prompt_word_count
                prompt = question['prompt'].lower()
                matched_terms = [term for term in banned_terms if term in prompt]
                if matched_terms:
                    jargon_prompts[question['code']] = matched_terms

        assert long_prompts == {}
        assert jargon_prompts == {}

    def test_role_question_catalog_uses_static_core_only_for_role_discovery(self):
        _roles_data, _topics_data, questions_data = load_curated_catalog()

        item_groups = Counter(question.get('item_group', 'core') for question in questions_data['role_questions'])
        assert item_groups == Counter({'core': 46, 'tie_break': 12})
