from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from assessments.models import (
    AssessmentSession,
    SkillAssessmentAnswer,
    SkillAssessmentDimension,
    SkillAssessmentQuestion,
    SkillAssessmentRoleGuidance,
)

from .held_topic_service import get_held_topic_keys
from .topic_skill_assessment_service import (
    build_assessment_summary,
    build_readiness_summary,
    get_topic_mastery,
)


# The post-assessment screen shows the next few topics to learn, not the whole
# graph: three to five is a place to start (ADR-0003).
NEXT_TOPIC_COUNT = 5

# Recommendation Stability: at least this many answered items before the
# assessment may stop, however settled the suggestions look, and never more
# than the ceiling. A catalog smaller than the floor is asked to the end.
SKILL_ASSESSMENT_FLOOR = 12
SKILL_ASSESSMENT_CEILING = 20


def _stop_bounds(total_questions: int) -> tuple[int, int]:
    return min(SKILL_ASSESSMENT_FLOOR, total_questions), min(SKILL_ASSESSMENT_CEILING, total_questions)


def get_skill_assessment_catalog(role_slug: str | None = None) -> dict[str, object]:
    return {
        'version': '2026-05-11.psp-sdlc-v1',
        'scale': [
            {'label': 'Strongly disagree', 'label_th': 'ไม่เห็นด้วยอย่างยิ่ง', 'value': 1},
            {'label': 'Disagree', 'label_th': 'ไม่เห็นด้วย', 'value': 2},
            {'label': 'Neutral', 'label_th': 'เป็นกลาง', 'value': 3},
            {'label': 'Agree', 'label_th': 'เห็นด้วย', 'value': 4},
            {'label': 'Strongly agree', 'label_th': 'เห็นด้วยอย่างยิ่ง', 'value': 5},
        ],
        'dimensions': list_skill_assessment_dimensions(role_slug),
        'questions': list_skill_assessment_questions(role_slug),
        'role_guidance': list_skill_assessment_role_guidance(role_slug),
    }


def get_skill_assessment_question_ids(role_slug: str | None = None) -> set[str]:
    return {question['id'] for question in list_skill_assessment_questions(role_slug)}


def _question_queryset(role_slug: str | None):
    """Items for ``role_slug``, or the role-independent fallback items.

    A role with an imported roadmap has its own topic-anchored items and must
    never be served another role's; a role without one falls back to the items
    that carry no role. See ADR-0002.
    """
    questions = SkillAssessmentQuestion.objects.filter(is_active=True)
    if role_slug and questions.filter(role__slug=role_slug).exists():
        return questions.filter(role__slug=role_slug)
    return questions.filter(role__isnull=True)


def list_skill_assessment_questions(role_slug: str | None = None) -> list[dict[str, object]]:
    return [
        {
            'id': question['question_id'],
            'prompt': question['prompt'],
            'translations': {
                'en': {'prompt': question['prompt']},
                **(question['translations'] or {}),
            },
            'dimension_key': question['dimension_key'],
            'display_order': question['display_order'],
            'topic_slug': question['topic_slug'],
            'topic_title': question['topic_title'],
        }
        for question in _question_queryset(role_slug)
        .order_by('display_order', 'question_id')
        .values('question_id', 'prompt', 'translations', 'dimension_key', 'display_order', 'topic_slug', 'topic_title')
    ]


def list_skill_assessment_dimensions(role_slug: str | None = None) -> list[dict[str, object]]:
    dimensions = SkillAssessmentDimension.objects.filter(is_active=True)
    if role_slug and dimensions.filter(role__slug=role_slug).exists():
        dimensions = dimensions.filter(role__slug=role_slug)
    else:
        dimensions = dimensions.filter(role__isnull=True)
    return [
        {
            'key': dimension['dimension_key'],
            'label': dimension['label'],
            'track': dimension['track'],
            'low_score_action': dimension['low_score_action'],
            'translations': dimension['translations'] or {},
        }
        for dimension in dimensions.order_by('display_order', 'dimension_key')
        .values('dimension_key', 'label', 'track', 'low_score_action', 'translations')
    ]


