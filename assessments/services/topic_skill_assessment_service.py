"""Build the Skill Assessment from each role's own roadmap topics.

The previous instrument asked eleven general PSP/SDLC process statements that
were identical for every role, so nothing it produced could be readiness *for a
role* (ADR-0002). Items are now generated per role from the top-level topics of
that role's imported roadmap, and the rating a respondent gives a topic is the
mastery used to gate prerequisites and to choose what to recommend next.

Roles without an imported roadmap keep the role-independent fallback items, so
the assessment never comes back empty.

Every assessable unit is in exactly one of three states (ADR-0003): **Held**
(Self-placed Mastery at or above the threshold -- the respondent's own
statement, never a verdict), an **assessed gap** (rated below it), or
**Unassessed** (never asked and never marked). A unit nobody asked about is
never reported as absent capability.
"""

from collections import defaultdict

from assessments.models import SkillAssessmentDimension, SkillAssessmentQuestion
from assessments.services.assessable_topic_set_service import build_set_key, select_assessable_topic_sets
from roadmaps.external_roadmap import build_external_roadmap_topics
from roadmaps.models import ExternalRoadmapEdge, ExternalRoadmapNode, Role


# Top-level topic counts run from 6 to 59 per role. Asking every one of them is
# not a questionnaire anybody finishes, so the sequence is cut here; topics come
# in prerequisite order, so the cut keeps the earliest ones.
MAX_TOPIC_QUESTIONS_PER_ROLE = 12

# A rating of 1..5 on the shared agreement scale maps onto 0.0..1.0 mastery.
SCALE_MIN = 1
SCALE_MAX = 5

PROMPT_TEMPLATE = 'I could work on "{topic}" in a real project without help.'
PROMPT_TEMPLATE_TH = 'ฉันทำงานเรื่อง "{topic}" ในโปรเจกต์จริงได้เองโดยไม่ต้องมีคนช่วย'

TOPIC_DIMENSION_TRACK = SkillAssessmentDimension.Track.SDLC


def scale_value_to_mastery(value) -> float:
    """Map an agreement rating onto 0.0..1.0 mastery, clamped."""
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return 0.0
    normalized = (numeric - SCALE_MIN) / (SCALE_MAX - SCALE_MIN)
    return max(0.0, min(1.0, normalized))


# Roadmap graphs carry navigational nodes addressed to the reader rather than
# named skills -- "Pick a Language", "Learn SQL", "Visit the DevOps Roadmap".
# They belong on the roadmap, but "I could work on Pick a Language in a real
# project" is not a question anybody can answer, so they are not assessed.
INSTRUCTION_TITLE_PREFIXES = ('pick ', 'learn ', 'visit ', 'choose ', 'read ', 'explore ', 'go to ')


def is_assessable_topic_title(title: str) -> bool:
    return not title.strip().lower().startswith(INSTRUCTION_TITLE_PREFIXES)


def select_assessable_topics(role: Role) -> list[dict]:
    """The role's top-level roadmap topics, in prerequisite order, capped.

    Navigational nodes are filtered out here rather than at import, so the
    roadmap still shows them as steps while the assessment does not ask about
    them. Returns ``[]`` for a role with no imported roadmap, which is the
    signal to fall back to the role-independent items.
    """
    topics = build_external_roadmap_topics(role)
    top_level = [
        topic
        for topic in topics
        if topic['node_type'] == 'topic' and is_assessable_topic_title(topic['title'])
    ]
    return [
        {
            **topic,
            'node_slugs': [topic['slug']],
            'question_id': build_set_key(role.slug, topic['slug']),
        }
        for topic in top_level[:MAX_TOPIC_QUESTIONS_PER_ROLE]
    ]


def select_assessable_units(role: Role) -> list[dict]:
    """What this role is assessed on: its authored sets, or its derived topics.

    Authored Assessable Topic Sets are the unit ADR-0003 settled on, and they
    win wherever they exist. A role whose sets have not been authored yet keeps
    the items derived from its imported roadmap, so no role loses its
    topic-anchored assessment while the content is being written.
    """
    return select_assessable_topic_sets(role) or select_assessable_topics(role)


def build_question_id(role: Role, topic_slug: str) -> str:
    """The catalog key for a role's item.

    Composed by :func:`build_set_key`, so an item generated from an Assessable
    Topic Set is keyed by that set's own ``set_key`` rather than by a second
    string that happens to match it.
    """
    return build_set_key(role.slug, topic_slug)


