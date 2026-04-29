import json
from pathlib import Path
from types import SimpleNamespace

import yaml

from roadmaps.models import (
    Question,
    QuestionOption,
    QuestionTopicSignal,
    RoadmapTopic,
    Role,
    TopicPrerequisite,
)
from roadmaps.questionnaire import CORE_ROLE_DIMENSIONS, ROLE_DIMENSIONS


BASE_DATA_DIR = Path(__file__).resolve().parent.parent / 'data'
CURATED_CONTENT_DIR = BASE_DATA_DIR / 'content'
QUESTION_BANK_DIR = CURATED_CONTENT_DIR / 'questions'
LEGACY_QUESTION_FILE = CURATED_CONTENT_DIR / 'questions.yaml'
UPSTREAM_SNAPSHOT_DIR = BASE_DATA_DIR / 'upstream' / 'roadmap_sh'
MIN_TIE_BREAK_ROLE_COUNT = 2


def seed_mvp_content(*, stdout=None):
    load_curated_content(stdout=stdout)


def load_curated_content(*, stdout=None):
    roles_data, topics_data, questions_data = load_curated_catalog()

    roles_by_slug = _sync_roles(roles_data['roles'])
    topics_by_key = _sync_topics(topics_data['topics'], roles_by_slug)
    _sync_questions(
        role_questions=questions_data['role_questions'],
        skill_questions=questions_data['skill_questions'],
        roles_by_slug=roles_by_slug,
        topics_by_key=topics_by_key,
    )

    if stdout is not None:
        stdout.write(
            f'Seeded {Role.objects.count()} roles, '
            f'{RoadmapTopic.objects.count()} topics, '
            f'{Question.objects.count()} questions, and '
            f'{QuestionOption.objects.count()} options.'
        )


def load_curated_catalog():
    roles_data = _load_yaml(CURATED_CONTENT_DIR / 'roles.yaml')
    topics_data = _load_yaml(CURATED_CONTENT_DIR / 'topics.yaml')
    questions_data = _load_question_bank()
    validate_curated_catalog(roles_data=roles_data, topics_data=topics_data, questions_data=questions_data)
    return roles_data, topics_data, questions_data


def _load_question_bank():
    if QUESTION_BANK_DIR.exists():
        question_fragments = sorted(QUESTION_BANK_DIR.rglob('*.yaml'))
        if not question_fragments:
            msg = f'No question fragments were found in "{QUESTION_BANK_DIR}".'
            raise FileNotFoundError(msg)

        questions_data = {'role_questions': [], 'skill_questions': []}
        for fragment_path in question_fragments:
            fragment = _load_yaml(fragment_path)
            if fragment is None:
                continue
            questions_data['role_questions'].extend(fragment.get('role_questions', []))
            questions_data['skill_questions'].extend(fragment.get('skill_questions', []))
        return questions_data

    return _load_yaml(LEGACY_QUESTION_FILE)


def validate_curated_catalog(*, roles_data: dict, topics_data: dict, questions_data: dict):
    role_slugs = {role_seed['slug'] for role_seed in roles_data['roles']}
    topic_keys = {(topic_seed['role_slug'], topic_seed['slug']) for topic_seed in topics_data['topics']}
    question_codes: set[str] = set()

    for role_question in questions_data['role_questions']:
        _validate_role_question_seed(role_question, role_slugs=role_slugs, existing_codes=question_codes)

    for skill_question in questions_data['skill_questions']:
        _validate_skill_question_seed(
            skill_question,
            role_slugs=role_slugs,
            topic_keys=topic_keys,
            existing_codes=question_codes,
        )
    _validate_role_question_bank(questions_data['role_questions'])


def import_roadmap_snapshot(*, snapshot_path: Path, role_slug: str, source='roadmap.sh', source_version=''):
    snapshot = json.loads(snapshot_path.read_text(encoding='utf-8'))
    role = Role.objects.get(slug=role_slug)

    nodes = _extract_snapshot_nodes(snapshot)
    edges = _extract_snapshot_edges(snapshot)

    topics_by_external_id: dict[str, RoadmapTopic] = {}
    for index, node in enumerate(nodes, start=1):
        topic, _created = RoadmapTopic.objects.update_or_create(
            role=role,
            slug=node['slug'],
            defaults={
                'title': node['title'],
                'description': node.get('description', ''),
                'difficulty': RoadmapTopic.Difficulty.BEGINNER,
                'display_order': index,
                'is_active': True,
                'parent': None,
                'external_source': source,
                'external_id': node['id'],
                'external_slug': node['slug'],
                'source_version': source_version,
            },
        )
        topics_by_external_id[node['id']] = topic

    TopicPrerequisite.objects.filter(topic__role=role, topic__external_source=source).delete()
    for edge in edges:
        source_topic = topics_by_external_id.get(edge['source'])
        target_topic = topics_by_external_id.get(edge['target'])
        if source_topic is None or target_topic is None:
            continue
        TopicPrerequisite.objects.update_or_create(
            topic=target_topic,
            prerequisite=source_topic,
            defaults={
                'required_mastery_threshold': 0.7,
                'dependency_weight': 1.0,
            },
        )