def list_skill_assessment_role_guidance(role_slug: str | None = None) -> list[str]:
    if role_slug:
        role_guidance = list(
            SkillAssessmentRoleGuidance.objects.filter(role__slug=role_slug, is_active=True)
            .order_by('display_order', 'id')
            .values_list('guidance', flat=True)
        )
        if role_guidance:
            return role_guidance

    return list(
        SkillAssessmentRoleGuidance.objects.filter(role__isnull=True, is_active=True)
        .order_by('display_order', 'id')
        .values_list('guidance', flat=True)
    )


def build_skill_assessment_progress(session: AssessmentSession, answers: dict[str, int]) -> dict[str, object]:
    """How far through the questionnaire the respondent is, and whether it is settled.

    ``settled`` is Recommendation Stability with the floor applied: the top
    five suggestions have stopped changing *and* enough items were answered
    for that to mean something. It is only trusted against the answers the
    session actually saved, so a caller probing with unsaved answers cannot
    stop the assessment early.
    """
    role = session.preferred_role or session.best_fit_role
    total = len(get_skill_assessment_question_ids(role.slug if role else None))
    answered = len(answers)
    floor, ceiling = _stop_bounds(total)
    settled = (
        answered >= floor
        and session.skill_assessment_stable
        and answers == get_skill_assessment_answers(session)
    )
    return {
        'answered': answered,
        'total': total,
        'remaining': max(0, total - answered),
        'floor': floor,
        'ceiling': ceiling,
        'settled': settled,
    }


def select_next_skill_assessment_question(session: AssessmentSession, answers: dict[str, int]) -> dict[str, object] | None:
    """The next unanswered item, or ``None`` once the assessment should stop.

    Stopping follows the stop rule (ADR-0003): the floor of twelve keeps a
    settled-looking start from ending the questionnaire, the ceiling of twenty
    ends it regardless, and in between the assessment stops once the top five
    suggestions stop changing between answers.

    Selection is deterministic and aims at resolving the most uncertainty
    about which sets are held: an unanswered item that already sits among the
    current top five suggestions is asked first, because its rating either
    holds it -- removing it from the suggestions -- or confirms it as a gap,
    and both outcomes change what the respondent would be told. Items outside
    the top five follow in roadmap order. It is not a learned policy: the
    epsilon-greedy selector it replaced was rewarded by agreement, so it
    learned to ask the items a respondent already agrees with.
    """
    role = session.preferred_role or session.best_fit_role
    questions = list_skill_assessment_questions(role.slug if role else None)
    unanswered = [question for question in questions if question['id'] not in answers]
    if not unanswered:
        return None

    progress = build_skill_assessment_progress(session, answers)
    if progress['answered'] >= progress['ceiling'] or progress['settled']:
        return None

    if role:
        suggested_order = [
            item['topic_slug']
            for item in build_assessment_summary(role, answers, held_keys=get_held_topic_keys(session.user))['recommendations']
        ]
    else:
        suggested_order = []

    def uncertainty_rank(question):
        question_id = question['id']
        if question_id in suggested_order:
            return (suggested_order.index(question_id), int(question.get('display_order', 0) or 0), question_id)
        # Not among the current suggestions: ask after those, in roadmap order.
        return (len(suggested_order), int(question.get('display_order', 0) or 0), question_id)

    return min(unanswered, key=uncertainty_rank)


def _format_completed_at(value) -> str | None:
    if value is None:
        return None
    if hasattr(value, 'isoformat'):
        value = value.isoformat()
    if value.endswith('+00:00'):
        value = f'{value[:-6]}Z'
    return value


def get_skill_assessment_answers(session: AssessmentSession) -> dict[str, int]:
    return dict(session.skill_assessment_answers.values_list('question_id', 'value'))


