from collections import defaultdict

from django.db import transaction
from django.db.models import Prefetch, Q
from django.utils import timezone

from recommendations.models import Recommendation
from roadmaps.models import Question, Role

from .models import Answer, AssessmentSession, TopicMastery


ROLE_QUESTION_TARGET = 2
SKILL_QUESTION_TARGET = 3
RECOMMENDATION_MASTERY_THRESHOLD = 0.7
UNANSWERED_TOPIC_CONFIDENCE = 0.0


class AssessmentFlowError(ValueError):
    """Raised when the assessment session flow is used incorrectly."""


def create_assessment_session(*, selected_role=None, profile=None) -> AssessmentSession:
    return AssessmentSession.objects.create(
        selected_role=selected_role,
        inferred_role=selected_role,
        role_confidence=1.0 if selected_role else 0.0,
        phase=(AssessmentSession.Phase.SKILL_ASSESSMENT if selected_role else AssessmentSession.Phase.ROLE_DISCOVERY),
        profile=profile or {},
    )


def get_current_question(session: AssessmentSession):
    if session.status == AssessmentSession.Status.COMPLETED:
        return None

    role = _get_active_role(session)
    base_queryset = _get_unanswered_questions(session)
    if session.phase == AssessmentSession.Phase.ROLE_DISCOVERY:
        candidates = list(base_queryset.filter(stage=Question.Stage.ROLE))
        if not candidates:
            return None
        return max(candidates, key=lambda question: _score_role_question(session, question))

    if role is None:
        return None

    candidates = list(
        base_queryset.filter(stage=Question.Stage.SKILL)
        .filter(Q(role__isnull=True) | Q(role=role))
        .filter(Q(topic__isnull=True) | Q(topic__role=role))
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

    _recompute_role_inference(session)
    _recompute_mastery(session)
    _update_phase(session)
    recommendation = refresh_recommendation(session)
    return answer, recommendation


def refresh_recommendation(session: AssessmentSession):
    role = _get_active_role(session)
    if role is None or session.phase != AssessmentSession.Phase.RECOMMENDATION_READY:
        return None

    Recommendation.objects.filter(session=session).delete()
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
                reason=('Lowest-order topic with satisfied prerequisites and insufficient mastery.'),
                policy_type=Recommendation.PolicyType.RULE_BASED,
                score=1.0 - current_mastery,
            )

    return Recommendation.objects.create(
        session=session,
        role=role,
        topic=None,
        reason='No further topic recommendation is available for the current mastery profile.',
        policy_type=Recommendation.PolicyType.RULE_BASED,
        score=0.0,
    )


def serialize_milestones(session: AssessmentSession):
    return {
        'answered_role_questions': session.answers.filter(question__stage=Question.Stage.ROLE).count(),
        'answered_skill_questions': session.answers.filter(question__stage=Question.Stage.SKILL).count(),
    }


def _get_active_role(session: AssessmentSession):
    return session.selected_role or session.inferred_role


def _recompute_role_inference(session: AssessmentSession) -> None:
    if session.selected_role_id:
        session.inferred_role = session.selected_role
        session.role_confidence = 1.0
        session.save(update_fields=['inferred_role', 'role_confidence', 'updated_at'])
        return

    answers = (
        session.answers.filter(question__stage=Question.Stage.ROLE)
        .select_related('selected_option')
        .values_list('selected_option__role_weights', flat=True)
    )
    role_scores = defaultdict(float)
    for role_weight_map in answers:
        for role_slug, weight in role_weight_map.items():
            role_scores[role_slug] += float(weight)

    if not role_scores:
        session.inferred_role = None
        session.role_confidence = 0.0
        session.save(update_fields=['inferred_role', 'role_confidence', 'updated_at'])
        return

    sorted_scores = sorted(role_scores.items(), key=lambda item: item[1], reverse=True)
    top_slug, top_score = sorted_scores[0]
    total = sum(max(score, 0.0) for _, score in sorted_scores)
    session.inferred_role = Role.objects.filter(slug=top_slug, is_active=True).first()
    session.role_confidence = (top_score / total) if total else 0.0
    session.save(update_fields=['inferred_role', 'role_confidence', 'updated_at'])


def _recompute_mastery(session: AssessmentSession) -> None:
    answers = session.answers.filter(question__stage=Question.Stage.SKILL, question__topic__isnull=False).select_related(
        'question__topic', 'selected_option'
    )
    aggregates = defaultdict(lambda: {'weighted_total': 0.0, 'weight': 0.0, 'topic': None})
    for answer in answers:
        topic = answer.question.topic
        weight = max(answer.question.discrimination_score, 1.0)
        aggregates[topic.id]['weighted_total'] += answer.selected_option.mastery_value * weight
        aggregates[topic.id]['weight'] += weight
        aggregates[topic.id]['topic'] = topic

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


def _update_phase(session: AssessmentSession) -> None:
    role_answers = session.answers.filter(question__stage=Question.Stage.ROLE).count()
    next_role_question = (
        Question.objects.filter(stage=Question.Stage.ROLE, is_active=True)
        .exclude(id__in=session.answers.values_list('question_id', flat=True))
        .exists()
    )
    if not session.selected_role_id and session.inferred_role_id is None and role_answers < ROLE_QUESTION_TARGET and next_role_question:
        session.phase = AssessmentSession.Phase.ROLE_DISCOVERY
    else:
        has_remaining_skill_questions = get_current_question_for_role(session)
        if has_remaining_skill_questions:
            session.phase = AssessmentSession.Phase.SKILL_ASSESSMENT
        else:
            session.phase = AssessmentSession.Phase.RECOMMENDATION_READY

    if session.phase == AssessmentSession.Phase.RECOMMENDATION_READY:
        session.status = AssessmentSession.Status.COMPLETED
        session.completed_at = timezone.now()

    session.save(update_fields=['phase', 'status', 'completed_at', 'updated_at'])


def get_current_question_for_role(session: AssessmentSession):
    active_role = _get_active_role(session)
    if active_role is None:
        return None
    return (
        _get_unanswered_questions(session)
        .filter(stage=Question.Stage.SKILL)
        .filter(Q(role__isnull=True) | Q(role=active_role))
        .filter(Q(topic__isnull=True) | Q(topic__role=active_role))
        .exists()
    )


def _get_unanswered_questions(session: AssessmentSession):
    answered_question_ids = session.answers.values_list('question_id', flat=True)
    return Question.objects.filter(is_active=True).exclude(id__in=answered_question_ids).select_related('role', 'topic').prefetch_related('options')


def _score_role_question(_session: AssessmentSession, question: Question):
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
        mastery_scores.get(prerequisite.prerequisite_id, 0.0) >= prerequisite.required_mastery_threshold for prerequisite in topic.prerequisites.all()
    )
