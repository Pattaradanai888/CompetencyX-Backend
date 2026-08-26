"""Load, synchronise, and validate the authored Assessable Topic Sets.

A set is an authored cluster of one role's imported roadmap nodes, written so
a respondent can place themselves against it in a single question. The sets are
authored per role under ``data/content/topic_sets/<role-slug>.yaml`` rather than
derived from the imported graph, because the graph's own structure does not
carry the distinction the assessment needs (ADR-0003).

This module owns the entity and its synchronisation. The content that fills it
is drafted and reviewed separately: each set records where that review stands
in ``review.status``, and a set is synced and asked whichever status it holds
(ADR-0004).
"""

from pathlib import Path

import yaml

from assessments.models import AssessableTopicSet
from roadmaps.external_roadmap import build_external_roadmap_topics
from roadmaps.models import ExternalRoadmapNode, Role


TOPIC_SET_CONTENT_DIR = Path(__file__).resolve().parent.parent.parent / 'data' / 'content' / 'topic_sets'

SET_KEY_MAX_LENGTH = 128

# Mirrors the per-item review block of the question catalog. An agent may
# write ``draft``; only a person sets ``reviewed`` (ADR-0004).
VALID_TOPIC_SET_REVIEW_STATUSES = frozenset({'draft', 'reviewed'})


def build_set_key(role_slug: str, key: str) -> str:
    """The stable catalog key for a role-local authored key."""
    return f'{role_slug}--{key}'[:SET_KEY_MAX_LENGTH]


def load_assessable_topic_sets() -> list[dict]:
    """Every authored set, in file then authored order, with its key resolved.

    Returns ``[]`` when no role has been authored yet, which is the signal for
    every role to keep the items derived from its imported roadmap.
    """
    directory = TOPIC_SET_CONTENT_DIR
    if not directory.exists():
        return []

    sets: list[dict] = []
    seen_keys: set[str] = set()
    for path in sorted(directory.glob('*.yaml')):
        document = yaml.safe_load(path.read_text(encoding='utf-8')) or {}
        role_slug = document.get('role_slug')
        if not role_slug:
            msg = f'Topic set file "{path.name}" is missing "role_slug".'
            raise ValueError(msg)

        for display_order, entry in enumerate(document.get('sets') or [], start=1):
            sets.append(_normalise_set(entry, role_slug=role_slug, display_order=display_order, path=path, seen_keys=seen_keys))
    return sets


def _normalise_set(entry: dict, *, role_slug: str, display_order: int, path: Path, seen_keys: set[str]) -> dict:
    for field in ('key', 'title'):
        if not entry.get(field):
            msg = f'Topic set in "{path.name}" is missing "{field}".'
            raise ValueError(msg)

    set_key = build_set_key(role_slug, entry['key'])
    if set_key in seen_keys:
        msg = f'Topic set key "{set_key}" in "{path.name}" is defined more than once.'
        raise ValueError(msg)
    seen_keys.add(set_key)

    review = entry.get('review')
    review_status = review.get('status') if isinstance(review, dict) else None
    if review_status not in VALID_TOPIC_SET_REVIEW_STATUSES:
        msg = (
            f'Topic set "{set_key}" in "{path.name}" must declare review.status as one of '
            f'{sorted(VALID_TOPIC_SET_REVIEW_STATUSES)} (got: {review_status!r}).'
        )
        raise ValueError(msg)

    return {
        'set_key': set_key,
        'key': entry['key'],
        'role_slug': role_slug,
        'title': entry['title'],
        'title_th': entry.get('title_th', '') or '',
        # Read by the catalog report only: the sync publishes a set whichever
        # status it holds, so nothing downstream needs to know it (ADR-0004).
        'review_status': review_status,
        'node_slugs': list(entry.get('nodes') or []),
        'display_order': entry.get('display_order', display_order),
    }


def sync_assessable_topic_sets(*, stdout=None) -> dict[str, int]:
    """Upsert the authored sets and resolve the nodes they cover.

    Idempotent. A set that leaves the authored content is deactivated rather
    than deleted, so answers already recorded against it stay interpretable.
    Sets for a role that is not in the catalog are skipped with a warning
    instead of failing the sync.

    Authoring nothing at all is treated as "the content is not here" rather
    than "every set was retired": a deploy with the content directory missing
    would otherwise deactivate the whole catalog and drop every role back to
    its derived topics. Emptying the catalog deliberately is a database
    operation, not a sync.
    """
    authored = load_assessable_topic_sets()
    roles_by_slug = {role.slug: role for role in Role.objects.filter(slug__in={entry['role_slug'] for entry in authored})}

    synced: dict[str, int] = {}
    live_keys: list[str] = []
    for entry in authored:
        role = roles_by_slug.get(entry['role_slug'])
        if role is None:
            if stdout is not None:
                stdout.write(f'Skipping Assessable Topic Set "{entry["set_key"]}" for missing role "{entry["role_slug"]}".')
            continue

        topic_set, _created = AssessableTopicSet.objects.update_or_create(
            set_key=entry['set_key'],
            defaults={
                'role': role,
                'key': entry['key'],
                'title': entry['title'][:255],
                'title_th': entry['title_th'][:255],
                'node_slugs': entry['node_slugs'],
                'display_order': entry['display_order'],
                'is_active': True,
            },
        )
        topic_set.nodes.set(ExternalRoadmapNode.objects.filter(role=role, slug__in=entry['node_slugs']))
        live_keys.append(topic_set.set_key)
        synced[role.slug] = synced.get(role.slug, 0) + 1

    if live_keys:
        AssessableTopicSet.objects.exclude(set_key__in=live_keys).update(is_active=False)

    if stdout is not None:
        if not authored:
            stdout.write(f'No Assessable Topic Sets are authored in "{TOPIC_SET_CONTENT_DIR}"; every role keeps its derived topics.')
        else:
            stdout.write(f'Synced {sum(synced.values())} Assessable Topic Sets across {len(synced)} roles.')
    return synced


