import json
from pathlib import Path
from types import SimpleNamespace

import yaml

from roadmaps.content_review import VALID_REVIEW_STATUSES, invalid_review_status_message, read_review_status
from roadmaps.models import (
    ExternalRoadmapEdge,
    ExternalRoadmapNode,
    Question,
    QuestionOption,
    QuestionTopicSignal,
    RoadmapTopic,
    Role,
    TopicPrerequisite,
)
from roadmaps.questionnaire import CORE_ROLE_DIMENSIONS, ROLE_DIMENSIONS, SIGNAL_STRENGTH_WEIGHTS


BASE_DATA_DIR = Path(__file__).resolve().parent.parent / 'data'
CURATED_CONTENT_DIR = BASE_DATA_DIR / 'content'
QUESTION_BANK_DIR = CURATED_CONTENT_DIR / 'questions'
LEGACY_QUESTION_FILE = CURATED_CONTENT_DIR / 'questions.yaml'
UPSTREAM_SNAPSHOT_DIR = BASE_DATA_DIR / 'upstream' / 'roadmap_sh'
MIN_TIE_BREAK_ROLE_COUNT = 2
SUPPORTED_TRANSLATION_LANGUAGES = {'en', 'th'}
QUESTION_TRANSLATION_FIELDS = {'prompt', 'help_text'}


def load_curated_content(*, stdout=None):
    roles_data, topics_data, questions_data = load_curated_catalog()

    roles_by_slug = _sync_roles(roles_data['roles'])
    topics_by_key = _sync_topics(topics_data['topics'], roles_by_slug)
    _sync_questions(
        role_questions=questions_data['role_questions'],
        roles_by_slug=roles_by_slug,
        topics_by_key=topics_by_key,
    )

    if stdout is not None:
        stdout.write(
            f'Seeded {Role.objects.filter(is_active=True).count()} roles, '
            f'{RoadmapTopic.objects.filter(is_active=True).count()} topics, '
            f'{Question.objects.filter(is_active=True).count()} questions, and '
            f'{QuestionOption.objects.filter(question__is_active=True).count()} options.'
        )


def load_curated_catalog():
    roles_data = _load_yaml(CURATED_CONTENT_DIR / 'roles.yaml')
    topics_data = _load_yaml(CURATED_CONTENT_DIR / 'topics.yaml')
    questions_data = _load_question_bank()
    validate_curated_catalog(roles_data=roles_data, topics_data=topics_data, questions_data=questions_data)
    return roles_data, topics_data, questions_data


def _load_question_bank():
    if QUESTION_BANK_DIR.exists():
        question_fragments = sorted((QUESTION_BANK_DIR / 'role').rglob('*.yaml'))
        if not question_fragments:
            msg = f'No question fragments were found in "{QUESTION_BANK_DIR}".'
            raise FileNotFoundError(msg)

        questions_data = {'role_questions': [], 'skill_questions': []}
        for fragment_path in question_fragments:
            fragment = _load_yaml(fragment_path)
            if fragment is None:
                continue
            questions_data['role_questions'].extend(fragment.get('role_questions', []))
        return questions_data

    questions_data = _load_yaml(LEGACY_QUESTION_FILE)
    return {'role_questions': questions_data.get('role_questions', []), 'skill_questions': []}


def validate_curated_catalog(*, roles_data: dict, topics_data: dict, questions_data: dict):
    role_slugs = {role_seed['slug'] for role_seed in roles_data['roles']}
    question_codes: set[str] = set()

    for role_question in questions_data['role_questions']:
        _validate_role_question_seed(role_question, role_slugs=role_slugs, existing_codes=question_codes)

    _validate_role_question_bank(questions_data['role_questions'])


