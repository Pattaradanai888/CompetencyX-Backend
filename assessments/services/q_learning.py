"""Shared Q-learning primitives for the survey-2 and recommendation services.

Both services persist per-state Q-values (``Survey2QuestionQValue``,
``RecommendationQValue``) with the same field layout and the same
exponential-moving-average update rule; this module is the single home for
that update and for the small state-key bucketing helper.
"""

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
    q_before = float(q_row.q_value)
    q_row.q_value = q_before + alpha * (target - q_before)
    q_row.reward_total += reward
    q_row.update_count += 1
    q_row.last_reward = reward
    q_row.save(update_fields=['q_value', 'reward_total', 'update_count', 'last_reward', 'updated_at'])
    return q_before, float(q_row.q_value)
