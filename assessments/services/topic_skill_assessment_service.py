"""Build the Skill Assessment from each role's Assessable Topic Sets.

The previous instrument asked eleven general PSP/SDLC process statements that
were identical for every role, so nothing it produced could be readiness *for a
role* (ADR-0002). Items are generated per role from the Assessable Topic Sets
authored for it, and the rating a respondent gives a set is the mastery used to
gate prerequisites and to choose what to recommend next.

Authored sets are the only assessable unit. Nothing is read off the imported
roadmap graph, and there is no role-independent fallback any more: every
curated role has authored sets, a test guards that, and a role without them is
served an empty assessment rather than items about nothing in particular
(ADR-0005).

Every assessable unit is in exactly one of three states (ADR-0003): **Held**
(Self-placed Mastery at or above the threshold -- the respondent's own
statement, never a verdict), an **assessed gap** (rated below it), or
**Unassessed** (never asked and never marked). A unit nobody asked about is
never reported as absent capability.

Recommendation Stability is decided here too, by lookahead: the suggestions
have settled when no single further answer, at any rating, could change the
next topics (ADR-0005). It is a pure function of the answers, so the same rule
applies whether the answers are saved or merely proposed.
"""

from collections import defaultdict
from dataclasses import dataclass

from assessments.models import SkillAssessmentDimension, SkillAssessmentQuestion
from assessments.services.assessable_topic_set_service import select_assessable_topic_sets
from roadmaps.models import ExternalRoadmapEdge, ExternalRoadmapNode, Role


# A rating of 1..5 on the shared agreement scale maps onto 0.0..1.0 mastery.
SCALE_MIN = 1
SCALE_MAX = 5
SCALE_VALUES = tuple(range(SCALE_MIN, SCALE_MAX + 1))

PROMPT_TEMPLATE = 'I could work on "{topic}" in a real project without help.'
PROMPT_TEMPLATE_TH = 'ฉันทำงานเรื่อง "{topic}" ในโปรเจกต์จริงได้เองโดยไม่ต้องมีคนช่วย'

# The post-assessment screen shows the next few topics, not the whole graph:
# three to five is a place to start (ADR-0003). The same window is what
# Recommendation Stability watches (ADR-0005).
NEXT_TOPIC_COUNT = 5


def scale_value_to_mastery(value) -> float:
    """Map an agreement rating onto 0.0..1.0 mastery, clamped."""
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return 0.0
    normalized = (numeric - SCALE_MIN) / (SCALE_MAX - SCALE_MIN)
    return max(0.0, min(1.0, normalized))


def select_assessable_units(role: Role) -> list[dict]:
    """What this role is assessed on: its active Assessable Topic Sets.

    Authored sets are the only assessable unit (ADR-0003). A role with none
    returns ``[]`` and is served an empty assessment; every curated role has
    authored sets, and a test guards that.
    """
    return select_assessable_topic_sets(role)


def _unit_thai_title(unit: dict) -> str:
    """What names the unit in Thai: its Canonical Thai Wording, or nothing.

    An authored Assessable Topic Set is asked in its own Thai wording whatever
    its review status: review runs in parallel with use, and the respondent is
    not told the wording is draft (ADR-0004 decision 2). A set whose Thai text
    is still empty has no Thai name at all -- there is nothing to put in the
    sentence -- and returns ``''``. Every surface that renders Thai reads this
    one rule.
    """
    return unit['title_th']


