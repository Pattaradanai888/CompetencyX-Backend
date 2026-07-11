import logging
import random

from django.conf import settings
from django.db.models import Prefetch
from django.utils import timezone

from assessments.models import AssessmentSession
from recommendations.models import Recommendation, RecommendationQValue

from .guidance_service import get_role_alignment_status, get_role_resolution_status
from .q_learning import Q_VALUE_DEFAULTS, clamp_bucket, update_q_row


logger = logging.getLogger('assessments.services')


RECOMMENDATION_MASTERY_THRESHOLD = 0.7
RECOMMENDATION_POLICY_RULE_BASED = Recommendation.PolicyType.RULE_BASED
RECOMMENDATION_POLICY_Q_LEARNING = Recommendation.PolicyType.Q_LEARNING


def refresh_recommendations(session: AssessmentSession):
    Recommendation.objects.filter(session=session).delete()
    if session.phase != AssessmentSession.Phase.RECOMMENDATION_READY:
        logger.info(
            'assessment.recommendations_skipped session_id=%s phase=%s status=%s',
            session.id,
            session.phase,
            session.status,
        )
        return []

    recommendations = []
    preferred_role = session.preferred_role
    best_fit_role = session.best_fit_role

    if preferred_role is not None:
        recommendation = build_recommendation_for_role(
            session,
            role=preferred_role,
            path_kind=Recommendation.PathKind.PREFERRED,
        )
        if recommendation is not None:
            recommendations.append(recommendation)

    if best_fit_role is not None and best_fit_role != preferred_role:
        recommendation = build_recommendation_for_role(
            session,
            role=best_fit_role,
            path_kind=Recommendation.PathKind.BEST_FIT,
        )
        if recommendation is not None:
            recommendations.append(recommendation)

    if not recommendations and best_fit_role is not None:
        recommendation = build_recommendation_for_role(
            session,
            role=best_fit_role,
            path_kind=Recommendation.PathKind.PREFERRED,
        )
        if recommendation is not None:
            recommendations.append(recommendation)

    logger.info(
        'assessment.recommendations_refreshed session_id=%s preferred_role=%s best_fit_role=%s recommendation_count=%s',
        session.id,
        preferred_role.slug if preferred_role else None,
        best_fit_role.slug if best_fit_role else None,
        len(recommendations),
    )
    return recommendations


def build_recommendation_for_role(session: AssessmentSession, *, role, path_kind: str):
    eligible_topics = _get_eligible_recommendation_topics(session, role=role)
    recommendation_policy = _get_recommendation_policy()

    if recommendation_policy == RECOMMENDATION_POLICY_Q_LEARNING:
        return _build_q_learning_recommendation_for_role(
            session,
            role=role,
            path_kind=path_kind,
            eligible_topics=eligible_topics,
        )

    return _build_rule_based_recommendation_for_role(
        session,
        role=role,
        path_kind=path_kind,
        eligible_topics=eligible_topics,
    )


def _get_recommendation_policy() -> str:
    configured_policy = getattr(settings, 'ASSESSMENT_RECOMMENDATION_POLICY', RECOMMENDATION_POLICY_RULE_BASED)
    if configured_policy == RECOMMENDATION_POLICY_Q_LEARNING:
        return RECOMMENDATION_POLICY_Q_LEARNING
    return RECOMMENDATION_POLICY_RULE_BASED


def _get_eligible_recommendation_topics(session: AssessmentSession, *, role) -> list:
    eligible_topics = []
    for topic in role.topics.filter(is_active=True).prefetch_related(Prefetch('prerequisites', to_attr='prefetched_prerequisites')):
        prerequisites = getattr(topic, 'prefetched_prerequisites', [])
        if all(prerequisite.required_mastery_threshold <= 0.0 for prerequisite in prerequisites):
            eligible_topics.append(topic)
    return eligible_topics


def _build_rule_based_recommendation_for_role(
    session: AssessmentSession,
    *,
    role,
    path_kind: str,
    eligible_topics: list,
):
    if eligible_topics:
        topic = min(eligible_topics, key=lambda candidate: (candidate.display_order, candidate.id))
        return Recommendation.objects.create(
            session=session,
            role=role,
            topic=topic,
            reason='Lowest-order topic with satisfied prerequisites and insufficient mastery.',
            path_kind=path_kind,
            policy_type=Recommendation.PolicyType.RULE_BASED,
            score=1.0,
            state_key='',
        )

    return Recommendation.objects.create(
        session=session,
        role=role,
        topic=None,
        reason='No further topic recommendation is available for the current mastery profile.',
        path_kind=path_kind,
        policy_type=Recommendation.PolicyType.RULE_BASED,
        score=0.0,
        state_key='',
    )


