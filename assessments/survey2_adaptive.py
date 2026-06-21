import random

from django.conf import settings

from .guidance import get_role_alignment_status, get_role_resolution_status
from .models import AssessmentSession, Survey2QuestionQValue
from .roadmaps import list_survey2_questions


def build_survey2_state_key(session: AssessmentSession, answers: dict[str, int]) -> str:
    role_slug = (session.preferred_role or session.best_fit_role).slug if (session.preferred_role or session.best_fit_role) else 'none'
    role_alignment = get_role_alignment_status(session)
    role_resolution = get_role_resolution_status(session)
    avg = (sum(answers.values()) / len(answers)) if answers else 3.0
    avg_bucket = min(max(int((avg - 1.0) // 1.0), 0), 4)
    progress_bucket = min(len(answers) // 3, 4)
    return ':'.join(
        [
            role_slug,
            role_alignment,
            role_resolution,
            f'avg-{avg_bucket}',
            f'progress-{progress_bucket}',
        ],
    )


def select_next_survey2_question(session: AssessmentSession, answers: dict[str, int]) -> dict[str, object] | None:
    questions = list_survey2_questions()
    unanswered = [question for question in questions if question['id'] not in answers]
    if not unanswered:
        return None

    state_key = build_survey2_state_key(session, answers)
    epsilon = float(getattr(settings, 'ASSESSMENT_RECOMMENDATION_Q_EPSILON', 0.15))

    if random.random() < epsilon:  # noqa: S311
        return random.choice(unanswered)  # noqa: S311

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
        defaults={
            'q_value': 0.0,
            'reward_total': 0.0,
            'update_count': 0,
            'last_reward': 0.0,
        },
    )
    current_q = float(q_row.q_value)
    updated_q = current_q + alpha * (immediate_reward - current_q)
    q_row.q_value = updated_q
    q_row.reward_total += immediate_reward
    q_row.update_count += 1
    q_row.last_reward = immediate_reward
    q_row.save(update_fields=['q_value', 'reward_total', 'update_count', 'last_reward', 'updated_at'])