def sync_topic_skill_assessment_catalog(*, stdout=None) -> dict[str, int]:
    """Regenerate the topic-anchored items for every role that has a roadmap.

    Idempotent. Items for a role whose roadmap no longer covers a topic are
    deactivated rather than deleted, so answers already recorded against them
    stay interpretable.
    """
    synced: dict[str, int] = {}
    live_question_ids: list[str] = []
    live_dimension_keys: list[str] = []

    for role in Role.objects.filter(is_active=True).order_by('slug'):
        topics = select_assessable_units(role)
        if not topics:
            continue

        for display_order, topic in enumerate(topics, start=1):
            # A set's slug already is its global catalog key; a derived topic's
            # is role-local and carries the role slug here to become one.
            question_id = topic.get('question_id') or build_question_id(role, topic['slug'])
            # An authored set carries its own Canonical Thai Wording and is
            # asked in it whatever its review.status: review runs in parallel
            # with use, and the respondent is not told the wording is draft
            # (ADR-0004 decision 2). Only a set with no Thai text at all gets
            # no Thai prompt -- there is nothing to put in the sentence. A
            # derived topic has no authored wording either way, so its own
            # title stands in as it did before.
            thai_topic = topic['title_th'] if 'title_th' in topic else topic['title']
            dimension_key = question_id
            live_question_ids.append(question_id)
            live_dimension_keys.append(dimension_key)

            SkillAssessmentDimension.objects.update_or_create(
                dimension_key=dimension_key,
                defaults={
                    'role': role,
                    'label': topic['title'][:255],
                    'track': TOPIC_DIMENSION_TRACK,
                    'low_score_action': f'Start with "{topic["title"]}" on the {role.name} roadmap.',
                    'translations': {},
                    'display_order': display_order,
                    'is_active': True,
                },
            )
            SkillAssessmentQuestion.objects.update_or_create(
                question_id=question_id,
                defaults={
                    'role': role,
                    'topic_slug': topic['slug'][:200],
                    'topic_title': topic['title'][:255],
                    'prompt': PROMPT_TEMPLATE.format(topic=topic['title']),
                    'translations': {'th': {'prompt': PROMPT_TEMPLATE_TH.format(topic=thai_topic)}} if thai_topic else {},
                    'dimension_key': dimension_key,
                    'display_order': display_order,
                    'is_active': True,
                },
            )
        synced[role.slug] = len(topics)

    stale_questions = SkillAssessmentQuestion.objects.filter(role__isnull=False).exclude(question_id__in=live_question_ids)
    stale_questions.update(is_active=False)
    SkillAssessmentDimension.objects.filter(role__isnull=False).exclude(dimension_key__in=live_dimension_keys).update(is_active=False)

    if stdout is not None:
        # No cap is reported: the cap applies to topics derived from a roadmap,
        # not to a role's authored sets.
        stdout.write(f'Synced topic Skill Assessment items for {len(synced)} roles ({sum(synced.values())} questions).')
    return synced


def get_topic_mastery(role: Role, answers: dict[str, int]) -> dict[str, float]:
    """Per-topic mastery for a role, derived from that role's answered items.

    Only answered items appear: a unit the assessment never asked about has no
    mastery at all, which is what keeps Unassessed distinct from a Self-placed
    Mastery of 0.0 (ADR-0003).
    """
    questions = SkillAssessmentQuestion.objects.filter(role=role, is_active=True).values('question_id', 'topic_slug')
    mastery = {}
    for question in questions:
        if question['question_id'] in answers:
            mastery[question['topic_slug']] = scale_value_to_mastery(answers[question['question_id']])
    return mastery


# A topic at or above this rating is treated as already held, matching the
# threshold the recommendation engine uses for curated topics.
TOPIC_MASTERY_THRESHOLD = 0.7

STATE_HELD = 'held'
STATE_ASSESSED_GAP = 'assessed_gap'
STATE_UNASSESSED = 'unassessed'


def _unit_state(mastery: float | None, *, marked_held: bool) -> str:
    """Which of the three states a unit is in, from the evidence that exists.

    A Held Topic mark and a self-rating at or above the threshold are the same
    statement, so they land in the same state: one notion of "already held",
    not two competing ones.
    """
    if marked_held:
        return STATE_HELD
    if mastery is None:
        return STATE_UNASSESSED
    if mastery >= TOPIC_MASTERY_THRESHOLD:
        return STATE_HELD
    return STATE_ASSESSED_GAP


