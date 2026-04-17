import logging
from collections import defaultdict

from django.db import transaction
from django.db.models import Prefetch, Q
from django.utils import timezone

from recommendations.models import Recommendation
from roadmaps.models import Question, Role

from .models import Answer, AssessmentSession, TopicMastery


logger = logging.getLogger(__name__)


ROLE_QUESTION_TARGET = 2
SKILL_QUESTION_TARGET = 3
RECOMMENDATION_MASTERY_THRESHOLD = 0.7
UNANSWERED_TOPIC_CONFIDENCE = 0.0
MAX_GAP_TOPICS = 3


class AssessmentFlowError(ValueError):
    """Raised when the assessment session flow is used incorrectly."""


def create_assessment_session(*, preferred_role=None, profile=None) -> AssessmentSession:
    session = AssessmentSession.objects.create(
        preferred_role=preferred_role,
        best_fit_role=None,
        best_fit_confidence=0.0,
        phase=AssessmentSession.Phase.ROLE_DISCOVERY,
        profile=profile or {},
    )
    logger.info(
        'assessment.session_created session_id=%s preferred_role=%s profile_keys=%s',
        session.id,
        preferred_role.slug if preferred_role else None,
        sorted((profile or {}).keys()),
    )
    return session


def get_current_question(session: AssessmentSession):
    if session.status == AssessmentSession.Status.COMPLETED:
        return None

    base_queryset = _get_unanswered_questions(session)
    if session.phase == AssessmentSession.Phase.ROLE_DISCOVERY:
        candidates = list(base_queryset.filter(stage=Question.Stage.ROLE))
        if not candidates:
            return None
        return max(candidates, key=_score_role_question)

    target_role = get_skill_target_role(session)
    if target_role is None:
        return None

    candidates = list(
        base_queryset.filter(stage=Question.Stage.SKILL)
        .filter(Q(role__isnull=True) | Q(role=target_role))
        .filter(Q(topic__isnull=True) | Q(topic__role=target_role))
    )
    if not candidates:
        return None
    return max(candidates, key=lambda question: _score_skill_question(session, question))