def _build_q_learning_recommendation_for_role(
    session: AssessmentSession,
    *,
    role,
    path_kind: str,
    eligible_topics: list,
):
    state_key = _build_recommendation_state_key(session, role=role, path_kind=path_kind)

    if not eligible_topics:
        return Recommendation.objects.create(
            session=session,
            role=role,
            topic=None,
            reason='Q-learning found no eligible next topic for the current mastery profile.',
            path_kind=path_kind,
            policy_type=Recommendation.PolicyType.Q_LEARNING,
            score=0.0,
            state_key=state_key,
        )

    chosen_topic, q_value, reward = _select_q_learning_topic(
        session,
        role=role,
        path_kind=path_kind,
        state_key=state_key,
        eligible_topics=eligible_topics,
    )
    return Recommendation.objects.create(
        session=session,
        role=role,
        topic=chosen_topic,
        reason=(
            'Q-learning selected the next topic from the current mastery state using an '
            'epsilon-greedy policy and projected future learning value.'
        ),
        path_kind=path_kind,
        policy_type=Recommendation.PolicyType.Q_LEARNING,
        score=max(q_value, reward, 1.0),
        state_key=state_key,
    )


def _build_recommendation_state_key(
    session: AssessmentSession,
    *,
    role,
    path_kind: str,
    mastery_overrides: dict[int, float] | None = None,
) -> str:
    role_alignment = get_role_alignment_status(session)
    role_resolution = get_role_resolution_status(session)
    role_topics = list(role.topics.filter(is_active=True).order_by('display_order', 'id'))
    overrides = mastery_overrides or {}
    if role_topics:
        mastery_values = [float(overrides.get(topic.id, 0.0)) for topic in role_topics]
        average_mastery = sum(mastery_values) / len(mastery_values)
        weak_topic_count = sum(1 for value in mastery_values if value < RECOMMENDATION_MASTERY_THRESHOLD)
    else:
        average_mastery = 0.0
        weak_topic_count = 0

    mastery_bucket = clamp_bucket(average_mastery * 4)
    confidence_bucket = clamp_bucket(float(session.best_fit_confidence or 0.0) * 4)
    weak_bucket = clamp_bucket(weak_topic_count)
    return ':'.join(
        [
            role.slug,
            path_kind,
            role_alignment,
            role_resolution,
            f'confidence-{confidence_bucket}',
            f'mastery-{mastery_bucket}',
            f'weak-{weak_bucket}',
        ],
    )


def _select_q_learning_topic(
    session: AssessmentSession,
    *,
    role,
    path_kind: str,
    state_key: str,
    eligible_topics: list,
) -> tuple[object, float, float]:
    epsilon = float(getattr(settings, 'ASSESSMENT_RECOMMENDATION_Q_EPSILON', 0.15))
    alpha = float(getattr(settings, 'ASSESSMENT_RECOMMENDATION_Q_ALPHA', 0.35))
    gamma = float(getattr(settings, 'ASSESSMENT_RECOMMENDATION_Q_GAMMA', 0.8))

    q_rows = {
        row.topic_id: row
        for row in RecommendationQValue.objects.filter(
            state_key=state_key,
            path_kind=path_kind,
            role=role,
            topic_id__in=[topic.id for topic in eligible_topics],
        )
    }

    if random.random() < epsilon:  # noqa: S311
        chosen_topic = random.choice(eligible_topics)  # noqa: S311
    else:
        chosen_topic = max(
            eligible_topics,
            key=lambda topic: (
                q_rows.get(topic.id).q_value if q_rows.get(topic.id) is not None else 0.0,
                1.0,
                -topic.display_order,
                -topic.id,
            ),
        )

    reward = _calculate_recommendation_reward(chosen_topic)
    current_q_row, _created = RecommendationQValue.objects.get_or_create(
        state_key=state_key,
        path_kind=path_kind,
        role=role,
        topic=chosen_topic,
        defaults=Q_VALUE_DEFAULTS,
    )
    projected_next_q = _get_projected_next_q_value(
        session,
        role=role,
        path_kind=path_kind,
        chosen_topic=chosen_topic,
    )
    current_q, updated_q = update_q_row(
        current_q_row,
        reward=reward,
        alpha=alpha,
        target=reward + (gamma * projected_next_q),
    )

    logger.info(
        (
            'assessment.q_learning_recommendation_updated session_id=%s role=%s path_kind=%s '
            'state=%s topic=%s reward=%.4f q_before=%.4f q_after=%.4f projected_next_q=%.4f'
        ),
        session.id,
        role.slug,
        path_kind,
        state_key,
        chosen_topic.slug,
        reward,
        current_q,
        updated_q,
        projected_next_q,
    )
    return chosen_topic, updated_q, reward


