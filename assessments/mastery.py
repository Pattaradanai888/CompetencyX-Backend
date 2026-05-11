import logging
from collections import defaultdict

from roadmaps.models import Question

from .models import AssessmentSession, TopicMastery


logger = logging.getLogger('assessments.services')


SKILL_QUESTION_TARGET = 3
UNANSWERED_TOPIC_CONFIDENCE = 0.0


def recompute_mastery(session: AssessmentSession, *, target_role) -> None:
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
        if answer.selected_option is None:
            continue
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


def score_skill_question(session: AssessmentSession, question: Question):
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
    prerequisite_penalty = 0.0 if topic_prerequisites_satisfied(session, topic) else -1.0
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


def topic_prerequisites_satisfied(session: AssessmentSession, topic) -> bool:
    mastery_scores = {mastery.topic_id: mastery.mastery_score for mastery in session.mastery_scores.all()}
    return all(
        mastery_scores.get(prerequisite.prerequisite_id, 0.0) >= prerequisite.required_mastery_threshold for prerequisite in topic.prerequisites.all()
    )
