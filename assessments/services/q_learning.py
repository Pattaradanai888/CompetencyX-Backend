"""Shared Q-learning primitives for the skill assessment and recommendation services.

Both services persist per-state Q-values (``SkillAssessmentQuestionQValue``,
``RecommendationQValue``) with the same field layout and the same
exponential-moving-average update rule; this module is the single home for
that update and for the small state-key bucketing helper.
"""

from django.db import transaction


Q_VALUE_DEFAULTS = {
    'q_value': 0.0,
    'reward_total': 0.0,
    'update_count': 0,
    'last_reward': 0.0,
}

STATE_KEY_BUCKET_CAP = 4


def clamp_bucket(value: float, *, cap: int = STATE_KEY_BUCKET_CAP) -> int:
    return min(max(int(value), 0), cap)


def update_q_row(q_row, *, reward: float, alpha: float, target: float | None = None) -> tuple[float, float]:
    """Apply one EMA step toward ``target`` (defaults to the immediate reward).

    Pass ``target=reward + gamma * projected_next_q`` for the
    temporal-difference form. Returns ``(q_before, q_after)``.
    """
    if target is None:
        target = reward
    with transaction.atomic():
        locked_row = type(q_row).objects.select_for_update().get(pk=q_row.pk)
        q_before = float(locked_row.q_value)
        locked_row.q_value = q_before + alpha * (target - q_before)
        locked_row.reward_total += reward
        locked_row.update_count += 1
        locked_row.last_reward = reward
        locked_row.save(update_fields=['q_value', 'reward_total', 'update_count', 'last_reward', 'updated_at'])

    q_row.q_value = locked_row.q_value
    q_row.reward_total = locked_row.reward_total
    q_row.update_count = locked_row.update_count
    q_row.last_reward = locked_row.last_reward
    return q_before, float(locked_row.q_value)