def _calculate_recommendation_reward(topic) -> float:
    order_bonus = 1.0 / (1.0 + max(topic.display_order, 0))
    difficulty_bonus = 0.15 if topic.difficulty == topic.Difficulty.BEGINNER else 0.05
    return max(0.0, min(1.0, 0.7 + (0.2 * order_bonus) + difficulty_bonus))


def _get_projected_next_q_value(
    session: AssessmentSession,
    *,
    role,
    path_kind: str,
    chosen_topic,
) -> float:
    mastery_overrides = {chosen_topic.id: RECOMMENDATION_MASTERY_THRESHOLD}
    projected_state_key = _build_recommendation_state_key(
        session,
        role=role,
        path_kind=path_kind,
        mastery_overrides=mastery_overrides,
    )

    projected_eligible_topics = []
    for topic in role.topics.filter(is_active=True).prefetch_related(Prefetch('prerequisites', to_attr='prefetched_prerequisites')):
        if mastery_overrides.get(topic.id, 0.0) >= RECOMMENDATION_MASTERY_THRESHOLD:
            continue
        prerequisites = getattr(topic, 'prefetched_prerequisites', [])
        if all(mastery_overrides.get(prerequisite.prerequisite_id, 0.0) >= prerequisite.required_mastery_threshold for prerequisite in prerequisites):
            projected_eligible_topics.append(topic)

    if not projected_eligible_topics:
        return 0.0

    next_q_values = RecommendationQValue.objects.filter(
        state_key=projected_state_key,
        path_kind=path_kind,
        role=role,
        topic_id__in=[topic.id for topic in projected_eligible_topics],
    ).values_list('q_value', flat=True)
    return max((float(value) for value in next_q_values), default=0.0)


def apply_recommendation_feedback_from_survey2(session: AssessmentSession) -> int:
    if not session.survey2_completed:
        return 0

    answers = dict(session.survey2_answers.values_list('question_id', 'value'))
    if not answers:
        return 0

    applied_count = 0
    alpha = float(getattr(settings, 'ASSESSMENT_RECOMMENDATION_Q_ALPHA', 0.35))
    completed_at = timezone.now()
    outcome_reward = _calculate_survey2_outcome_reward(answers)

    for recommendation in session.recommendations.select_related('role', 'topic').filter(
        policy_type=Recommendation.PolicyType.Q_LEARNING,
        feedback_reward_applied=False,
        topic__isnull=False,
    ):
        if not recommendation.state_key:
            continue

        q_value_row, _created = RecommendationQValue.objects.get_or_create(
            state_key=recommendation.state_key,
            path_kind=recommendation.path_kind,
            role=recommendation.role,
            topic=recommendation.topic,
            defaults=Q_VALUE_DEFAULTS,
        )
        current_q, updated_q = update_q_row(q_value_row, reward=outcome_reward, alpha=alpha)

        recommendation.feedback_reward_applied = True
        recommendation.feedback_reward_applied_at = completed_at
        recommendation.save(update_fields=['feedback_reward_applied', 'feedback_reward_applied_at'])
        applied_count += 1
        logger.info(
            (
                'assessment.q_learning_feedback_applied session_id=%s role=%s path_kind=%s topic=%s '
                'outcome_reward=%.4f q_before=%.4f q_after=%.4f'
            ),
            session.id,
            recommendation.role.slug,
            recommendation.path_kind,
            recommendation.topic.slug,
            outcome_reward,
            current_q,
            updated_q,
        )

    return applied_count


def _calculate_survey2_outcome_reward(answers: dict[str, int]) -> float:
    values = [int(value) for value in answers.values()]
    completion_reward = 0.55
    average_score = sum(values) / len(values)
    normalized_average = max(0.0, min(1.0, (average_score - 1.0) / 4.0))
    consistency_penalty = 0.0
    if len(values) > 1:
        spread = (max(values) - min(values)) / 4.0
        consistency_penalty = 0.1 * spread
    reward = completion_reward + (0.45 * normalized_average) - consistency_penalty
    return max(0.0, min(1.0, reward))