def select_assessable_topic_sets(role: Role) -> list[dict]:
    """The role's active sets as assessable units, in authored order.

    The shape matches what :func:`select_assessable_topics` returns for a role
    with no authored sets, so everything downstream -- the catalog, mastery, the
    readiness targets -- reads one kind of unit. Prerequisites and follow-ons are
    the union of those of the covered nodes, with the set's own nodes removed:
    a dependency inside a set is not a dependency of the set.
    """
    topic_sets = list(AssessableTopicSet.objects.filter(role=role, is_active=True).prefetch_related('nodes'))
    if not topic_sets:
        return []

    topics_by_slug = {topic['slug']: topic for topic in build_external_roadmap_topics(role)}
    set_key_by_title = {
        topics_by_slug[node.slug]['title']: topic_set.key
        for topic_set in topic_sets
        for node in topic_set.nodes.all()
        if node.slug in topics_by_slug
    }

    units = []
    for display_order, topic_set in enumerate(topic_sets, start=1):
        covered = [topics_by_slug[node.slug] for node in topic_set.nodes.all() if node.slug in topics_by_slug]
        covered_titles = {topic['title'] for topic in covered}
        follow_on_titles = _related_titles(covered, 'follow_on_titles', covered_titles)
        units.append(
            {
                # The stable catalog key, the same string the question id, the
                # answer keys, and a Held Topic mark are addressed by.
                'slug': topic_set.set_key,
                'question_id': topic_set.set_key,
                'title': topic_set.title,
                'title_th': topic_set.title_th,
                # Which imported nodes the set covers: prerequisite edges are
                # resolved at the node level and lifted back to units, so a set
                # whose nodes span several roadmap sections still lands after
                # everything it builds on (ADR-0003).
                'node_slugs': [node.slug for node in topic_set.nodes.all()],
                'display_order': topic_set.display_order or display_order,
                'prerequisite_titles': _related_titles(covered, 'prerequisite_titles', covered_titles),
                'follow_on_titles': follow_on_titles,
                # Counted in sets, not in node titles: the readiness target
                # rises per dependent unit, and a set covering a handful of
                # connected nodes would otherwise pin every target at the
                # maximum.
                'dependent_count': len({set_key_by_title[title] for title in follow_on_titles if title in set_key_by_title}),
            }
        )
    return units


def _related_titles(covered: list[dict], key: str, covered_titles: set[str]) -> list[str]:
    titles: list[str] = []
    for topic in covered:
        for title in topic[key]:
            if title not in covered_titles and title not in titles:
                titles.append(title)
    return titles


def build_topic_set_report() -> dict[str, object]:
    """What the authored catalog is missing, measured against the imported graph.

    Coverage of the graph is deliberately not a gate: a node belonging to no
    set stays Unassessed and is reported as a review backlog (ADR-0003).

    A set is "not reviewed" by its ``review.status`` alone, never by whether it
    has Thai wording: the wording is drafted by an agent and served while the
    human review of it runs in parallel (ADR-0004).
    """
    authored = load_assessable_topic_sets()
    node_slugs_by_role: dict[str, set[str]] = {}
    for role_slug, slug in ExternalRoadmapNode.objects.values_list('role__slug', 'slug'):
        node_slugs_by_role.setdefault(role_slug, set()).add(slug)

    covered_by_role: dict[str, set[str]] = {}
    unknown_node_slugs: list[tuple[str, list[str]]] = []
    sets_not_reviewed: list[str] = []
    roles_with_sets: set[str] = set()

    for entry in authored:
        role_slug = entry['role_slug']
        roles_with_sets.add(role_slug)
        known = node_slugs_by_role.get(role_slug, set())
        covered_by_role.setdefault(role_slug, set()).update(slug for slug in entry['node_slugs'] if slug in known)

        unknown = [slug for slug in entry['node_slugs'] if slug not in known]
        if unknown:
            unknown_node_slugs.append((entry['set_key'], unknown))
        if entry['review_status'] != 'reviewed':
            sets_not_reviewed.append(entry['set_key'])

    active_role_slugs = list(Role.objects.filter(is_active=True).order_by('slug').values_list('slug', flat=True))
    uncovered_counts = [
        (role_slug, len(node_slugs_by_role.get(role_slug, set()) - covered_by_role.get(role_slug, set())))
        for role_slug in active_role_slugs
        if node_slugs_by_role.get(role_slug)
    ]

    return {
        'set_count': len(authored),
        'roles_with_sets': sorted(roles_with_sets),
        'roles_without_sets': [slug for slug in active_role_slugs if slug not in roles_with_sets],
        'unknown_node_slugs': unknown_node_slugs,
        'sets_not_reviewed': sets_not_reviewed,
        'uncovered_node_counts': [(role_slug, count) for role_slug, count in uncovered_counts if count],
        'uncovered_node_total': sum(count for _role_slug, count in uncovered_counts),
    }