def sync_topic_skill_assessment_catalog(*, stdout=None) -> dict[str, int]:
    """Regenerate the topic-anchored items for every role with authored sets.

    Idempotent. Items for a set that is no longer active are deactivated rather
    than deleted, so answers already recorded against them stay interpretable.
    """
    synced: dict[str, int] = {}
    live_question_ids: list[str] = []
    live_dimension_keys: list[str] = []

    for role in Role.objects.filter(is_active=True).order_by('slug'):
        topics = select_assessable_units(role)
        if not topics:
            continue

        for display_order, topic in enumerate(topics, start=1):
            # The set's own ``set_key``: the one string the question, the
            # answer, and a Held Topic mark are all addressed by.
            question_id = topic['question_id']
            thai_topic = _unit_thai_title(topic)
            dimension_key = question_id
            live_question_ids.append(question_id)
            live_dimension_keys.append(dimension_key)

            SkillAssessmentDimension.objects.update_or_create(
                dimension_key=dimension_key,
                defaults={
                    'role': role,
                    'label': topic['title'][:255],
                    'low_score_action': f'Start with "{topic["title"]}" on the {role.name} roadmap.',
                    # The axis label and its advice are read straight off this
                    # row, so a set with Canonical Thai Wording has to carry it
                    # here or a Thai respondent reads an English radar.
                    'translations': {
                        'th': {
                            'label': thai_topic[:255],
                            'low_score_action': f'เริ่มจาก "{thai_topic}" ใน roadmap ของ {role.name_th or role.name}',
                        },
                    } if thai_topic else {},
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

    SkillAssessmentQuestion.objects.exclude(question_id__in=live_question_ids).update(is_active=False)
    SkillAssessmentDimension.objects.exclude(dimension_key__in=live_dimension_keys).update(is_active=False)

    if stdout is not None:
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
HELD_STATEMENT_TEMPLATE_TH = 'คุณระบุว่าคุณทำงานเรื่อง "{title}" ได้แล้ว'

# Why a unit is suggested, in terms of the topics behind it. The four sentences
# are the two states crossed with whether prerequisites are outstanding; the
# language is data, so both languages read the same cascade.
SUGGESTION_REASON_TEMPLATES = {
    'en': {
        (STATE_ASSESSED_GAP, True): 'You rated "{title}" low, and it builds on {named}.',
        (STATE_ASSESSED_GAP, False): 'You rated "{title}" low, and it has no unmet prerequisites.',
        (STATE_UNASSESSED, True): 'The assessment has not asked about "{title}" yet; it builds on {named}.',
        (STATE_UNASSESSED, False): 'The assessment has not asked about "{title}" yet.',
    },
    'th': {
        (STATE_ASSESSED_GAP, True): 'คุณให้คะแนน "{title}" ค่อนข้างต่ำ และหัวข้อนี้ต่อยอดจาก {named}',
        (STATE_ASSESSED_GAP, False): 'คุณให้คะแนน "{title}" ค่อนข้างต่ำ และไม่มีหัวข้อที่ต้องเรียนก่อนค้างอยู่',
        (STATE_UNASSESSED, True): 'แบบประเมินยังไม่ได้ถามเรื่อง "{title}" และหัวข้อนี้ต่อยอดจาก {named}',
        (STATE_UNASSESSED, False): 'แบบประเมินยังไม่ได้ถามเรื่อง "{title}"',
    },
}


def build_unit_dependencies(role: Role, units: list[dict]) -> dict[str, set[str]]:
    """Which units each unit builds on, lifted from the node-level edges.

    An edge from a node in unit A to a node in unit B means B builds on A --
    unless the two nodes are the same unit, because a dependency inside a set
    is not a dependency *of* the set, or the edge is a parent nesting a
    subtopic rather than a prerequisite.
    """
    node_to_unit: dict[str, str] = {}
    for unit in units:
        for node_slug in unit['node_slugs']:
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


@dataclass(frozen=True)
class AssessmentGraph:
    """Everything about a role's assessment that does not depend on the answers.

    Read from the database once per request; every derivation below -- the
    states, the suggestion order, the readiness targets, and the stability
    lookahead -- is then a pure function of this graph and the answers, so a
    single response never re-reads the roadmap for each derived field.
    """

    units: list[dict]
    unit_by_slug: dict[str, dict]
    dependencies: dict[str, set[str]]
    layers: dict[str, int]
    targets: dict[str, float]

    @property
    def question_ids(self) -> list[str]:
        return [unit['question_id'] for unit in self.units]


def load_assessment_graph(role: Role) -> AssessmentGraph:
    units = select_assessable_units(role)
    dependencies = build_unit_dependencies(role, units)
    return AssessmentGraph(
        units=units,
        unit_by_slug={unit['slug']: unit for unit in units},
        dependencies=dependencies,
        layers=build_unit_layers(role, units, dependencies=dependencies),
        targets=build_topic_targets(role, units=units),
    )


def _unit_mastery(graph: AssessmentGraph, answers: dict[str, int]) -> dict[str, float]:
    """Self-placed Mastery per unit, from the answers alone (no database read)."""
    return {
        unit['slug']: scale_value_to_mastery(answers[unit['question_id']])
        for unit in graph.units
        if unit['question_id'] in answers
    }


def _suggestion_reason(title: str, state: str, unmet_prerequisite_titles: list[str], *, language: str) -> str:
    """Why this unit is suggested, naming up to two outstanding prerequisites.

    Both languages are carried on the entry rather than the wording being
    rebuilt from a title on the client, where the prerequisite names behind
    the reason are not available.
    """
    named = ', '.join(f'"{name}"' for name in unmet_prerequisite_titles[:2])
    template = SUGGESTION_REASON_TEMPLATES[language][(state, bool(unmet_prerequisite_titles))]
    return template.format(title=title, named=named)


def _derive_states(graph: AssessmentGraph, answers: dict[str, int], held_keys: frozenset[str]) -> list[dict]:
    """Every unit's state entry, in authored order."""
    mastery = _unit_mastery(graph, answers)
    states: list[dict] = []
    for unit in graph.units:
        unit_mastery = mastery.get(unit['slug'])
        marked = unit['slug'] in held_keys
        state = _unit_state(unit_mastery, marked_held=marked)
        # The Canonical Thai Wording travels with the entry: the page has no
        # other way to name the unit in the session's own language. A unit
        # with no Thai wording says so with ``None`` rather than passing
        # English off as Thai, so the page falls back deliberately.
        thai_title = _unit_thai_title(unit) or None
        entry = {
            'topic_slug': unit['slug'],
            'topic_title': unit['title'],
            'topic_title_th': thai_title,
            # Which imported roadmap nodes the set covers, so a page rendering
            # the roadmap can mark the nodes a held set stands for by slug
            # rather than guessing from titles.
            'node_slugs': list(unit['node_slugs']),
            'state': state,
            'mastery': unit_mastery,
            'display_order': unit['display_order'],
            'layer': graph.layers[unit['slug']],
        }
        if state == STATE_HELD:
            entry['statement'] = HELD_STATEMENT_TEMPLATE.format(title=unit['title'])
            entry['statement_th'] = HELD_STATEMENT_TEMPLATE_TH.format(title=thai_title) if thai_title else None
            # Undoing a mark is offered only where the mark is what holds the
            # unit. One held by a top self-rating -- whether or not it is also
            # marked -- stays held when the mark is taken back, and offering
            # that undo would be a control that does nothing.
            entry['held_by_mark'] = marked and _unit_state(unit_mastery, marked_held=False) != STATE_HELD
        states.append(entry)
    return states


def _rank_suggestions(states: list[dict]) -> list[dict]:
    """The suggestion order: prerequisite layer, then roadmap order, then mastery.

    Prerequisites always win. Self-placed Mastery only breaks ties between
    units at the same depth (ADR-0003). Assessed gaps are acted on before
    unassessed units, which follow in the same order.
    """
    assessed_gaps = [entry for entry in states if entry['state'] == STATE_ASSESSED_GAP]
    unassessed = [entry for entry in states if entry['state'] == STATE_UNASSESSED]
    assessed_gaps.sort(key=lambda entry: (entry['layer'], entry['display_order'], entry['mastery']))
    unassessed.sort(key=lambda entry: (entry['layer'], entry['display_order']))
    return [*assessed_gaps, *unassessed]


def top_suggestions(graph: AssessmentGraph, answers: dict[str, int], *, held_keys: frozenset[str] = frozenset()) -> list[str]:
    """The slugs of the next topics for these answers, in order."""
    return [entry['topic_slug'] for entry in _rank_suggestions(_derive_states(graph, answers, held_keys))[:NEXT_TOPIC_COUNT]]


def is_recommendation_settled(graph: AssessmentGraph, answers: dict[str, int], *, held_keys: frozenset[str] = frozenset()) -> bool:
    """Recommendation Stability: no further single answer could change the next topics.

    Every unanswered, unmarked unit is tried at every rating on the scale; if
    any of them would move the next topics, the assessment has more to learn
    and is not settled. The rule reads only the answers it is given, so it
    holds for answers a client proposes as much as for answers it has saved
    (ADR-0005). A catalog with nothing left to ask is settled vacuously.
    """
    baseline = top_suggestions(graph, answers, held_keys=held_keys)
    for unit in graph.units:
        question_id = unit['question_id']
        if question_id in answers or unit['slug'] in held_keys:
            continue
        for rating in SCALE_VALUES:
            if top_suggestions(graph, {**answers, question_id: rating}, held_keys=held_keys) != baseline:
                return False
    return True


def build_assessment_summary(
    role: Role,
    answers: dict[str, int],
    *,
    held_keys: frozenset[str] = frozenset(),
    graph: AssessmentGraph | None = None,
) -> dict:
    """Everything the three states and the suggestion order are derived from.

    Pass ``graph`` when the caller already loaded it, so one response reads
    the roadmap once.
    """
    if graph is None:
        graph = load_assessment_graph(role)
    states = _derive_states(graph, answers, held_keys)
    by_slug = {entry['topic_slug']: entry for entry in states}

    # A unit's prerequisites count as met only when the unit behind them is
    # held; naming a held prerequisite as outstanding would be a false reason.
    unmet: dict[str, list[str]] = {}
    unmet_th: dict[str, list[str]] = {}
    for unit in graph.units:
        prerequisite_units = sorted(
            graph.dependencies.get(unit['slug'], ()),
            key=lambda slug: (graph.unit_by_slug[slug]['display_order'], slug),
        )
        outstanding = [prereq_slug for prereq_slug in prerequisite_units if by_slug[prereq_slug]['state'] != STATE_HELD]
        unmet[unit['slug']] = [graph.unit_by_slug[prereq_slug]['title'] for prereq_slug in outstanding]
        # A prerequisite with no Thai wording is still named, in English,
        # rather than the sentence losing the topic it points at.
        unmet_th[unit['slug']] = [
            _unit_thai_title(graph.unit_by_slug[prereq_slug]) or graph.unit_by_slug[prereq_slug]['title'] for prereq_slug in outstanding
        ]

    recommendations = []
    for entry in _rank_suggestions(states):
        slug, state, thai_title = entry['topic_slug'], entry['state'], entry['topic_title_th']
        recommendations.append(
            {
                'topic_slug': slug,
                'topic_title': entry['topic_title'],
                'topic_title_th': thai_title,
                'node_slugs': entry['node_slugs'],
                'state': state,
                'mastery': entry['mastery'],
                'reason': _suggestion_reason(entry['topic_title'], state, unmet[slug], language='en'),
                'reason_th': _suggestion_reason(thai_title, state, unmet_th[slug], language='th') if thai_title else None,
            },
        )

    return {'units': graph.units, 'states': states, 'recommendations': recommendations, 'targets': graph.targets}


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
        topic['slug']: min(TOPIC_TARGET_MAX, TOPIC_TARGET_BASE + TOPIC_TARGET_PER_DEPENDENT * topic['dependent_count'])
        for topic in units
    }


def build_readiness_summary(
    role: Role,
    answers: dict[str, int],
    *,
    held_keys: frozenset[str] = frozenset(),
    summary: dict | None = None,
) -> dict[str, object]:
    """As-is against the role's own target, over the assessed units only.

    An unasked remainder is no evidence either way, so it must not deflate the
    figure: readiness is the mean mastery of what was actually assessed, and
    the response says how many units that is.
    """
    if summary is None:
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