def _sync_roles(role_seeds: list[dict]):
    roles_by_slug: dict[str, Role] = {}
    for role_seed in role_seeds:
        role, _created = Role.objects.update_or_create(
            slug=role_seed['slug'],
            defaults={
                'name': role_seed['name'],
                'description': role_seed.get('description', ''),
                'top_ka_codes': role_seed.get('top_ka_codes', []),
                'core_tasks': role_seed.get('core_tasks', []),
                'swebok_source_version': role_seed.get('swebok_source_version', ''),
                'is_active': True,
            },
        )
        roles_by_slug[role.slug] = role
    Role.objects.exclude(slug__in=roles_by_slug).update(is_active=False)
    return roles_by_slug


def _sync_topics(topic_seeds: list[dict], roles_by_slug: dict[str, Role]):
    topics_by_key: dict[tuple[str, str], RoadmapTopic] = {}
    for topic_seed in topic_seeds:
        role = roles_by_slug[topic_seed['role_slug']]
        topic, _created = RoadmapTopic.objects.update_or_create(
            role=role,
            slug=topic_seed['slug'],
            defaults={
                'title': topic_seed['title'],
                'description': topic_seed.get('description', ''),
                'difficulty': topic_seed.get('difficulty', RoadmapTopic.Difficulty.BEGINNER),
                'display_order': topic_seed['display_order'],
                'is_active': True,
                'parent': None,
                'external_source': topic_seed.get('external_source', ''),
                'external_id': topic_seed.get('external_id', ''),
                'external_slug': topic_seed.get('external_slug', ''),
                'source_version': topic_seed.get('source_version', ''),
            },
        )
        topics_by_key[(role.slug, topic.slug)] = topic

    TopicPrerequisite.objects.all().delete()
    for topic_seed in topic_seeds:
        role_slug = topic_seed['role_slug']
        for prerequisite_slug in topic_seed.get('prerequisites', []):
            TopicPrerequisite.objects.update_or_create(
                topic=topics_by_key[(role_slug, topic_seed['slug'])],
                prerequisite=topics_by_key[(role_slug, prerequisite_slug)],
                defaults={
                    'required_mastery_threshold': 0.7,
                    'dependency_weight': 1.0,
                },
            )
    return topics_by_key


def _sync_questions(*, role_questions: list[dict], skill_questions: list[dict], roles_by_slug, topics_by_key):
    seed_codes = {question_seed['code'] for question_seed in [*role_questions, *skill_questions]}
    for question_seed in role_questions:
        agree_dimension_signals = question_seed.get('agree_dimension_signals', {})
        disagree_dimension_signals = question_seed.get('disagree_dimension_signals', {})
        trait_positive_dimension = question_seed.get('trait_positive_dimension') or next(iter(agree_dimension_signals), '')
        question, _created = Question.objects.update_or_create(
            code=question_seed['code'],
            defaults={
                'stage': Question.Stage.ROLE,
                'question_type': question_seed['question_type'],
                'prompt': question_seed['prompt'],
                'help_text': question_seed.get('help_text', ''),
                'role': None,
                'topic': None,
                'difficulty': question_seed['difficulty'],
                'discrimination_score': question_seed['discrimination_score'],
                'item_group': question_seed.get('item_group', Question.ItemGroup.CORE),
                'discriminates_between': question_seed.get('discriminates_between', []),
                'agree_dimension_signals': agree_dimension_signals,
                'disagree_dimension_signals': disagree_dimension_signals,
                'trait_positive_dimension': trait_positive_dimension,
                'display_order': question_seed['display_order'],
                'is_active': True,
            },
        )
        question.options.all().delete()

    Question.objects.exclude(code__in=seed_codes).delete()

    for question_seed in skill_questions:
        role = roles_by_slug[question_seed['role_slug']]
        topic = topics_by_key[(question_seed['role_slug'], question_seed['topic_slug'])]
        question, _created = Question.objects.update_or_create(
            code=question_seed['code'],
            defaults={
                'stage': Question.Stage.SKILL,
                'question_type': question_seed['question_type'],
                'prompt': question_seed['prompt'],
                'help_text': question_seed.get('help_text', ''),
                'role': role,
                'topic': topic,
                'difficulty': question_seed['difficulty'],
                'discrimination_score': question_seed['discrimination_score'],
                'item_group': Question.ItemGroup.STANDARD,
                'discriminates_between': [],
                'agree_dimension_signals': {},
                'disagree_dimension_signals': {},
                'trait_positive_dimension': '',
                'display_order': question_seed['display_order'],
                'is_active': True,
            },
        )
        _sync_question_options(question, question_seed['options'], topics_by_key=topics_by_key)