HELD_STATEMENT_TEMPLATE = 'You said you can already work on "{title}".'


def build_unit_dependencies(role: Role, units: list[dict]) -> dict[str, set[str]]:
    """Which units each unit builds on, lifted from the node-level edges.

    An edge from a node in unit A to a node in unit B means B builds on A --
    unless the two nodes are the same unit, because a dependency inside a set
    is not a dependency *of* the set, or the edge is a parent nesting a
    subtopic rather than a prerequisite.
    """
    node_to_unit: dict[str, str] = {}
    for unit in units:
        for node_slug in unit.get('node_slugs') or [unit['slug']]:
            node_to_unit[node_slug] = unit['slug']

    nodes = ExternalRoadmapNode.objects.filter(role=role).only('id', 'slug', 'parent_id')
    slug_by_id = {node.id: node.slug for node in nodes}
    parent_id_by_id = {node.id: node.parent_id for node in nodes}

    dependencies: dict[str, set[str]] = defaultdict(set)
    for source_id, target_id in ExternalRoadmapEdge.objects.filter(role=role).values_list('source_node_id', 'target_node_id'):
        source_unit = node_to_unit.get(slug_by_id.get(source_id, ''))
        target_unit = node_to_unit.get(slug_by_id.get(target_id, ''))
        if not source_unit or not target_unit or source_unit == target_unit:
            continue
        if parent_id_by_id.get(target_id) == source_id:
            continue
        dependencies[target_unit].add(source_unit)
    return dependencies


def build_unit_layers(role: Role, units: list[dict], *, dependencies: dict[str, set[str]] | None = None) -> dict[str, int]:
    """Prerequisite depth of each unit: how much it builds on.

    The depth is the longest prerequisite chain below the unit. 64% of
    imported nodes appear in no edge at all; those land at depth 0, where the
    roadmap's own order carries them. Cycles in imported graphs are tolerated:
    a back-edge does not add depth. Pass ``dependencies`` when the caller
    already built the unit graph, so the tables are read once.
    """
    if dependencies is None:
        dependencies = build_unit_dependencies(role, units)
    layers: dict[str, int] = {}
    visiting: set[str] = set()

    def layer_of(unit_slug: str) -> int:
        if unit_slug in layers:
            return layers[unit_slug]
        if unit_slug in visiting:  # cycle: this back-edge adds no depth
            return 0
        visiting.add(unit_slug)
        depth = max((layer_of(dep) for dep in dependencies.get(unit_slug, ())), default=-1) + 1
        visiting.discard(unit_slug)
        layers[unit_slug] = depth
        return depth

    for unit in units:
        layer_of(unit['slug'])
    return layers


def _suggestion_reason(unit: dict, state: str, unmet_prerequisite_titles: list[str]) -> str:
    """Why this unit is suggested, in terms of the topics behind it."""
    title = unit['title']
    if state == STATE_ASSESSED_GAP:
        if unmet_prerequisite_titles:
            named = ', '.join(f'"{name}"' for name in unmet_prerequisite_titles[:2])
            return f'You rated "{title}" low, and it builds on {named}.'
        return f'You rated "{title}" low, and it has no unmet prerequisites.'
    if unmet_prerequisite_titles:
        named = ', '.join(f'"{name}"' for name in unmet_prerequisite_titles[:2])
        return f'The assessment has not asked about "{title}" yet; it builds on {named}.'
    return f'The assessment has not asked about "{title}" yet.'


