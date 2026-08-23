from django.db import transaction
from django.utils import timezone

from assessments.models import (
    AssessmentSession,
    SkillAssessmentAnswer,
    SkillAssessmentDimension,
    SkillAssessmentQuestion,
    SkillAssessmentRoleGuidance,
)

from .topic_skill_assessment_service import build_readiness_summary, build_topic_recommendations, get_topic_mastery


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


def select_next_skill_assessment_question(session: AssessmentSession, answers: dict[str, int]) -> dict[str, object] | None:
    """The next unanswered item for the session's role, in authored order.

    Roadmap order is the only signal here: the epsilon-greedy policy that used to
    choose was rewarded by how strongly the respondent agreed with an item, so it
    learned to ask the questions someone already agrees with -- the opposite of
    what an adaptive questionnaire needs (ADR-0003).
    """
    role = session.preferred_role or session.best_fit_role
    questions = list_skill_assessment_questions(role.slug if role else None)
    unanswered = [question for question in questions if question['id'] not in answers]
    if not unanswered:
        return None

    return min(unanswered, key=lambda question: (int(question.get('display_order', 0) or 0), question['id']))


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
    return {
        'completed': session.skill_assessment_completed,
        'answers': answers,
        'completed_at': _format_completed_at(session.skill_assessment_completed_at),
        # Derived from the answers, so what the respondent is told to learn next
        # follows from what they said about this role's topics (ADR-0002).
        'topic_mastery': get_topic_mastery(role, answers) if role else {},
        'recommended_topics': build_topic_recommendations(role, answers) if role else [],
        'readiness': build_readiness_summary(role, answers) if role else {'targets': {}, 'overall_target': 0.0, 'overall_mastery': 0.0},
    }


@transaction.atomic
def save_skill_assessment_state(*, session: AssessmentSession, state: dict[str, object]) -> dict[str, object]:
    session = AssessmentSession.objects.with_roles().select_for_update().get(pk=session.pk)
    answers = state.get('answers', {})
    if not isinstance(answers, dict):
        answers = {}

    was_completed = session.skill_assessment_completed
    session.skill_assessment_completed = bool(state.get('completed', False))
    if session.skill_assessment_completed and not was_completed:
        session.skill_assessment_completed_at = timezone.now()
    elif not session.skill_assessment_completed:
        session.skill_assessment_completed_at = None
    session.save(update_fields=['skill_assessment_completed', 'skill_assessment_completed_at', 'updated_at'])

    session.skill_assessment_answers.all().delete()
    SkillAssessmentAnswer.objects.bulk_create(
        SkillAssessmentAnswer(session=session, question_id=question_id, value=value) for question_id, value in answers.items()
    )

    return get_skill_assessment_state(session)