def _sync_question_options(question: Question, option_seeds: list[dict], *, topics_by_key):
    existing_keys = set(question.options.values_list('key', flat=True))
    seed_keys = set()
    for option_seed in option_seeds:
        _validate_option_seed(option_seed, question=question)
        seed_keys.add(option_seed['key'])
        option, _created = QuestionOption.objects.update_or_create(
            question=question,
            key=option_seed['key'],
            defaults={
                'label': option_seed['label'],
                'value': option_seed.get('value', ''),
                'display_order': option_seed['display_order'],
            },
        )
        _sync_topic_signals(
            option,
            option_seed.get('topic_signals', []),
            question=question,
            topics_by_key=topics_by_key,
        )
    if existing_keys - seed_keys:
        question.options.exclude(key__in=seed_keys).delete()


def _validate_option_seed(option_seed: dict, *, question: Question) -> None:
    unsupported_fields = {'dimension_signals', 'mastery_value', 'role_signals', 'role_weights'} & option_seed.keys()
    if not unsupported_fields:
        return

    fields = ', '.join(sorted(unsupported_fields))
    msg = f'Unsupported option seed field(s) for question "{question.code}": {fields}'
    raise ValueError(msg)


def _validate_question_seed_uniqueness(question_seed: dict, *, existing_codes: set[str]) -> None:
    code = question_seed['code']
    if code in existing_codes:
        msg = f'Duplicate question code in curated content: "{code}"'
        raise ValueError(msg)
    existing_codes.add(code)


def _validate_option_key_uniqueness(question_code: str, option_seed: dict, option_keys: set[str]) -> None:
    option_key = option_seed['key']
    if option_key in option_keys:
        msg = f'Duplicate option key for question "{question_code}": "{option_key}"'
        raise ValueError(msg)
    option_keys.add(option_key)


def _validate_role_question_seed(role_question: dict, *, role_slugs: set[str], existing_codes: set[str]) -> None:
    _validate_question_seed_uniqueness(role_question, existing_codes=existing_codes)
    item_group = role_question.get('item_group', Question.ItemGroup.CORE)
    if item_group not in {Question.ItemGroup.CORE, Question.ItemGroup.TIE_BREAK}:
        msg = f'Role question "{role_question["code"]}" must use item_group "core" or "tie_break".'
        raise ValueError(msg)
    if role_question.get('question_type') != Question.Type.LIKERT_5:
        msg = f'Role question "{role_question["code"]}" must use question_type "likert_5".'
        raise ValueError(msg)
    if role_question.get('options'):
        msg = f'Role question "{role_question["code"]}" must not define options.'
        raise ValueError(msg)
    agree_dimension_signals = _validate_dimension_signal_map(role_question, field_name='agree_dimension_signals')
    disagree_dimension_signals = _validate_dimension_signal_map(role_question, field_name='disagree_dimension_signals')
    if item_group == Question.ItemGroup.CORE:
        core_signal_dimensions = set(agree_dimension_signals) | set(disagree_dimension_signals)
        if not core_signal_dimensions & CORE_ROLE_DIMENSIONS:
            msg = f'Core role question "{role_question["code"]}" must signal at least one SWEBOK knowledge area.'
            raise ValueError(msg)

    _validate_role_question_pairing(role_question, item_group=item_group, role_slugs=role_slugs)


def _validate_dimension_signal_map(role_question: dict, *, field_name: str) -> dict:
    signals = role_question.get(field_name)
    if not isinstance(signals, dict) or not signals:
        msg = f'Role question "{role_question["code"]}" must define {field_name}.'
        raise ValueError(msg)
    unknown_dimensions = sorted(set(signals) - set(ROLE_DIMENSIONS))
    if unknown_dimensions:
        msg = f'Role question "{role_question["code"]}" has unknown {field_name}: {", ".join(unknown_dimensions)}'
        raise ValueError(msg)
    invalid_weights = sorted(key for key, value in signals.items() if not isinstance(value, int | float) or float(value) <= 0)
    if invalid_weights:
        msg = f'Role question "{role_question["code"]}" has invalid {field_name} weight(s): {", ".join(invalid_weights)}'
        raise ValueError(msg)
    return signals


