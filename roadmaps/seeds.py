import json
from pathlib import Path

import yaml

from roadmaps.models import (
    Question,
    QuestionOption,
    QuestionRoleSignal,
    QuestionTopicSignal,
    RoadmapTopic,
    Role,
    TopicPrerequisite,
)


BASE_DATA_DIR = Path(__file__).resolve().parent.parent / 'data'
CURATED_CONTENT_DIR = BASE_DATA_DIR / 'content'
UPSTREAM_SNAPSHOT_DIR = BASE_DATA_DIR / 'upstream' / 'roadmap_sh'


def seed_mvp_content(*, stdout=None):
    load_curated_content(stdout=stdout)


def load_curated_content(*, stdout=None):
    roles_data = _load_yaml(CURATED_CONTENT_DIR / 'roles.yaml')
    topics_data = _load_yaml(CURATED_CONTENT_DIR / 'topics.yaml')
    questions_data = _load_yaml(CURATED_CONTENT_DIR / 'questions.yaml')

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
                'is_active': True,
            },
        )
        roles_by_slug[role.slug] = role
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
    for question_seed in role_questions:
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
                'display_order': question_seed['display_order'],
                'is_active': True,
            },
        )
        _sync_question_options(question, question_seed['options'], roles_by_slug=roles_by_slug, topics_by_key=topics_by_key)

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
                'display_order': question_seed['display_order'],
                'is_active': True,
            },
        )
        _sync_question_options(question, question_seed['options'], roles_by_slug=roles_by_slug, topics_by_key=topics_by_key)


def _sync_question_options(question: Question, option_seeds: list[dict], *, roles_by_slug, topics_by_key):
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
        _sync_role_signals(option, option_seed.get('role_signals', {}), roles_by_slug)
        _sync_topic_signals(
            option,
            option_seed.get('topic_signals', []),
            question=question,
            topics_by_key=topics_by_key,
        )
    if existing_keys - seed_keys:
        question.options.exclude(key__in=seed_keys).delete()


def _validate_option_seed(option_seed: dict, *, question: Question) -> None:
    unsupported_fields = {'mastery_value', 'role_weights'} & option_seed.keys()
    if not unsupported_fields:
        return

    fields = ', '.join(sorted(unsupported_fields))
    msg = f'Unsupported option seed field(s) for question "{question.code}": {fields}'
    raise ValueError(msg)


def _sync_role_signals(option: QuestionOption, role_signals: dict[str, float], roles_by_slug: dict[str, Role]):
    QuestionRoleSignal.objects.filter(question_option=option).exclude(role__slug__in=role_signals.keys()).delete()
    for role_slug, weight in role_signals.items():
        QuestionRoleSignal.objects.update_or_create(
            question_option=option,
            role=roles_by_slug[role_slug],
            defaults={'weight': float(weight)},
        )


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
    return (
        value.lower()
        .replace('&', 'and')
        .replace('/', ' ')
        .replace('_', ' ')
        .replace('-', ' ')
        .strip()
        .replace(' ', '-')
    )