def import_roadmap_snapshot(*, snapshot_path: Path, role_slug: str, source='roadmap.sh', source_version=''):
    snapshot = json.loads(snapshot_path.read_text(encoding='utf-8'))
    role = Role.objects.get(slug=role_slug)

    topic_group_map = _extract_topic_group_map(snapshot)
    nodes = _extract_snapshot_nodes(snapshot)
    edges = _extract_snapshot_edges(snapshot)

    topics_by_external_id: dict[str, RoadmapTopic] = {}
    for index, node in enumerate(nodes, start=1):
        topic, _created = RoadmapTopic.objects.update_or_create(
            role=role,
            slug=node['slug'],
            defaults={
                'title': node['title'],
                'topic_group': topic_group_map.get(node['id'], ''),
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


EXTERNAL_ROADMAP_SOURCE = 'roadmap.sh'


def load_external_roadmap_manifest(*, snapshot_dir: Path = UPSTREAM_SNAPSHOT_DIR) -> list[dict]:
    """Manifest entries that describe a real role snapshot.

    Entries with ``role_slug: null`` (the hand-made loader-test sample) are skipped.
    """
    manifest_path = snapshot_dir / 'manifest.yaml'
    if not manifest_path.exists():
        return []

    manifest = _load_yaml(manifest_path)
    return [entry for entry in manifest.get('files', []) if entry.get('role_slug')]


def sync_external_roadmap_graphs(*, snapshot_dir: Path = UPSTREAM_SNAPSHOT_DIR, stdout=None) -> dict[str, int]:
    """Import every vendored roadmap.sh snapshot into the external master-data tables.

    Idempotent: re-running replaces each role's graph in place. Roles named in the
    manifest that are not in the curated catalog, and manifest files that are
    missing from disk, are skipped rather than raised, so a partial upstream
    directory never blocks content sync.
    """
    roles_by_slug = {role.slug: role for role in Role.objects.all()}
    imported = {}

    for entry in load_external_roadmap_manifest(snapshot_dir=snapshot_dir):
        role = roles_by_slug.get(entry['role_slug'])
        snapshot_path = snapshot_dir / entry['file']
        if role is None or not snapshot_path.exists():
            continue
        imported[role.slug] = import_external_roadmap_graph(
            snapshot_path=snapshot_path,
            role=role,
            source_url=entry.get('source_url') or '',
            retrieved_on=entry.get('retrieved'),
        )

    if stdout is not None:
        covered = len(imported)
        total_roles = Role.objects.filter(is_active=True).count()
        stdout.write(
            f'Imported {sum(imported.values())} external roadmap nodes for {covered} of {total_roles} roles '
            f'({ExternalRoadmapEdge.objects.count()} edges).'
        )
    return imported


def import_external_roadmap_graph(  # noqa: PLR0913 - snapshot identity plus its provenance fields
    *,
    snapshot_path: Path,
    role: Role,
    source: str = EXTERNAL_ROADMAP_SOURCE,
    source_url: str = '',
    source_version: str = '',
    retrieved_on=None,
) -> int:
    """Replace ``role``'s external roadmap graph with the contents of ``snapshot_path``.

    Returns the number of nodes imported.
    """
    snapshot = json.loads(snapshot_path.read_text(encoding='utf-8'))
    topic_group_map = _extract_topic_group_map(snapshot)
    nodes = _extract_snapshot_nodes(snapshot)
    edges = _extract_snapshot_edges(snapshot)
    nodes = _topologically_ordered_nodes(nodes, edges)

    ExternalRoadmapNode.objects.filter(role=role, source=source).delete()

    nodes_by_external_id: dict[str, ExternalRoadmapNode] = {}
    for display_order, node in enumerate(nodes, start=1):
        nodes_by_external_id[node['id']] = ExternalRoadmapNode(
            role=role,
            external_id=node['id'],
            slug=node['slug'][:200],
            title=node['title'][:255],
            topic_group=topic_group_map.get(node['id'], '')[:255],
            node_type=node['type'],
            display_order=display_order,
            source=source,
            source_url=source_url,
            source_version=source_version,
            retrieved_on=retrieved_on,
        )
    ExternalRoadmapNode.objects.bulk_create(list(nodes_by_external_id.values()))

    known_edges = [
        (nodes_by_external_id[edge['source']], nodes_by_external_id[edge['target']])
        for edge in edges
        if edge['source'] in nodes_by_external_id and edge['target'] in nodes_by_external_id
    ]

    ExternalRoadmapEdge.objects.bulk_create(
        [
            ExternalRoadmapEdge(role=role, source_node=source_node, target_node=target_node)
            for source_node, target_node in known_edges
        ],
        ignore_conflicts=True,
    )

    _assign_external_roadmap_parents(known_edges)
    return len(nodes_by_external_id)


def _topologically_ordered_nodes(nodes: list[dict], edges: list[dict]) -> list[dict]:
    """Order nodes so a prerequisite always precedes what it unlocks.

    Kahn's algorithm over the snapshot's own edges; ties and nodes in a cycle
    keep their original export order, which follows the roadmap's visual layout.
    The order is computed once at import time and stored as ``display_order``
    so every read serves the same sequence.
    """
    nodes_by_id = {node['id']: node for node in nodes}
    adjacency: dict[str, list[str]] = {node_id: [] for node_id in nodes_by_id}
    in_degree: dict[str, int] = dict.fromkeys(nodes_by_id, 0)

    for edge in edges:
        if edge['source'] in nodes_by_id and edge['target'] in nodes_by_id:
            adjacency[edge['source']].append(edge['target'])
            in_degree[edge['target']] += 1

    queue = [node_id for node_id in nodes_by_id if in_degree[node_id] == 0]
    ordered: list[dict] = []
    while queue:
        node_id = queue.pop(0)
        ordered.append(nodes_by_id[node_id])
        for neighbour in adjacency[node_id]:
            in_degree[neighbour] -= 1
            if in_degree[neighbour] == 0:
                queue.append(neighbour)

    if len(ordered) < len(nodes):
        placed = {node['id'] for node in ordered}
        ordered.extend(node for node in nodes if node['id'] not in placed)
    return ordered


def _assign_external_roadmap_parents(known_edges: list[tuple[ExternalRoadmapNode, ExternalRoadmapNode]]) -> None:
    """Nest subtopics under the topic that points at them.

    roadmap.sh models "subtopic of" as an ordinary edge from a topic to a
    subtopic, so an edge into a subtopic from a non-subtopic is a parent link.
    The first such edge wins, matching the upstream layout.
    """
    parented: list[ExternalRoadmapNode] = []
    for source_node, target_node in known_edges:
        if (
            target_node.node_type == ExternalRoadmapNode.NodeType.SUBTOPIC
            and source_node.node_type != ExternalRoadmapNode.NodeType.SUBTOPIC
            and target_node.parent_id is None
        ):
            target_node.parent = source_node
            parented.append(target_node)

    if parented:
        ExternalRoadmapNode.objects.bulk_update(parented, ['parent'])


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

    RoadmapTopic.objects.filter(
        role_id__in=[role.id for role in roles_by_slug.values()],
        external_source='',
    ).exclude(id__in=[topic.id for topic in topics_by_key.values()]).update(is_active=False)

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


def _signal_levels_to_weights(signal_levels: dict[str, str]) -> dict[str, float]:
    return {dimension_key: SIGNAL_STRENGTH_WEIGHTS[level] for dimension_key, level in signal_levels.items()}


def _sync_questions(*, role_questions: list[dict], roles_by_slug, topics_by_key):
    seed_codes = {question_seed['code'] for question_seed in role_questions}
    for question_seed in role_questions:
        question, _created = Question.objects.update_or_create(
            code=question_seed['code'],
            defaults={
                'stage': Question.Stage.ROLE,
                'question_type': question_seed['question_type'],
                'prompt': question_seed['prompt'],
                'help_text': question_seed.get('help_text', ''),
                'translations': question_seed.get('translations', {}),
                'role': None,
                'topic': None,
                'item_group': question_seed.get('item_group', Question.ItemGroup.CORE),
                'discriminates_between': question_seed.get('discriminates_between', []),
                'agree_dimension_signals': _signal_levels_to_weights(question_seed['agree_signals']),
                'disagree_dimension_signals': _signal_levels_to_weights(question_seed['disagree_signals']),
                'trait_positive_dimension': question_seed['construct'],
                'display_order': question_seed['display_order'],
                'is_active': True,
            },
        )
        question.options.all().delete()

    Question.objects.exclude(code__in=seed_codes).update(is_active=False)


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
    unsupported_fields = {'dimension_signals', 'mastery_value', 'role_signals', 'role_weights', 'translations'} & option_seed.keys()
    if not unsupported_fields:
        return

    fields = ', '.join(sorted(unsupported_fields))
    msg = f'Unsupported option seed field(s) for question "{question.code}": {fields}'
    raise ValueError(msg)


def _validate_translation_seed(translations: dict, *, item_label: str, allowed_fields: set[str]) -> None:
    if not translations:
        return
    if not isinstance(translations, dict):
        msg = f'{item_label} translations must be a mapping.'
        raise TypeError(msg)

    unsupported_languages = set(translations) - SUPPORTED_TRANSLATION_LANGUAGES
    if unsupported_languages:
        languages = ', '.join(sorted(unsupported_languages))
        msg = f'{item_label} has unsupported translation language(s): {languages}'
        raise ValueError(msg)

    for language, translated_fields in translations.items():
        if not isinstance(translated_fields, dict):
            msg = f'{item_label} "{language}" translation must be a mapping.'
            raise TypeError(msg)
        unsupported_fields = set(translated_fields) - allowed_fields
        if unsupported_fields:
            fields = ', '.join(sorted(unsupported_fields))
            msg = f'{item_label} has unsupported {language} translation field(s): {fields}'
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


LEGACY_QUESTION_FIELDS = {'agree_dimension_signals', 'disagree_dimension_signals', 'difficulty', 'discrimination_score', 'trait_positive_dimension'}


def _validate_role_question_seed(role_question: dict, *, role_slugs: set[str], existing_codes: set[str]) -> None:
    _validate_question_seed_uniqueness(role_question, existing_codes=existing_codes)
    code = role_question['code']
    legacy_fields = LEGACY_QUESTION_FIELDS & role_question.keys()
    if legacy_fields:
        msg = (
            f'Role question "{code}" uses pre-provenance field(s) {sorted(legacy_fields)}; '
            'use construct/agree_signals/disagree_signals levels instead (docs/scoring-methodology.md).'
        )
        raise ValueError(msg)
    _validate_translation_seed(
        role_question.get('translations', {}),
        item_label=f'Question "{code}"',
        allowed_fields=QUESTION_TRANSLATION_FIELDS,
    )
    item_group = role_question.get('item_group', Question.ItemGroup.CORE)
    if item_group not in {Question.ItemGroup.CORE, Question.ItemGroup.TIE_BREAK}:
        msg = f'Role question "{code}" must use item_group "core" or "tie_break".'
        raise ValueError(msg)
    if role_question.get('question_type') != Question.Type.LIKERT_5:
        msg = f'Role question "{code}" must use question_type "likert_5".'
        raise ValueError(msg)
    if role_question.get('options'):
        msg = f'Role question "{code}" must not define options.'
        raise ValueError(msg)

    agree_signals = _validate_signal_level_map(role_question, field_name='agree_signals')
    disagree_signals = _validate_signal_level_map(role_question, field_name='disagree_signals')
    _validate_question_provenance(role_question, agree_signals=agree_signals)
    if item_group == Question.ItemGroup.CORE:
        core_signal_dimensions = set(agree_signals) | set(disagree_signals)
        if not core_signal_dimensions & CORE_ROLE_DIMENSIONS:
            msg = f'Core role question "{code}" must signal at least one SWEBOK knowledge area.'
            raise ValueError(msg)

    _validate_role_question_pairing(role_question, item_group=item_group, role_slugs=role_slugs)


def _validate_signal_level_map(role_question: dict, *, field_name: str) -> dict:
    signals = role_question.get(field_name)
    if not isinstance(signals, dict) or not signals:
        msg = f'Role question "{role_question["code"]}" must define {field_name}.'
        raise ValueError(msg)
    unknown_dimensions = sorted(set(signals) - set(ROLE_DIMENSIONS))
    if unknown_dimensions:
        msg = f'Role question "{role_question["code"]}" has unknown {field_name}: {", ".join(unknown_dimensions)}'
        raise ValueError(msg)
    invalid_levels = sorted(key for key, level in signals.items() if level not in SIGNAL_STRENGTH_WEIGHTS)
    if invalid_levels:
        allowed = ', '.join(sorted(SIGNAL_STRENGTH_WEIGHTS))
        msg = f'Role question "{role_question["code"]}" has invalid {field_name} level(s) for: {", ".join(invalid_levels)} (allowed: {allowed})'
        raise ValueError(msg)
    return signals


def _validate_question_provenance(role_question: dict, *, agree_signals: dict) -> None:
    from roadmaps.weight_derivation import _load_known_source_anchors, _validate_sources  # noqa: PLC0415 - lazy: pulls in the YAML source anchors

    code = role_question['code']
    construct = role_question.get('construct')
    if construct not in agree_signals or agree_signals[construct] != 'primary':
        msg = f'Role question "{code}" construct must be an agree_signals dimension at level "primary" (got: {construct!r}).'
        raise ValueError(msg)
    if not str(role_question.get('rationale') or '').strip():
        msg = f'Role question "{code}" requires a non-empty rationale.'
        raise ValueError(msg)
    review_status = read_review_status(role_question)
    if review_status not in VALID_REVIEW_STATUSES:
        raise ValueError(invalid_review_status_message(f'Role question "{code}"', review_status))
    ka_codes, manifest_files = _load_known_source_anchors()
    source_errors: list[str] = []
    _validate_sources(f'question "{code}"', role_question.get('sources'), ka_codes=ka_codes, manifest_files=manifest_files, errors=source_errors)
    if source_errors:
        raise ValueError('; '.join(source_errors))


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
    if 'translations' in skill_question:
        msg = f'Unsupported skill question seed field(s) for question "{skill_question["code"]}": translations'
        raise ValueError(msg)
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
            question_dimensions = set(question.get('agree_signals', {})) | set(question.get('disagree_signals', {}))
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


def _extract_topic_group_map(snapshot: dict) -> dict[str, str]:
    nodes = snapshot.get('nodes', [])
    if isinstance(nodes, dict):
        nodes = list(nodes.values())

    sorted_nodes = sorted(nodes, key=lambda n: n.get('position', {}).get('y', 0))

    current_section = ''
    group_map: dict[str, str] = {}

    for node in sorted_nodes:
        node_id = str(node['id'])
        node_type = node.get('type', '')
        node_data = node.get('data') or {}

        if node_type == 'section':
            current_section = node_data.get('label') or node.get('label') or node.get('title') or ''
        elif node_type == 'title':
            if not current_section:
                current_section = node_data.get('label') or node.get('label') or node.get('title') or ''
        elif node_type == 'label':
            if not current_section:
                candidate = node_data.get('label') or ''
                if candidate:
                    current_section = candidate
        elif node_type in _SNAPSHOT_CONTENT_TYPES:
            group_map[node_id] = current_section

    return group_map


_SNAPSHOT_CONTENT_TYPES = {'topic', 'subtopic'}


def _extract_snapshot_nodes(snapshot: dict):
    nodes = snapshot.get('nodes', [])
    if isinstance(nodes, dict):
        nodes = list(nodes.values())
    normalized = []
    for node in nodes:
        node_type = node.get('type', '')
        if node_type not in _SNAPSHOT_CONTENT_TYPES:
            continue
        node_id = str(node['id'])
        node_data = node.get('data') or {}
        title = node.get('title') or node.get('label') or node_data.get('label') or node_id
        slug = node.get('slug') or _slugify(title)
        normalized.append(
            {
                'id': node_id,
                'title': title,
                'slug': slug,
                'type': node_type,
                'description': node.get('description', ''),
            }
        )
    return normalized


def _extract_snapshot_edges(snapshot: dict):
    edges = snapshot.get('edges', [])
    if isinstance(edges, dict):
        edges = list(edges.values())
    result = []
    for edge in edges:
        source = edge.get('source')
        target = edge.get('target')
        if not source or not target:
            continue
        result.append({
            'source': str(source),
            'target': str(target),
        })
    return result


def _slugify(value: str):
    return value.lower().replace('&', 'and').replace('/', ' ').replace('_', ' ').replace('-', ' ').strip().replace(' ', '-')