def get_skill_assessment_state(session: AssessmentSession) -> dict[str, object]:
    answers = get_skill_assessment_answers(session)
    role = session.preferred_role or session.best_fit_role
    # Marks belong to the owner, so they are in effect in every session the
    # signed-in respondent opens on this role (ADR-0003).
    held_keys = get_held_topic_keys(session.user)
    if role:
        # Every unit's state -- held, assessed gap, or unassessed -- plus the
        # suggestions derived from the same answers, computed once.
        summary = build_assessment_summary(role, answers, held_keys=held_keys)
        states = [
            {key: entry[key] for key in ('topic_slug', 'topic_title', 'state', 'mastery', 'statement') if key in entry}
            for entry in summary['states']
        ]
        recommendations = summary['recommendations']
        readiness = build_readiness_summary(role, answers, held_keys=held_keys)
    else:
        states = []
        recommendations = []
        readiness = {'targets': {}, 'overall_target': 0.0, 'overall_mastery': 0.0, 'assessed_count': 0}
    return {
        'completed': session.skill_assessment_completed,
        'answers': answers,
        'completed_at': _format_completed_at(session.skill_assessment_completed_at),
        # Derived from the answers, so what the respondent is told to learn next
        # follows from what they said about this role's topics (ADR-0002).
        'topic_mastery': get_topic_mastery(role, answers) if role else {},
        'topic_states': states,
        'recommended_topics': recommendations,
        # The post-assessment screen reads this, not the whole roadmap (ADR-0003).
        'next_topics': recommendations[:NEXT_TOPIC_COUNT],
        'readiness': readiness,
        'progress': build_skill_assessment_progress(session, answers),
        # Reaching the ceiling without the suggestions settling completes the
        # assessment and says the result is less certain (ADR-0003).
        'confidence': (
            'high' if session.skill_assessment_stable else 'low'
        ) if session.skill_assessment_completed else None,
    }


@transaction.atomic
def save_skill_assessment_state(*, session: AssessmentSession, state: dict[str, object]) -> dict[str, object]:
    session = AssessmentSession.objects.with_roles().select_for_update().get(pk=session.pk)
    answers = state.get('answers', {})
    if not isinstance(answers, dict):
        answers = {}
    requested_completed = bool(state.get('completed', False))

    was_completed = session.skill_assessment_completed
    session.skill_assessment_completed = requested_completed
    if session.skill_assessment_completed and not was_completed:
        session.skill_assessment_completed_at = timezone.now()
    elif not session.skill_assessment_completed:
        session.skill_assessment_completed_at = None

    previous_answers = dict(session.skill_assessment_answers.values_list('question_id', 'value'))
    session.skill_assessment_answers.all().delete()
    SkillAssessmentAnswer.objects.bulk_create(
        SkillAssessmentAnswer(session=session, question_id=question_id, value=value) for question_id, value in answers.items()
    )

    # Recommendation Stability: whether this save's answers left the top five
    # suggestions where the previous save had them. Stored on the session, so
    # the decision survives the request that observed it. Only a save whose
    # answers actually changed can move it: re-saving the same answers is not
    # "between answers", so it must not be read as the suggestions settling.
    if answers != previous_answers:
        role = session.preferred_role or session.best_fit_role
        held_keys = get_held_topic_keys(session.user)
        if role:
            top_five = [
                item['topic_slug'] for item in build_assessment_summary(role, answers, held_keys=held_keys)['recommendations'][:5]
            ]
        else:
            top_five = []
        session.skill_assessment_stable = (
            session.skill_assessment_top_five is not None and session.skill_assessment_top_five == top_five
        )
        session.skill_assessment_top_five = top_five

    if requested_completed:
        progress = build_skill_assessment_progress(session, answers)
        if not (progress['settled'] or progress['answered'] >= progress['ceiling']):
            remaining_to_floor = max(0, progress['floor'] - progress['answered'])
            msg = (
                'The Skill Assessment cannot be completed yet: '
                f'{remaining_to_floor} more answer(s) are needed before the suggestions can settle.'
            )
            raise ValidationError({'completed': msg})

    session.save(
        update_fields=[
            'skill_assessment_completed',
            'skill_assessment_completed_at',
            'skill_assessment_top_five',
            'skill_assessment_stable',
            'updated_at',
        ],
    )

    return get_skill_assessment_state(session)
