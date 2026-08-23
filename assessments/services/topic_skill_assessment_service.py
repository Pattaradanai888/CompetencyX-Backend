"""Build the Skill Assessment from each role's own roadmap topics.

The previous instrument asked eleven general PSP/SDLC process statements that
were identical for every role, so nothing it produced could be readiness *for a
role* (ADR-0002). Items are now generated per role from the top-level topics of
that role's imported roadmap, and the rating a respondent gives a topic is the
mastery used to gate prerequisites and to choose what to recommend next.

Roles without an imported roadmap keep the role-independent fallback items, so
the assessment never comes back empty.
"""

from assessments.models import SkillAssessmentDimension, SkillAssessmentQuestion
from assessments.services.assessable_topic_set_service import build_set_key, select_assessable_topic_sets
from roadmaps.external_roadmap import build_external_roadmap_topics
from roadmaps.models import Role


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
    return top_level[:MAX_TOPIC_QUESTIONS_PER_ROLE]


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
            question_id = build_question_id(role, topic['slug'])
            # An authored set carries its own Canonical Thai wording, and a set
            # without reviewed wording gets no Thai prompt: English inside a
            # Thai sentence would read as reviewed when it is not. A derived
            # topic has no authored wording either way, so its own title stands
            # in as it did before.
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
    """Per-topic mastery for a role, derived from that role's answered items."""
    questions = SkillAssessmentQuestion.objects.filter(role=role, is_active=True).values('question_id', 'topic_slug')
    mastery = {}
    for question in questions:
        if question['question_id'] in answers:
            mastery[question['topic_slug']] = scale_value_to_mastery(answers[question['question_id']])
    return mastery


# A topic at or above this rating is treated as already held, matching the
# threshold the recommendation engine uses for curated topics.
TOPIC_MASTERY_THRESHOLD = 0.7


def build_topic_recommendations(role: Role, answers: dict[str, int]) -> list[dict]:
    """Which topics this respondent should learn next, weakest first.

    Ordered by the rating the respondent gave, then by the roadmap's own
    prerequisite order, so two people on the same role with different answers
    get different topics. Topics rated at or above the threshold are treated as
    already held and drop out.
    """
    assessed = {topic['slug']: topic for topic in select_assessable_units(role)}
    if not assessed:
        return []

    mastery = get_topic_mastery(role, answers)
    pending = [
        {
            'topic_slug': slug,
            'topic_title': topic['title'],
            'mastery': mastery.get(slug, 0.0),
            'display_order': topic['display_order'],
            'prerequisite_titles': topic['prerequisite_titles'],
        }
        for slug, topic in assessed.items()
        if mastery.get(slug, 0.0) < TOPIC_MASTERY_THRESHOLD
    ]
    pending.sort(key=lambda item: (item['mastery'], item['display_order']))

    for item in pending:
        if item['prerequisite_titles']:
            item['reason'] = (
                f'You rated "{item["topic_title"]}" low, and it builds on '
                f'{", ".join(item["prerequisite_titles"][:2])}.'
            )
        else:
            item['reason'] = f'You rated "{item["topic_title"]}" low, and it has no unmet prerequisites.'
        del item['display_order']
    return pending


# A topic that other topics build on has to be solid before the roadmap makes
# sense; a terminal topic can sit lower without blocking anything. The target
# therefore rises with how many topics depend on it, which is a property of the
# role's own roadmap rather than a number chosen for all roles at once.
TOPIC_TARGET_BASE = 0.6
TOPIC_TARGET_PER_DEPENDENT = 0.1
TOPIC_TARGET_MAX = 1.0


def build_topic_targets(role: Role) -> dict[str, float]:
    """The mastery each assessed unit should reach for this role.

    An Assessable Topic Set counts its dependents in sets rather than in node
    titles: a set covering a handful of connected nodes inherits dozens of
    follow-on titles, which would pin every target at the maximum and say
    nothing about which unit the roadmap actually leans on.
    """
    return {
        topic['slug']: min(
            TOPIC_TARGET_MAX,
            TOPIC_TARGET_BASE + TOPIC_TARGET_PER_DEPENDENT * topic.get('dependent_count', len(topic['follow_on_titles'])),
        )
        for topic in select_assessable_units(role)
    }


def build_readiness_summary(role: Role, answers: dict[str, int]) -> dict[str, object]:
    """As-is against the role's own target, per topic and overall.

    Replaces comparing every respondent of every role to one constant.
    """
    targets = build_topic_targets(role)
    if not targets:
        return {'targets': {}, 'overall_target': 0.0, 'overall_mastery': 0.0}

    mastery = get_topic_mastery(role, answers)
    return {
        'targets': targets,
        'overall_target': sum(targets.values()) / len(targets),
        'overall_mastery': sum(mastery.get(slug, 0.0) for slug in targets) / len(targets),
    }