@transaction.atomic
def submit_answer(
    *,
    session: AssessmentSession,
    question: Question,
    option,
    response_time_ms=None,
    confidence_indicator='',
):
    logger.info(
        (
            'assessment.answer_submission_received session_id=%s phase=%s '
            'question_id=%s question_code=%s option_id=%s '
            'response_time_ms=%s confidence_indicator=%s'
        ),
        session.id,
        session.phase,
        question.id,
        question.code,
        option.id,
        response_time_ms,
        confidence_indicator or '',
    )
    expected_question = get_current_question(session)
    if expected_question is None:
        msg = 'This assessment session is not accepting more answers.'
        raise AssessmentFlowError(msg)
    if question.id != expected_question.id:
        msg = f'Out-of-order answer submission. Expected question "{expected_question.code}" ({expected_question.id}).'
        raise AssessmentFlowError(msg)

    answer, created = Answer.objects.get_or_create(
        session=session,
        question=question,
        defaults={
            'selected_option': option,
            'response_time_ms': response_time_ms,
            'confidence_indicator': confidence_indicator,
        },
    )
    if not created:
        msg = 'This question has already been answered for the session.'
        raise AssessmentFlowError(msg)

    logger.info(
        'assessment.answer_recorded session_id=%s answer_id=%s question_id=%s question_stage=%s option_key=%s',
        session.id,
        answer.id,
        question.id,
        question.stage,
        option.key,
    )
    _recompute_best_fit_role(session)
    _recompute_mastery(session)
    _update_phase(session)
    refresh_recommendations(session)
    return answer


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
        recommendation = _build_recommendation_for_role(
            session,
            role=preferred_role,
            path_kind=Recommendation.PathKind.PREFERRED,
        )
        if recommendation is not None:
            recommendations.append(recommendation)

    if best_fit_role is not None and best_fit_role != preferred_role:
        recommendation = _build_recommendation_for_role(
            session,
            role=best_fit_role,
            path_kind=Recommendation.PathKind.BEST_FIT,
        )
        if recommendation is not None:
            recommendations.append(recommendation)

    if not recommendations and best_fit_role is not None:
        recommendation = _build_recommendation_for_role(
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


def serialize_milestones(session: AssessmentSession):
    return {
        'answered_role_questions': session.answers.filter(question__stage=Question.Stage.ROLE).count(),
        'answered_skill_questions': session.answers.filter(question__stage=Question.Stage.SKILL).count(),
    }


def get_skill_target_role(session: AssessmentSession):
    return session.preferred_role or session.best_fit_role


def get_role_alignment_status(session: AssessmentSession) -> str:
    if session.best_fit_role_id is None:
        return 'unknown'
    if session.preferred_role_id is None:
        return 'aligned'
    if session.preferred_role_id == session.best_fit_role_id:
        return 'aligned'
    return 'mismatch'


def get_preferred_role_gap_topics(session: AssessmentSession, *, limit: int = MAX_GAP_TOPICS):
    role = get_skill_target_role(session)
    if role is None:
        return []

    topic_mastery = {mastery.topic_id: mastery for mastery in session.mastery_scores.select_related('topic')}
    ranked_topics = sorted(
        role.topics.filter(is_active=True),
        key=lambda topic: (
            topic_mastery.get(topic.id).mastery_score if topic.id in topic_mastery else 0.0,
            topic.display_order,
            topic.id,
        ),
    )
    return ranked_topics[:limit]


def build_guidance_summary(session: AssessmentSession) -> str:
    alignment_status = get_role_alignment_status(session)
    preferred_role = session.preferred_role
    best_fit_role = session.best_fit_role
    gap_topics = get_preferred_role_gap_topics(session)
    gap_names = ', '.join(topic.title for topic in gap_topics)

    if preferred_role is None and best_fit_role is None:
        return 'Answer the role-discovery questions to identify the best-fit roadmap.'

    if preferred_role is not None and best_fit_role is None:
        return f'You want to pursue {preferred_role.name}. Answer the role-discovery questions to see how close your current fit is.'

    if preferred_role is None and best_fit_role is not None:
        return f'Your current answers align best with {best_fit_role.name}. Focus next on {gap_names}.'

    if alignment_status == 'aligned':
        return f'You are tracking well toward {preferred_role.name}. Focus next on {gap_names}.'

    return (
        f'Your current answers look closer to {best_fit_role.name}, but you can still pursue {preferred_role.name}. '
        f'The main gaps to close are {gap_names}.'
    )


def _build_recommendation_for_role(session: AssessmentSession, *, role: Role, path_kind: str):
    topic_mastery = {mastery.topic_id: mastery.mastery_score for mastery in session.mastery_scores.select_related('topic')}
    for topic in role.topics.filter(is_active=True).prefetch_related(Prefetch('prerequisites', to_attr='prefetched_prerequisites')):
        current_mastery = topic_mastery.get(topic.id, 0.0)
        if current_mastery >= RECOMMENDATION_MASTERY_THRESHOLD:
            continue
        prerequisites = getattr(topic, 'prefetched_prerequisites', [])
        if all(topic_mastery.get(prerequisite.prerequisite_id, 0.0) >= prerequisite.required_mastery_threshold for prerequisite in prerequisites):
            return Recommendation.objects.create(
                session=session,
                role=role,
                topic=topic,
                reason='Lowest-order topic with satisfied prerequisites and insufficient mastery.',
                path_kind=path_kind,
                policy_type=Recommendation.PolicyType.RULE_BASED,
                score=1.0 - current_mastery,
            )

    return Recommendation.objects.create(
        session=session,
        role=role,
        topic=None,
        reason='No further topic recommendation is available for the current mastery profile.',
        path_kind=path_kind,
        policy_type=Recommendation.PolicyType.RULE_BASED,
        score=0.0,
    )


def _recompute_best_fit_role(session: AssessmentSession) -> None:
    answers = (
        session.answers.filter(question__stage=Question.Stage.ROLE)
        .select_related('selected_option')
        .prefetch_related('selected_option__role_signals__role')
    )
    role_scores = defaultdict(float)
    for answer in answers:
        for signal in answer.selected_option.role_signals.all():
            role_scores[signal.role.slug] += float(signal.weight)

    if not role_scores:
        session.best_fit_role = None
        session.best_fit_confidence = 0.0
        session.save(update_fields=['best_fit_role', 'best_fit_confidence', 'updated_at'])
        logger.info(
            'assessment.best_fit_recomputed session_id=%s best_fit_role=%s confidence=%.4f role_scores=%s',
            session.id,
            None,
            0.0,
            {},
        )
        return

    sorted_scores = sorted(role_scores.items(), key=lambda item: item[1], reverse=True)
    top_slug, top_score = sorted_scores[0]
    total = sum(max(score, 0.0) for _, score in sorted_scores)
    session.best_fit_role = Role.objects.filter(slug=top_slug, is_active=True).first()
    session.best_fit_confidence = (top_score / total) if total else 0.0
    session.save(update_fields=['best_fit_role', 'best_fit_confidence', 'updated_at'])
    logger.info(
        'assessment.best_fit_recomputed session_id=%s best_fit_role=%s confidence=%.4f role_scores=%s',
        session.id,
        session.best_fit_role.slug if session.best_fit_role else None,
        session.best_fit_confidence,
        dict(sorted_scores),
    )


def _recompute_mastery(session: AssessmentSession) -> None:
    target_role = get_skill_target_role(session)
    if target_role is None:
        TopicMastery.objects.filter(session=session).delete()
        logger.info(
            'assessment.mastery_recomputed session_id=%s target_role=%s topic_count=%s mastery_scores=%s',
            session.id,
            None,
            0,
            [],
        )
        return

    answers = session.answers.filter(
        question__stage=Question.Stage.SKILL,
        question__topic__isnull=False,
        question__topic__role=target_role,
    ).select_related('question__topic', 'selected_option')
    aggregates = defaultdict(lambda: {'weighted_total': 0.0, 'weight': 0.0, 'topic': None})
    for answer in answers:
        weight = max(answer.question.discrimination_score, 1.0)
        for signal in answer.selected_option.topic_signals.select_related('topic'):
            if signal.topic.role_id != target_role.id:
                continue
            aggregates[signal.topic_id]['weighted_total'] += signal.mastery_delta * weight
            aggregates[signal.topic_id]['weight'] += weight
            aggregates[signal.topic_id]['topic'] = signal.topic

    existing_topic_ids = set(TopicMastery.objects.filter(session=session).values_list('topic_id', flat=True))
    computed_topic_ids = set(aggregates)
    for topic_id in existing_topic_ids - computed_topic_ids:
        TopicMastery.objects.filter(session=session, topic_id=topic_id).delete()

    for aggregate in aggregates.values():
        mastery_score = aggregate['weighted_total'] / aggregate['weight']
        confidence_score = min(1.0, aggregate['weight'] / max(SKILL_QUESTION_TARGET, 1))
        TopicMastery.objects.update_or_create(
            session=session,
            topic=aggregate['topic'],
            defaults={
                'mastery_score': mastery_score,
                'confidence_score': confidence_score,
            },
        )

    mastery_snapshot = list(
        session.mastery_scores.select_related('topic')
        .order_by('topic__display_order', 'topic_id')
        .values_list('topic__slug', 'mastery_score', 'confidence_score')
    )
    logger.info(
        'assessment.mastery_recomputed session_id=%s target_role=%s topic_count=%s mastery_scores=%s',
        session.id,
        target_role.slug,
        len(mastery_snapshot),
        mastery_snapshot,
    )


def _update_phase(session: AssessmentSession) -> None:
    previous_phase = session.phase
    previous_status = session.status
    role_answers = session.answers.filter(question__stage=Question.Stage.ROLE).count()
    has_remaining_role_questions = (
        Question.objects.filter(stage=Question.Stage.ROLE, is_active=True)
        .exclude(id__in=session.answers.values_list('question_id', flat=True))
        .exists()
    )
    if role_answers < ROLE_QUESTION_TARGET and has_remaining_role_questions:
        session.phase = AssessmentSession.Phase.ROLE_DISCOVERY
        session.status = AssessmentSession.Status.IN_PROGRESS
        session.completed_at = None
        session.save(update_fields=['phase', 'status', 'completed_at', 'updated_at'])
        return

    has_remaining_skill_questions = get_current_question_for_role(session)
    if has_remaining_skill_questions:
        session.phase = AssessmentSession.Phase.SKILL_ASSESSMENT
        session.status = AssessmentSession.Status.IN_PROGRESS
        session.completed_at = None
    else:
        session.phase = AssessmentSession.Phase.RECOMMENDATION_READY
        session.status = AssessmentSession.Status.COMPLETED
        session.completed_at = timezone.now()

    session.save(update_fields=['phase', 'status', 'completed_at', 'updated_at'])
    logger.info(
        (
            'assessment.phase_updated session_id=%s previous_phase=%s new_phase=%s '
            'previous_status=%s new_status=%s role_answers=%s '
            'has_skill_questions=%s completed_at=%s'
        ),
        session.id,
        previous_phase,
        session.phase,
        previous_status,
        session.status,
        role_answers,
        bool(has_remaining_skill_questions),
        session.completed_at.isoformat() if session.completed_at else None,
    )


def get_current_question_for_role(session: AssessmentSession):
    target_role = get_skill_target_role(session)
    if target_role is None:
        return None
    return (
        _get_unanswered_questions(session)
        .filter(stage=Question.Stage.SKILL)
        .filter(Q(role__isnull=True) | Q(role=target_role))
        .filter(Q(topic__isnull=True) | Q(topic__role=target_role))
        .exists()
    )


def _get_unanswered_questions(session: AssessmentSession):
    answered_question_ids = session.answers.values_list('question_id', flat=True)
    return Question.objects.filter(is_active=True).exclude(id__in=answered_question_ids).select_related('role', 'topic').prefetch_related(
        'options'
    )


def _score_role_question(question: Question):
    return (
        question.discrimination_score,
        -question.display_order,
        -question.id,
    )


def _score_skill_question(session: AssessmentSession, question: Question):
    topic = question.topic
    if topic is None:
        return (
            0.0,
            question.discrimination_score,
            -question.display_order,
            -question.id,
        )

    mastery = session.mastery_scores.filter(topic=topic).first()
    confidence_gap = 1.0 - (mastery.confidence_score if mastery else UNANSWERED_TOPIC_CONFIDENCE)
    mastery_gap = 1.0 - (mastery.mastery_score if mastery else 0.0)
    prerequisite_penalty = 0.0 if _topic_prerequisites_satisfied(session, topic) else -1.0
    answered_for_topic = session.answers.filter(question__topic=topic).count()

    return (
        prerequisite_penalty,
        confidence_gap,
        mastery_gap,
        question.discrimination_score,
        -answered_for_topic,
        -question.display_order,
        -question.id,
    )


def _topic_prerequisites_satisfied(session: AssessmentSession, topic) -> bool:
    mastery_scores = {mastery.topic_id: mastery.mastery_score for mastery in session.mastery_scores.all()}
    return all(
        mastery_scores.get(prerequisite.prerequisite_id, 0.0) >= prerequisite.required_mastery_threshold
        for prerequisite in topic.prerequisites.all()
    )