def _validate_role_question_pairing(role_question: dict, *, item_group: str, role_slugs: set[str]) -> None:
    discriminates_between = role_question.get('discriminates_between', [])
    if item_group != Question.ItemGroup.TIE_BREAK:
        return
    if len(discriminates_between) < MIN_TIE_BREAK_ROLE_COUNT:
        msg = f'Role tie-break question "{role_question["code"]}" must declare at least two roles in discriminates_between.'
        raise ValueError(msg)
    unknown_pair_roles = sorted(set(discriminates_between) - role_slugs)
    if unknown_pair_roles:
        msg = f'Unknown role slug(s) for question "{role_question["code"]}": {", ".join(unknown_pair_roles)}'
        raise ValueError(msg)


def _validate_skill_question_seed(skill_question: dict, *, role_slugs: set[str], topic_keys: set[tuple[str, str]], existing_codes: set[str]):
    _validate_question_seed_uniqueness(skill_question, existing_codes=existing_codes)
    role_slug = skill_question['role_slug']
    topic_slug = skill_question['topic_slug']
    if role_slug not in role_slugs:
        msg = f'Unknown role slug for skill question "{skill_question["code"]}": {role_slug}'
        raise ValueError(msg)
    if (role_slug, topic_slug) not in topic_keys:
        msg = f'Unknown topic reference for skill question "{skill_question["code"]}": {role_slug}/{topic_slug}'
        raise ValueError(msg)

    option_keys = set()
    question_stub = SimpleNamespace(code=skill_question['code'])
    for option_seed in skill_question['options']:
        _validate_option_seed(option_seed, question=question_stub)
        _validate_option_key_uniqueness(skill_question['code'], option_seed, option_keys)
        topic_signals = option_seed.get('topic_signals', [])
        if not topic_signals:
            msg = f'Skill question "{skill_question["code"]}" option "{option_seed["key"]}" must define topic signals.'
            raise ValueError(msg)
        signal_topics = {(signal.get('role_slug') or role_slug, signal['topic_slug']) for signal in topic_signals}
        if signal_topics != {(role_slug, topic_slug)}:
            msg = f'Skill question "{skill_question["code"]}" option "{option_seed["key"]}" must only target the question topic.'
            raise ValueError(msg)


def _validate_role_question_bank(role_questions: list[dict]) -> None:
    core_dimensions = set()
    for question in role_questions:
        item_group = question.get('item_group', Question.ItemGroup.CORE)
        if item_group == Question.ItemGroup.CORE:
            question_dimensions = set(question.get('agree_dimension_signals', {})) | set(question.get('disagree_dimension_signals', {}))
            question_core_dimensions = question_dimensions & CORE_ROLE_DIMENSIONS
            core_dimensions.update(question_core_dimensions)

    missing_dimensions = sorted(CORE_ROLE_DIMENSIONS - core_dimensions)
    if missing_dimensions:
        msg = f'Core role question bank is missing dimension coverage for: {", ".join(missing_dimensions)}'
        raise ValueError(msg)


def _sync_topic_signals(option: QuestionOption, topic_signals: list[dict], *, question: Question, topics_by_key):
    signal_keys = set()
    for signal in topic_signals:
        role_slug = signal.get('role_slug') or (question.role.slug if question.role else None)
        if role_slug is None:
            continue
        topic = topics_by_key[(role_slug, signal['topic_slug'])]
        signal_keys.add(topic.id)
        QuestionTopicSignal.objects.update_or_create(
            question_option=option,
            topic=topic,
            defaults={'mastery_delta': float(signal['mastery_delta'])},
        )
    if signal_keys:
        QuestionTopicSignal.objects.filter(question_option=option).exclude(topic_id__in=signal_keys).delete()
    else:
        QuestionTopicSignal.objects.filter(question_option=option).delete()


def _load_yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding='utf-8'))


def _extract_snapshot_nodes(snapshot: dict):
    nodes = snapshot.get('nodes', [])
    if isinstance(nodes, dict):
        nodes = list(nodes.values())
    normalized = []
    for node in nodes:
        node_id = str(node['id'])
        title = node.get('title') or node.get('label') or node_id
        slug = node.get('slug') or _slugify(title)
        normalized.append(
            {
                'id': node_id,
                'title': title,
                'slug': slug,
                'description': node.get('description', ''),
            }
        )
    return normalized


def _extract_snapshot_edges(snapshot: dict):
    edges = snapshot.get('edges', [])
    if isinstance(edges, dict):
        edges = list(edges.values())
    return [
        {
            'source': str(edge['source']),
            'target': str(edge['target']),
        }
        for edge in edges
    ]


def _slugify(value: str):
    return value.lower().replace('&', 'and').replace('/', ' ').replace('_', ' ').replace('-', ' ').strip().replace(' ', '-')
