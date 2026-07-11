import random

from django.conf import settings
from django.db import transaction

from assessments.models import (
    AssessmentSession,
    Survey2Answer,
    Survey2Dimension,
    Survey2FeedbackEvent,
    Survey2Question,
    Survey2QuestionQValue,
    Survey2RoleGuidance,
)

from . import recommendation_service
from .guidance_service import get_role_alignment_status, get_role_resolution_status
from .q_learning import Q_VALUE_DEFAULTS, clamp_bucket, update_q_row


def get_survey2_catalog(role_slug: str | None = None) -> dict[str, object]:
    return {
        'version': '2026-05-11.psp-sdlc-v1',
        'scale': [
            {'label': 'Strongly disagree', 'label_th': 'ไม่เห็นด้วยอย่างยิ่ง', 'value': 1},
            {'label': 'Disagree', 'label_th': 'ไม่เห็นด้วย', 'value': 2},
            {'label': 'Neutral', 'label_th': 'เป็นกลาง', 'value': 3},
            {'label': 'Agree', 'label_th': 'เห็นด้วย', 'value': 4},
            {'label': 'Strongly agree', 'label_th': 'เห็นด้วยอย่างยิ่ง', 'value': 5},
        ],
        'dimensions': list_survey2_dimensions(),
        'questions': list_survey2_questions(),
        'role_guidance': list_survey2_role_guidance(role_slug),
    }


def get_survey2_question_ids() -> set[str]:
    return {question['id'] for question in list_survey2_questions()}


def list_survey2_questions() -> list[dict[str, object]]:
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
        }
        for question in Survey2Question.objects.filter(is_active=True)
        .order_by('display_order', 'question_id')
        .values('question_id', 'prompt', 'translations', 'dimension_key', 'display_order')
    ]


def list_survey2_dimensions() -> list[dict[str, object]]:
    return [
        {
            'key': dimension['dimension_key'],
            'label': dimension['label'],
            'track': dimension['track'],
            'low_score_action': dimension['low_score_action'],
        }
        for dimension in Survey2Dimension.objects.filter(is_active=True)
        .order_by('display_order', 'dimension_key')
        .values('dimension_key', 'label', 'track', 'low_score_action')
    ]


def list_survey2_role_guidance(role_slug: str | None = None) -> list[str]:
    if role_slug:
        role_guidance = list(
            Survey2RoleGuidance.objects.filter(role__slug=role_slug, is_active=True)
            .order_by('display_order', 'id')
            .values_list('guidance', flat=True)
        )
        if role_guidance:
            return role_guidance

    return list(
        Survey2RoleGuidance.objects.filter(role__isnull=True, is_active=True)
        .order_by('display_order', 'id')
        .values_list('guidance', flat=True)
    )


def build_survey2_state_key(session: AssessmentSession, answers: dict[str, int]) -> str:
    role_slug = (session.preferred_role or session.best_fit_role).slug if (session.preferred_role or session.best_fit_role) else 'none'
    role_alignment = get_role_alignment_status(session)
    role_resolution = get_role_resolution_status(session)
    avg = (sum(answers.values()) / len(answers)) if answers else 3.0
    avg_bucket = clamp_bucket((avg - 1.0) // 1.0)
    progress_bucket = clamp_bucket(len(answers) // 3)
    return ':'.join(
        [
            role_slug,
            role_alignment,
            role_resolution,
            f'avg-{avg_bucket}',
            f'progress-{progress_bucket}',
        ],
    )


def select_next_survey2_question(
    session: AssessmentSession,
    answers: dict[str, int],
    *,
    rng=random,  # pass a seeded random.Random for deterministic selection
) -> dict[str, object] | None:
    questions = list_survey2_questions()
    unanswered = [question for question in questions if question['id'] not in answers]
    if not unanswered:
        return None

    state_key = build_survey2_state_key(session, answers)
    epsilon = float(getattr(settings, 'ASSESSMENT_RECOMMENDATION_Q_EPSILON', 0.15))
    if rng.random() < epsilon:
        return rng.choice(unanswered)

    q_map = {
        row.question_id: row
        for row in Survey2QuestionQValue.objects.filter(
            state_key=state_key,
            question_id__in=[question['id'] for question in unanswered],
        )
    }
    return max(
        unanswered,
        key=lambda question: (
            q_map.get(question['id']).q_value if q_map.get(question['id']) is not None else 0.0,
            -int(question.get('display_order', 0) or 0),
            question['id'],
        ),
    )


def apply_survey2_step_feedback(session: AssessmentSession, *, before_answers: dict[str, int], answered_question_id: str) -> None:
    after_state_key = build_survey2_state_key(session, before_answers)
    answered_value = int(before_answers.get(answered_question_id, 3))
    immediate_reward = max(0.0, min(1.0, (answered_value - 1.0) / 4.0))
    alpha = float(getattr(settings, 'ASSESSMENT_RECOMMENDATION_Q_ALPHA', 0.35))

    q_row, _created = Survey2QuestionQValue.objects.get_or_create(
        state_key=after_state_key,
        question_id=answered_question_id,
        defaults=Q_VALUE_DEFAULTS,
    )
    update_q_row(q_row, reward=immediate_reward, alpha=alpha)


def _format_completed_at(value) -> str | None:
    if value is None:
        return None
    if hasattr(value, 'isoformat'):
        value = value.isoformat()
    if value.endswith('+00:00'):
        value = f'{value[:-6]}Z'
    return value


def get_survey2_answers(session: AssessmentSession) -> dict[str, int]:
    return dict(session.survey2_answers.values_list('question_id', 'value'))


def get_survey2_state(session: AssessmentSession) -> dict[str, object]:
    return {
        'completed': session.survey2_completed,
        'answers': get_survey2_answers(session),
        'completed_at': _format_completed_at(session.survey2_completed_at),
    }


@transaction.atomic
def save_survey2_state(*, session: AssessmentSession, state: dict[str, object]) -> dict[str, object]:
    session = AssessmentSession.objects.with_roles().select_for_update().get(pk=session.pk)
    answers = state.get('answers', {})
    if not isinstance(answers, dict):
        answers = {}

    session.survey2_completed = bool(state.get('completed', False))
    session.survey2_completed_at = state.get('completed_at')
    session.save(update_fields=['survey2_completed', 'survey2_completed_at', 'updated_at'])

    session.survey2_answers.all().delete()
    Survey2Answer.objects.bulk_create(
        Survey2Answer(session=session, question_id=question_id, value=value) for question_id, value in answers.items()
    )

    applied_question_ids = set(session.survey2_feedback_events.values_list('question_id', flat=True))
    new_question_ids = answers.keys() - applied_question_ids
    Survey2FeedbackEvent.objects.bulk_create(
        Survey2FeedbackEvent(session=session, question_id=question_id) for question_id in new_question_ids
    )

    for question_id in new_question_ids:
        apply_survey2_step_feedback(session, before_answers=answers, answered_question_id=question_id)
    if session.survey2_completed:
        recommendation_service.apply_recommendation_feedback_from_survey2(session)
    return get_survey2_state(session)