def build_assessment_summary(role: Role, answers: dict[str, int], *, held_keys: frozenset[str] = frozenset()) -> dict:
    """Everything the three states and the suggestion order are derived from.

    Computed once so a single response never re-reads the roadmap graph for
    each derived field.
    """
    units = select_assessable_units(role)
    mastery = get_topic_mastery(role, answers)
    unit_by_slug = {unit['slug']: unit for unit in units}
    dependencies = build_unit_dependencies(role, units)
    layers = build_unit_layers(role, units, dependencies=dependencies)

    states: list[dict] = []
    by_slug: dict[str, dict] = {}
    for unit in units:
        unit_mastery = mastery.get(unit['slug'])
        state = _unit_state(unit_mastery, marked_held=unit['slug'] in held_keys)
        entry = {
            'topic_slug': unit['slug'],
            'topic_title': unit['title'],
            'state': state,
            'mastery': unit_mastery,
            'display_order': unit['display_order'],
            'layer': layers[unit['slug']],
        }
        if state == STATE_HELD:
            entry['statement'] = HELD_STATEMENT_TEMPLATE.format(title=unit['title'])
        states.append(entry)
        by_slug[unit['slug']] = entry

    # A unit's prerequisites count as met only when the unit behind them is
    # held; naming a held prerequisite as outstanding would be a false reason.
    unmet: dict[str, list[str]] = {}
    for unit in units:
        prerequisite_units = sorted(
            dependencies.get(unit['slug'], ()),
            key=lambda slug: (unit_by_slug[slug]['display_order'], slug),
        )
        unmet[unit['slug']] = [
            unit_by_slug[prereq_slug]['title']
            for prereq_slug in prerequisite_units
            if by_slug[prereq_slug]['state'] != STATE_HELD
        ]

    assessed_gaps = [entry for entry in states if entry['state'] == STATE_ASSESSED_GAP]
    unassessed = [entry for entry in states if entry['state'] == STATE_UNASSESSED]

    # Prerequisite layer first, then roadmap order; Self-placed Mastery only
    # breaks ties between units at the same depth (ADR-0003). Assessed gaps are
    # acted on before unassessed units, which follow in the same order.
    assessed_gaps.sort(key=lambda entry: (entry['layer'], entry['display_order'], entry['mastery']))
    unassessed.sort(key=lambda entry: (entry['layer'], entry['display_order']))

    recommendations = []
    for entry in (*assessed_gaps, *unassessed):
        unit = unit_by_slug[entry['topic_slug']]
        recommendations.append(
            {
                'topic_slug': entry['topic_slug'],
                'topic_title': entry['topic_title'],
                'state': entry['state'],
                'mastery': entry['mastery'],
                'reason': _suggestion_reason(unit, entry['state'], unmet[entry['topic_slug']]),
            },
        )

    return {'units': units, 'states': states, 'recommendations': recommendations, 'targets': build_topic_targets(role, units=units)}


# A topic that other topics build on has to be solid before the roadmap makes
# sense; a terminal topic can sit lower without blocking anything. The target
# therefore rises with how many topics depend on it, which is a property of the
# role's own roadmap rather than a number chosen for all roles at once.
TOPIC_TARGET_BASE = 0.6
TOPIC_TARGET_PER_DEPENDENT = 0.1
TOPIC_TARGET_MAX = 1.0


def build_topic_targets(role: Role, *, units: list[dict] | None = None) -> dict[str, float]:
    """The mastery each assessed unit should reach for this role.

    An Assessable Topic Set counts its dependents in sets rather than in node
    titles: a set covering a handful of connected nodes inherits dozens of
    follow-on titles, which would pin every target at the maximum and say
    nothing about which unit the roadmap actually leans on.
    """
    if units is None:
        units = select_assessable_units(role)
    return {
        topic['slug']: min(
            TOPIC_TARGET_MAX,
            TOPIC_TARGET_BASE + TOPIC_TARGET_PER_DEPENDENT * topic.get('dependent_count', len(topic['follow_on_titles'])),
        )
        for topic in units
    }


def build_readiness_summary(role: Role, answers: dict[str, int], *, held_keys: frozenset[str] = frozenset()) -> dict[str, object]:
    """As-is against the role's own target, over the assessed units only.

    An unasked remainder is no evidence either way, so it must not deflate the
    figure: readiness is the mean mastery of what was actually assessed, and
    the response says how many units that is.
    """
    summary = build_assessment_summary(role, answers, held_keys=held_keys)
    # A Held Topic mark is a statement, not a rating: it holds the set without
    # producing a Self-placed Mastery, so readiness counts only units that
    # were actually rated.
    assessed = [entry for entry in summary['states'] if entry['mastery'] is not None]
    targets = summary['targets']
    if not assessed:
        return {'targets': targets, 'overall_target': 0.0, 'overall_mastery': 0.0, 'assessed_count': 0}

    assessed_slugs = [entry['topic_slug'] for entry in assessed]
    return {
        'targets': targets,
        'overall_target': sum(targets[slug] for slug in assessed_slugs) / len(assessed_slugs),
        'overall_mastery': sum(entry['mastery'] for entry in assessed) / len(assessed),
        'assessed_count': len(assessed),
    }
