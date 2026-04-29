import logging
import math
from collections import defaultdict
from dataclasses import dataclass

from django.conf import settings
from django.db import transaction
from django.db.models import Prefetch, Q
from django.utils import timezone

from recommendations.models import Recommendation
from roadmaps.models import Question, Role
from roadmaps.questionnaire import ROLE_DIMENSION_LABELS, ROLE_PROFILE_WEIGHTS, ROLE_TRAIT_AXES
from roadmaps.serializers import QuestionSerializer

from .models import Answer, AssessmentSession, QuestionBanditStat, QuestionSelectionEvent, TopicMastery


logger = logging.getLogger(__name__)


SKILL_QUESTION_TARGET = 3
RECOMMENDATION_MASTERY_THRESHOLD = 0.7
UNANSWERED_TOPIC_CONFIDENCE = 0.0
MAX_GAP_TOPICS = 3
ROLE_DISCOVERY_CONFIDENCE_THRESHOLD = 0.45
ROLE_DISCOVERY_MIN_MARGIN = 0.08
ROLE_DISCOVERY_MAX_ENTROPY = 0.82
ROLE_DISCOVERY_CORE_QUESTION_TARGET = 30
ROLE_DISCOVERY_MIN_QUESTIONS = ROLE_DISCOVERY_CORE_QUESTION_TARGET
ROLE_DISCOVERY_MIN_OBSERVED_PILLARS = len(ROLE_TRAIT_AXES)
MIN_TIE_BREAK_ROLE_COUNT = 2
ROLE_TIE_BREAK_CLUSTER_SIZE = 3
ROLE_SELECTION_POLICY_INFO_GAIN = QuestionSelectionEvent.PolicyMode.INFO_GAIN
DEFAULT_ROLE_PRIOR_WEIGHT = 0.01
ROLE_SCORE_SOFTMAX_TEMPERATURE = 10.0
ROLE_DIRECT_SIGNAL_WEIGHT = 0.35
LOG_TOP_ROLE_COUNT = 3
LOG_TOP_QUESTION_COUNT = 3
SUPPORTED_POLICY_MODES = {
    QuestionSelectionEvent.PolicyMode.HEURISTIC,
    QuestionSelectionEvent.PolicyMode.CORE_SEQUENCE,
    QuestionSelectionEvent.PolicyMode.INFO_GAIN,
    QuestionSelectionEvent.PolicyMode.SHADOW_BANDIT,
    QuestionSelectionEvent.PolicyMode.LIVE_BANDIT,
}


@dataclass(frozen=True)
class QuestionSelectionDecision:
    stage: str
    policy_mode: str
    candidates: list[Question]
    chosen_question: Question
    heuristic_question: Question
    bandit_question: Question
    candidate_scores: list[dict[str, object]]
    selection_score: float | None
    pre_selection_uncertainty: float


@dataclass(frozen=True)
class RoleEvidenceSnapshot:
    role_scores: dict[str, float]
    legacy_role_scores: dict[str, float]
    dimension_scores: dict[str, float]
    dimension_evidence_counts: dict[str, int]
    uses_dimension_scoring: bool


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
    if session.phase == AssessmentSession.Phase.ROLE_AMBIGUITY:
        return None

    base_queryset = _get_unanswered_questions(session)
    if session.phase == AssessmentSession.Phase.ROLE_DISCOVERY:
        candidates = _get_selectable_role_candidates(session, list(base_queryset.filter(stage=Question.Stage.ROLE)))
        if candidates:
            decision = _select_question_for_session(session, candidates, stage=Question.Stage.ROLE)
            _ensure_selection_event(session, decision)
            return decision.chosen_question
        return None

    target_role = get_skill_target_role(session)
    if target_role is not None:
        candidates = list(
            base_queryset.filter(stage=Question.Stage.SKILL)
            .filter(Q(role__isnull=True) | Q(role=target_role))
            .filter(Q(topic__isnull=True) | Q(topic__role=target_role))
        )
        if candidates:
            decision = _select_question_for_session(session, candidates, stage=Question.Stage.SKILL)
            _ensure_selection_event(session, decision)
            return decision.chosen_question
    return None


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
    selection_event = _get_pending_selection_event(session, expected_question)
    if selection_event is None:
        selection_event = _ensure_selection_event(
            session,
            _select_question_for_session(session, _get_candidates_for_stage(session, question.stage), stage=question.stage),
        )

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
    _finalize_selection_event(selection_event, session=session, question=question)
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


def _get_answered_core_role_question_count(session: AssessmentSession) -> int:
    return session.answers.filter(question__stage=Question.Stage.ROLE, question__item_group=Question.ItemGroup.CORE).count()


def _get_answered_tie_break_question_count(session: AssessmentSession) -> int:
    return session.answers.filter(question__stage=Question.Stage.ROLE, question__item_group=Question.ItemGroup.TIE_BREAK).count()


def _is_core_role_profile_complete(session: AssessmentSession) -> bool:
    return _get_answered_core_role_question_count(session) >= ROLE_DISCOVERY_CORE_QUESTION_TARGET


def get_current_question_data(session: AssessmentSession):
    question = get_current_question(session)
    if question is None:
        return None

    return QuestionSerializer(question).data


def build_session_state(session: AssessmentSession) -> dict[str, object]:
    role_profile_complete = _is_core_role_profile_complete(session)
    return {
        'id': session.id,
        'status': session.status,
        'phase': session.phase,
        'best_fit_confidence': session.best_fit_confidence if role_profile_complete else 0.0,
        'preferred_role': session.preferred_role,
        'best_fit_role': session.best_fit_role if role_profile_complete else None,
        'profile': session.profile,
        'started_at': session.started_at,
        'updated_at': session.updated_at,
        'completed_at': session.completed_at,
        'milestones': serialize_milestones(session),
        'role_alignment_status': get_role_alignment_status(session),
        'role_resolution_status': get_role_resolution_status(session),
        'guidance_summary': build_guidance_summary(session),
        'current_question': get_current_question_data(session),
    }


def get_role_insights(session: AssessmentSession) -> dict[str, object]:
    snapshot = _get_role_inference_snapshot(session)
    if not _is_core_role_profile_complete(session):
        return {
            'role_resolution_status': 'in_progress',
            'best_fit_role': None,
            'best_fit_confidence': 0.0,
            'answered_role_questions': serialize_milestones(session)['answered_role_questions'],
            'pillar_profile': snapshot['pillar_profile'],
            'ranked_roles': [],
            'guidance_summary': build_guidance_summary(session),
        }
    return {
        'role_resolution_status': get_role_resolution_status(session),
        'best_fit_role': session.best_fit_role,
        'best_fit_confidence': session.best_fit_confidence,
        'answered_role_questions': serialize_milestones(session)['answered_role_questions'],
        'pillar_profile': snapshot['pillar_profile'],
        'ranked_roles': snapshot['ranked_roles'],
        'guidance_summary': build_guidance_summary(session),
    }


def get_skill_target_role(session: AssessmentSession):
    if not _is_role_inference_resolved(session):
        return session.preferred_role if session.preferred_role_id is not None else None
    return session.preferred_role or session.best_fit_role


def get_role_alignment_status(session: AssessmentSession) -> str:
    if not _is_core_role_profile_complete(session):
        return 'unknown'
    if get_role_resolution_status(session) == 'ambiguous':
        return 'ambiguous'
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
    if not _is_core_role_profile_complete(session):
        return (
            f'You want to pursue {session.preferred_role.name}. Complete the role-discovery profile to compare fit.'
            if session.preferred_role_id is not None
            else 'Complete the role-discovery profile to identify the best-fit roadmap.'
        )

    alignment_status = get_role_alignment_status(session)
    preferred_role = session.preferred_role
    best_fit_role = session.best_fit_role
    role_snapshot = get_top_role_candidates(session)
    gap_topics = get_preferred_role_gap_topics(session)
    gap_names = ', '.join(topic.title for topic in gap_topics)

    resolution_status = get_role_resolution_status(session)
    if resolution_status == 'ambiguous':
        candidate_names = ' and '.join(candidate['name'] for candidate in role_snapshot[:2])
        return f'Your answers are not confident enough to separate {candidate_names} yet.'

    if preferred_role is None and best_fit_role is None:
        return 'Answer the role-discovery questions to identify the best-fit roadmap.'

    if preferred_role is not None and best_fit_role is None:
        return f'You want to pursue {preferred_role.name}. Answer the role-discovery questions to see how close your current fit is.'

    if preferred_role is None and best_fit_role is not None:
        base_message = f'Your current answers align best with {best_fit_role.name}.'
    elif alignment_status == 'aligned':
        base_message = f'You are tracking well toward {preferred_role.name}.'
    else:
        base_message = f'Your current answers look closer to {best_fit_role.name}, but you can still pursue {preferred_role.name}.'

    if gap_names:
        return f'{base_message} Focus next on {gap_names}.'
    return base_message


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
    snapshot = _get_role_inference_snapshot(session)
    role_scores = {candidate['slug']: candidate['fit_score'] for candidate in snapshot['ranked_roles']}

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

    sorted_scores = _get_sorted_role_scores(role_scores)
    top_slug, _top_score = sorted_scores[0]
    session.best_fit_role = Role.objects.filter(slug=top_slug, is_active=True).first()
    session.best_fit_confidence = float(snapshot['confidence'])
    session.save(update_fields=['best_fit_role', 'best_fit_confidence', 'updated_at'])
    logger.info(
        (
            'assessment.best_fit_recomputed session_id=%s role=%s confidence=%.4f share=%.4f '
            'margin=%.4f entropy=%.4f pillars=%s top=%s dims=%s failed_gates=%s'
        ),
        session.id,
        session.best_fit_role.slug if session.best_fit_role else None,
        session.best_fit_confidence,
        float(snapshot['winner_share']),
        float(snapshot['margin_share']),
        float(snapshot['entropy']),
        int(snapshot['observed_pillars']),
        _format_top_roles(snapshot['ranked_roles']),
        _format_dimension_scores(snapshot),
        _format_failed_resolution_gates(session, snapshot),
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
    has_remaining_role_questions = _has_remaining_role_questions(session)
    if not _is_role_inference_resolved(session) and has_remaining_role_questions:
        session.phase = AssessmentSession.Phase.ROLE_DISCOVERY
        session.status = AssessmentSession.Status.IN_PROGRESS
        session.completed_at = None
        session.save(update_fields=['phase', 'status', 'completed_at', 'updated_at'])
        logger.info(
            (
                'assessment.phase_updated session_id=%s previous_phase=%s new_phase=%s '
                'previous_status=%s new_status=%s role_confidence=%.4f has_role_questions=%s completed_at=%s'
            ),
            session.id,
            previous_phase,
            session.phase,
            previous_status,
            session.status,
            session.best_fit_confidence,
            has_remaining_role_questions,
            session.completed_at.isoformat() if session.completed_at else None,
        )
        return
    if not _is_role_inference_resolved(session):
        if session.preferred_role_id is not None:
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
                    'previous_status=%s new_status=%s role_confidence=%.4f has_role_questions=%s completed_at=%s'
                ),
                session.id,
                previous_phase,
                session.phase,
                previous_status,
                session.status,
                session.best_fit_confidence,
                has_remaining_role_questions,
                session.completed_at.isoformat() if session.completed_at else None,
            )
            return
        session.phase = AssessmentSession.Phase.ROLE_AMBIGUITY
        session.status = AssessmentSession.Status.IN_PROGRESS
        session.completed_at = None
        session.save(update_fields=['phase', 'status', 'completed_at', 'updated_at'])
        logger.info(
            (
                'assessment.phase_updated session_id=%s previous_phase=%s new_phase=%s '
                'previous_status=%s new_status=%s role_confidence=%.4f has_role_questions=%s completed_at=%s'
            ),
            session.id,
            previous_phase,
            session.phase,
            previous_status,
            session.status,
            session.best_fit_confidence,
            has_remaining_role_questions,
            session.completed_at.isoformat() if session.completed_at else None,
        )
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
            'previous_status=%s new_status=%s role_confidence=%.4f '
            'has_skill_questions=%s completed_at=%s'
        ),
        session.id,
        previous_phase,
        session.phase,
        previous_status,
        session.status,
        session.best_fit_confidence,
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
    return (
        Question.objects.filter(is_active=True)
        .exclude(id__in=answered_question_ids)
        .select_related('role', 'topic')
        .prefetch_related('options__role_signals__role', 'options__topic_signals__topic', 'topic__prerequisites')
    )


def _get_policy_mode() -> str:
    configured_mode = getattr(settings, 'ASSESSMENT_BANDIT_POLICY_MODE', QuestionSelectionEvent.PolicyMode.SHADOW_BANDIT)
    if configured_mode not in SUPPORTED_POLICY_MODES:
        return QuestionSelectionEvent.PolicyMode.SHADOW_BANDIT
    return configured_mode


def _select_question_for_session(session: AssessmentSession, candidates: list[Question], *, stage: str) -> QuestionSelectionDecision:
    heuristic_question = max(candidates, key=lambda question: _get_heuristic_score(session, question))
    candidate_scores: list[dict[str, object]] = []
    selection_score: float | None = None

    if stage == Question.Stage.ROLE:
        role_question, candidate_scores = _select_role_info_gain_question(session, candidates)
        policy_mode = ROLE_SELECTION_POLICY_INFO_GAIN
        chosen_question = role_question
        bandit_question = role_question
        selection_score = next(
            (float(candidate['selection_score']) for candidate in candidate_scores if candidate['question_id'] == chosen_question.id),
            None,
        )
    else:
        bandit_question = _select_bandit_question(session, candidates, stage=stage)
        policy_mode = _get_policy_mode()
        chosen_question = bandit_question if policy_mode == QuestionSelectionEvent.PolicyMode.LIVE_BANDIT else heuristic_question
        for question in candidates:
            heuristic_score = _get_heuristic_score(session, question)
            if question.id == chosen_question.id:
                selection_score = float(_compute_ucb_score_for_question(question, stage=stage))
            candidate_scores.append(
                {
                    'question_id': question.id,
                    'question_code': question.code,
                    'policy_score': float(_compute_ucb_score_for_question(question, stage=stage)),
                    'selection_score': float(_compute_ucb_score_for_question(question, stage=stage)),
                    'heuristic_score': list(heuristic_score),
                }
            )

    return QuestionSelectionDecision(
        stage=stage,
        policy_mode=policy_mode,
        candidates=candidates,
        chosen_question=chosen_question,
        heuristic_question=heuristic_question,
        bandit_question=bandit_question,
        candidate_scores=candidate_scores,
        selection_score=selection_score,
        pre_selection_uncertainty=_calculate_stage_uncertainty(session, stage),
    )


def _format_top_roles(ranked_roles: list[dict[str, object]], *, limit: int = LOG_TOP_ROLE_COUNT) -> list[dict[str, object]]:
    return [
        {
            'slug': role['slug'],
            'score': round(float(role['fit_score']), 4),
            'share': round(float(role['fit_share']), 4),
        }
        for role in ranked_roles[:limit]
    ]


def _format_dimension_scores(snapshot: dict[str, object]) -> dict[str, float]:
    return {key: round(float(value), 2) for key, value in sorted(snapshot['dimension_scores'].items()) if float(value) > 0}


def _format_failed_resolution_gates(session: AssessmentSession, snapshot: dict[str, object]) -> list[str]:
    if snapshot['top_role_slug'] is not None and int(snapshot['answered_core_questions']) >= ROLE_DISCOVERY_CORE_QUESTION_TARGET:
        return []
    uses_dimension_scoring = bool(snapshot['uses_dimension_scoring'])
    common_gates = {
        'top_role_exists': snapshot['top_role_slug'] is not None,
        'answered_core_questions': int(snapshot['answered_core_questions']) >= ROLE_DISCOVERY_CORE_QUESTION_TARGET,
        'confidence_met': float(snapshot['confidence']) >= ROLE_DISCOVERY_CONFIDENCE_THRESHOLD,
        'margin_met': float(snapshot['margin_share']) >= ROLE_DISCOVERY_MIN_MARGIN,
    }
    if not uses_dimension_scoring:
        return [gate_name.removesuffix('_met') for gate_name, passed in common_gates.items() if not passed]
    gates = {
        **common_gates,
        'observed_pillars_met': int(snapshot['observed_pillars']) >= ROLE_DISCOVERY_MIN_OBSERVED_PILLARS,
        'entropy_met': float(snapshot['entropy']) <= ROLE_DISCOVERY_MAX_ENTROPY,
    }
    return [gate_name.removesuffix('_met') for gate_name, passed in gates.items() if not passed]


def _format_top_question_scores(candidate_scores: list[dict[str, object]], *, limit: int = LOG_TOP_QUESTION_COUNT) -> list[dict[str, object]]:
    sorted_scores = sorted(
        candidate_scores,
        key=lambda candidate: (
            -float(candidate.get('selection_score') or 0.0),
            candidate.get('question_code') or '',
        ),
    )
    formatted = []
    for candidate in sorted_scores[:limit]:
        formatted_candidate = {
            'code': candidate['question_code'],
            'selection': round(float(candidate.get('selection_score') or 0.0), 4),
        }
        if 'expected_entropy' in candidate:
            formatted_candidate['expected_entropy'] = round(float(candidate['expected_entropy']), 4)
        formatted.append(formatted_candidate)
    return formatted


def _select_bandit_question(session: AssessmentSession, candidates: list[Question], *, stage: str) -> Question:
    candidate_ids = [question.id for question in candidates]
    stats_by_question_id = {stat.question_id: stat for stat in QuestionBanditStat.objects.filter(stage=stage, question_id__in=candidate_ids)}
    total_stage_pulls = sum(stat.pulls for stat in QuestionBanditStat.objects.filter(stage=stage).only('pulls'))
    unseen_candidates = [
        question for question in candidates if stats_by_question_id.get(question.id) is None or stats_by_question_id[question.id].pulls == 0
    ]
    if unseen_candidates:
        return max(unseen_candidates, key=lambda question: _get_heuristic_score(session, question))

    return max(
        candidates,
        key=lambda question: (
            _compute_ucb_score(stats_by_question_id[question.id], total_stage_pulls),
            _get_heuristic_score(session, question),
        ),
    )


def _compute_ucb_score_for_question(question: Question, *, stage: str) -> float:
    stat = QuestionBanditStat.objects.filter(stage=stage, question=question).first()
    if stat is None:
        return 1.0
    total_stage_pulls = sum(stage_stat.pulls for stage_stat in QuestionBanditStat.objects.filter(stage=stage).only('pulls'))
    return _compute_ucb_score(stat, total_stage_pulls)


def _compute_ucb_score(stat: QuestionBanditStat, total_stage_pulls: int) -> float:
    if stat.pulls == 0:
        return 1.0
    safe_total_stage_pulls = max(total_stage_pulls, 1)
    return stat.mean_reward + math.sqrt(2.0 * math.log(safe_total_stage_pulls) / stat.pulls)


def _ensure_selection_event(session: AssessmentSession, decision: QuestionSelectionDecision) -> QuestionSelectionEvent:
    existing_event = _get_pending_selection_event(session, decision.chosen_question)
    if existing_event is not None:
        return existing_event

    event = QuestionSelectionEvent.objects.create(
        session=session,
        stage=decision.stage,
        policy_mode=decision.policy_mode,
        chosen_question=decision.chosen_question,
        heuristic_question=decision.heuristic_question,
        shadow_bandit_question=decision.bandit_question if decision.policy_mode != QuestionSelectionEvent.PolicyMode.HEURISTIC else None,
        candidate_question_ids=[question.id for question in decision.candidates],
        candidate_question_codes=[question.code for question in decision.candidates],
        candidate_scores=decision.candidate_scores,
        selection_score=decision.selection_score,
        pre_selection_uncertainty=decision.pre_selection_uncertainty,
    )
    logger.info(
        ('assessment.question_selected session_id=%s stage=%s chosen=%s candidates=%s score=%s uncertainty=%.4f top_candidates=%s'),
        session.id,
        decision.stage,
        decision.chosen_question.code,
        len(decision.candidates),
        f'{decision.selection_score:.4f}' if decision.selection_score is not None else 'n/a',
        decision.pre_selection_uncertainty,
        _format_top_question_scores(decision.candidate_scores),
    )
    return event


def _get_pending_selection_event(session: AssessmentSession, question: Question):
    return (
        QuestionSelectionEvent.objects.filter(
            session=session,
            chosen_question=question,
            answered_at__isnull=True,
        )
        .order_by('-selected_at')
        .first()
    )


def _finalize_selection_event(selection_event: QuestionSelectionEvent, *, session: AssessmentSession, question: Question) -> None:
    post_answer_uncertainty = _calculate_stage_uncertainty(session, question.stage)
    reward = max(0.0, min(1.0, selection_event.pre_selection_uncertainty - post_answer_uncertainty))
    answered_at = timezone.now()
    selection_event.post_answer_uncertainty = post_answer_uncertainty
    selection_event.reward = reward
    selection_event.answered_at = answered_at
    selection_event.save(update_fields=['post_answer_uncertainty', 'reward', 'answered_at'])

    if selection_event.stage == Question.Stage.ROLE:
        logger.info(
            ('assessment.role_selection_evaluated session_id=%s stage=%s question_code=%s reward=%.4f post_answer_uncertainty=%.4f'),
            session.id,
            selection_event.stage,
            question.code,
            reward,
            post_answer_uncertainty,
        )
        return

    stat, _created = QuestionBanditStat.objects.get_or_create(
        question=selection_event.chosen_question,
        stage=selection_event.stage,
        defaults={
            'pulls': 0,
            'cumulative_reward': 0.0,
            'mean_reward': 0.0,
        },
    )
    stat.pulls += 1
    stat.cumulative_reward += reward
    stat.mean_reward = stat.cumulative_reward / stat.pulls
    stat.last_selected_at = answered_at
    stat.save(update_fields=['pulls', 'cumulative_reward', 'mean_reward', 'last_selected_at'])
    logger.info(
        (
            'assessment.bandit_reward_recorded session_id=%s stage=%s question_code=%s reward=%.4f '
            'post_answer_uncertainty=%.4f pulls=%s mean_reward=%.4f'
        ),
        session.id,
        selection_event.stage,
        question.code,
        reward,
        post_answer_uncertainty,
        stat.pulls,
        stat.mean_reward,
    )


def _calculate_stage_uncertainty(session: AssessmentSession, stage: str) -> float:
    if stage == Question.Stage.ROLE:
        return _calculate_role_uncertainty(session)
    return _calculate_skill_uncertainty(session)


def _calculate_role_uncertainty(session: AssessmentSession) -> float:
    active_role_slugs = list(Role.objects.filter(is_active=True).values_list('slug', flat=True))
    if len(active_role_slugs) <= 1:
        return 0.0
    role_distribution = _compute_role_distribution(session)
    return _normalize_entropy(role_distribution, active_role_slugs)


def _calculate_skill_uncertainty(session: AssessmentSession) -> float:
    target_role = get_skill_target_role(session)
    if target_role is None:
        return 1.0
    topics = list(target_role.topics.filter(is_active=True))
    if not topics:
        return 0.0
    mastery_by_topic_id = {mastery.topic_id: mastery for mastery in session.mastery_scores.all()}
    return sum(1.0 - mastery_by_topic_id.get(topic.id, _EmptyMastery()).confidence_score for topic in topics) / len(topics)


class _EmptyMastery:
    confidence_score = 0.0


def _compute_role_distribution(session: AssessmentSession) -> dict[str, float]:
    active_role_slugs = list(Role.objects.filter(is_active=True).values_list('slug', flat=True))
    return _build_role_distribution(_build_role_evidence_snapshot(session).role_scores, active_role_slugs)


def _compute_role_scores(session: AssessmentSession) -> dict[str, float]:
    return _build_role_evidence_snapshot(session).role_scores


def _build_role_evidence_snapshot(session: AssessmentSession) -> RoleEvidenceSnapshot:
    answers = (
        session.answers.filter(question__stage=Question.Stage.ROLE)
        .select_related('selected_option')
        .prefetch_related('selected_option__role_signals__role')
    )
    legacy_role_scores = defaultdict(float)
    dimension_scores = defaultdict(float)
    dimension_evidence_counts = defaultdict(int)
    uses_dimension_scoring = False
    for answer in answers:
        for signal in answer.selected_option.role_signals.all():
            legacy_role_scores[signal.role.slug] += max(float(signal.weight), 0.0)
        option_dimension_signals = answer.selected_option.dimension_signals or {}
        if option_dimension_signals:
            uses_dimension_scoring = True
            for dimension_key, weight in option_dimension_signals.items():
                dimension_scores[dimension_key] += max(float(weight), 0.0)
                dimension_evidence_counts[dimension_key] += 1

    role_scores = (
        _combine_dimension_and_direct_role_scores(dict(dimension_scores), dict(legacy_role_scores))
        if uses_dimension_scoring
        else dict(legacy_role_scores)
    )
    return RoleEvidenceSnapshot(
        role_scores=role_scores,
        legacy_role_scores=dict(legacy_role_scores),
        dimension_scores=dict(dimension_scores),
        dimension_evidence_counts=dict(dimension_evidence_counts),
        uses_dimension_scoring=uses_dimension_scoring,
    )


def _score_roles_from_dimensions(dimension_scores: dict[str, float]) -> dict[str, float]:
    if not dimension_scores:
        return {}

    observed_axis_profile, observed_axis_weights = _build_axis_profile(dimension_scores)
    if not observed_axis_profile:
        return {}

    role_scores: dict[str, float] = {}
    for role_slug, profile in ROLE_PROFILE_WEIGHTS.items():
        role_axis_profile, role_axis_weights = _build_axis_profile(profile)
        if not role_axis_profile:
            role_scores[role_slug] = 0.0
            continue
        weighted_similarity = 0.0
        total_axis_weight = 0.0
        for axis_key, role_balance in role_axis_profile.items():
            if axis_key not in observed_axis_profile:
                continue
            axis_weight = role_axis_weights.get(axis_key, 0.0) * observed_axis_weights.get(axis_key, 0.0)
            if axis_weight <= 0:
                continue
            weighted_similarity += axis_weight * (1.0 - abs(observed_axis_profile[axis_key] - role_balance))
            total_axis_weight += axis_weight
        role_scores[role_slug] = weighted_similarity / total_axis_weight if total_axis_weight > 0 else 0.0
    return role_scores


def _build_axis_profile(weights: dict[str, float]) -> tuple[dict[str, float], dict[str, float]]:
    axis_profile: dict[str, float] = {}
    axis_weights: dict[str, float] = {}
    for left_endpoint, right_endpoint in ROLE_TRAIT_AXES:
        left_weight = max(float(weights.get(left_endpoint, 0.0)), 0.0)
        right_weight = max(float(weights.get(right_endpoint, 0.0)), 0.0)
        total_weight = left_weight + right_weight
        if total_weight <= 0:
            continue
        axis_key = f'{left_endpoint}:{right_endpoint}'
        axis_profile[axis_key] = left_weight / total_weight
        axis_weights[axis_key] = total_weight
    return axis_profile, axis_weights


def _combine_dimension_and_direct_role_scores(
    dimension_scores: dict[str, float],
    direct_role_scores: dict[str, float],
) -> dict[str, float]:
    role_scores = _score_roles_from_dimensions(dimension_scores)
    if not direct_role_scores:
        return role_scores

    max_direct_score = max((max(float(score), 0.0) for score in direct_role_scores.values()), default=0.0)
    if max_direct_score <= 0:
        return role_scores

    for role_slug, direct_score in direct_role_scores.items():
        role_scores[role_slug] = role_scores.get(role_slug, 0.0) + (ROLE_DIRECT_SIGNAL_WEIGHT * max(float(direct_score), 0.0) / max_direct_score)
    return role_scores


def _normalize_weight_map(weights: dict[str, float]) -> dict[str, float]:
    positive_weights = {key: max(float(value), 0.0) for key, value in weights.items() if max(float(value), 0.0) > 0.0}
    total = sum(positive_weights.values())
    if total <= 0:
        return {}
    return {key: value / total for key, value in positive_weights.items()}


def _get_sorted_role_scores(role_scores: dict[str, float]) -> list[tuple[str, float]]:
    return sorted(role_scores.items(), key=lambda item: (-item[1], item[0]))


def _has_remaining_role_questions(session: AssessmentSession) -> bool:
    unanswered_role_questions = list(
        Question.objects.filter(stage=Question.Stage.ROLE, is_active=True).exclude(id__in=session.answers.values_list('question_id', flat=True))
    )
    return bool(_get_selectable_role_candidates(session, unanswered_role_questions))


def _get_role_inference_snapshot(session: AssessmentSession) -> dict[str, object]:
    evidence_snapshot = _build_role_evidence_snapshot(session)
    role_scores = evidence_snapshot.role_scores
    sorted_scores = _get_sorted_role_scores(role_scores)
    role_distribution = _build_role_distribution(role_scores, list(ROLE_PROFILE_WEIGHTS))
    top_slug, top_score = sorted_scores[0] if sorted_scores else (None, 0.0)
    runner_up_score = sorted_scores[1][1] if len(sorted_scores) > 1 else 0.0
    winner_share = role_distribution.get(top_slug, 0.0) if top_slug else 0.0
    margin_share = ((top_score - runner_up_score) / top_score) if top_score > 0 else 0.0
    entropy = _normalize_entropy(role_distribution, list(ROLE_PROFILE_WEIGHTS))
    answered_core_questions = _get_answered_core_role_question_count(session)
    evidence_factor = min(1.0, answered_core_questions / max(ROLE_DISCOVERY_CORE_QUESTION_TARGET, 1))
    if evidence_snapshot.uses_dimension_scoring:
        profile_complete = answered_core_questions >= ROLE_DISCOVERY_CORE_QUESTION_TARGET
        if profile_complete:
            confidence = max(0.0, min(1.0, 0.35 + (0.65 * min(1.0, margin_share / 0.25))))
        else:
            confidence = max(
                0.0,
                min(
                    1.0,
                    (((1.0 - entropy) * 0.35) + (winner_share * 0.35) + (margin_share * 0.30)) * evidence_factor,
                ),
            )
    else:
        confidence = max(0.0, min(1.0, ((winner_share * 0.7) + (margin_share * 0.3)) * evidence_factor))
    total_dimension_score = sum(max(score, 0.0) for score in evidence_snapshot.dimension_scores.values())
    pillar_profile = [
        {
            'key': dimension_key,
            'label': ROLE_DIMENSION_LABELS.get(dimension_key, dimension_key.replace('_', ' ').title()),
            'raw_score': raw_score,
            'normalized_score': (raw_score / total_dimension_score) if total_dimension_score else 0.0,
            'evidence_count': evidence_snapshot.dimension_evidence_counts.get(dimension_key, 0),
        }
        for dimension_key, raw_score in sorted(
            evidence_snapshot.dimension_scores.items(),
            key=lambda item: (-item[1], item[0]),
        )
        if raw_score > 0
    ]
    role_names = {role.slug: role.name for role in Role.objects.filter(is_active=True, slug__in=[slug for slug, _score in sorted_scores])}
    ranked_roles = [
        {
            'slug': role_slug,
            'name': role_names.get(role_slug, role_slug),
            'fit_score': score,
            'fit_share': role_distribution.get(role_slug, 0.0),
            'top_supporting_pillars': _get_top_supporting_pillars(role_slug, evidence_snapshot.dimension_scores),
        }
        for role_slug, score in sorted_scores
        if score > 0
    ]
    return {
        'sorted_scores': sorted_scores,
        'top_role_slug': top_slug,
        'winner_share': winner_share,
        'margin_share': margin_share,
        'entropy': entropy,
        'evidence_factor': evidence_factor,
        'confidence': confidence,
        'uses_dimension_scoring': evidence_snapshot.uses_dimension_scoring,
        'dimension_scores': evidence_snapshot.dimension_scores,
        'dimension_evidence_counts': evidence_snapshot.dimension_evidence_counts,
        'observed_pillars': sum(1 for score in evidence_snapshot.dimension_scores.values() if score > 0),
        'answered_core_questions': answered_core_questions,
        'answered_tie_break_questions': _get_answered_tie_break_question_count(session),
        'pillar_profile': pillar_profile,
        'ranked_roles': ranked_roles,
    }


def _is_role_inference_resolved(session: AssessmentSession) -> bool:
    snapshot = _get_role_inference_snapshot(session)
    if snapshot['top_role_slug'] is None:
        return False
    return int(snapshot['answered_core_questions']) >= ROLE_DISCOVERY_CORE_QUESTION_TARGET


def get_role_resolution_status(session: AssessmentSession) -> str:
    if not _is_core_role_profile_complete(session):
        return 'in_progress'
    if session.best_fit_role_id is None:
        return 'unknown'
    if _is_role_inference_resolved(session):
        return 'resolved'
    if _has_remaining_role_questions(session):
        return 'in_progress'
    return 'ambiguous'


def get_top_role_candidates(session: AssessmentSession, *, limit: int = 3) -> list[dict[str, object]]:
    snapshot = _get_role_inference_snapshot(session)
    return [
        {
            'slug': role['slug'],
            'name': role['name'],
            'score': role['fit_score'],
            'share': role['fit_share'],
        }
        for role in snapshot['ranked_roles'][:limit]
    ]


def _build_role_distribution(role_scores: dict[str, float], active_role_slugs: list[str]) -> dict[str, float]:
    if not active_role_slugs:
        return {}

    non_negative_scores = {role_slug: max(float(role_scores.get(role_slug, 0.0)), 0.0) for role_slug in active_role_slugs}
    max_score = max(non_negative_scores.values(), default=0.0)
    if max_score <= 0:
        uniform_probability = 1.0 / len(active_role_slugs)
        return dict.fromkeys(active_role_slugs, uniform_probability)

    # Role scores are similarities, not additive evidence counts. Softmax gives
    # entropy and winner share a useful contrast without discarding weaker roles.
    adjusted_scores = {
        role_slug: math.exp((score - max_score) * ROLE_SCORE_SOFTMAX_TEMPERATURE) + DEFAULT_ROLE_PRIOR_WEIGHT
        for role_slug, score in non_negative_scores.items()
    }
    total = sum(adjusted_scores.values())
    if total <= 0:
        uniform_probability = 1.0 / len(active_role_slugs)
        return dict.fromkeys(active_role_slugs, uniform_probability)
    return {role_slug: score / total for role_slug, score in adjusted_scores.items()}


def _normalize_entropy(distribution: dict[str, float], active_role_slugs: list[str]) -> float:
    if len(active_role_slugs) <= 1:
        return 0.0
    if not distribution:
        return 1.0
    entropy = -sum(probability * math.log(probability) for probability in distribution.values() if probability > 0)
    return min(1.0, entropy / math.log(len(active_role_slugs)))


def _is_role_resolution_exhausted_with_viable_winner(
    session: AssessmentSession,
    *,
    snapshot: dict[str, object] | None = None,
) -> bool:
    snapshot = snapshot or _get_role_inference_snapshot(session)
    if snapshot['top_role_slug'] is None:
        return False
    if int(snapshot['answered_core_questions']) < ROLE_DISCOVERY_CORE_QUESTION_TARGET:
        return False
    return (
        float(snapshot['confidence']) >= ROLE_DISCOVERY_CONFIDENCE_THRESHOLD
        and float(snapshot['margin_share']) >= ROLE_DISCOVERY_MIN_MARGIN
        and float(snapshot['entropy']) <= ROLE_DISCOVERY_MAX_ENTROPY
    )


def _select_role_info_gain_question(session: AssessmentSession, candidates: list[Question]) -> tuple[Question, list[dict[str, object]]]:
    if _get_answered_core_role_question_count(session) < ROLE_DISCOVERY_CORE_QUESTION_TARGET:
        ordered_core_candidates = sorted(
            [question for question in candidates if question.item_group == Question.ItemGroup.CORE],
            key=lambda question: (question.display_order, question.id),
        )
        if ordered_core_candidates:
            return (
                ordered_core_candidates[0],
                [
                    {
                        'question_id': question.id,
                        'question_code': question.code,
                        'policy_score': 0.0,
                        'selection_score': float(ROLE_DISCOVERY_CORE_QUESTION_TARGET - question.display_order),
                        'heuristic_score': list(_get_heuristic_score(session, question)),
                    }
                    for question in ordered_core_candidates
                ],
            )

    eligible_candidates = sorted(candidates, key=lambda question: (question.display_order, question.id))
    if not eligible_candidates:
        msg = 'No role questions are selectable for this session.'
        raise AssessmentFlowError(msg)

    active_role_slugs = list(Role.objects.filter(is_active=True).values_list('slug', flat=True))
    current_distribution = _compute_role_distribution(session)
    current_entropy = _normalize_entropy(current_distribution, active_role_slugs)
    evidence_snapshot = _build_role_evidence_snapshot(session)
    coverage_snapshot = evidence_snapshot.dimension_evidence_counts
    scored_candidates: list[dict[str, object]] = []

    for question in eligible_candidates:
        expected_entropy = _calculate_expected_role_entropy(question, current_distribution, evidence_snapshot, active_role_slugs)
        expected_information_gain = max(0.0, current_entropy - expected_entropy)
        coverage_bonus = _calculate_coverage_bonus(question, coverage_snapshot)
        discrimination_prior = min(1.0, max(float(question.discrimination_score), 0.0) / 5.0)
        selection_score = expected_information_gain + (0.2 * coverage_bonus) + (0.05 * discrimination_prior)
        heuristic_score = _get_heuristic_score(session, question)
        scored_candidates.append(
            {
                'question_id': question.id,
                'question_code': question.code,
                'policy_score': expected_information_gain,
                'selection_score': selection_score,
                'heuristic_score': list(heuristic_score),
                'expected_entropy': expected_entropy,
                'coverage_bonus': coverage_bonus,
            }
        )

    chosen_candidate = max(
        scored_candidates,
        key=lambda candidate: (
            float(candidate['selection_score']),
            tuple(candidate['heuristic_score']),
        ),
    )
    return (
        next(question for question in eligible_candidates if question.id == chosen_candidate['question_id']),
        scored_candidates,
    )


def _calculate_expected_role_entropy(
    question: Question,
    current_distribution: dict[str, float],
    evidence_snapshot: RoleEvidenceSnapshot,
    active_role_slugs: list[str],
) -> float:
    options = list(question.options.all())
    if not options:
        return 1.0

    option_probabilities = _estimate_role_option_probabilities(options, current_distribution, active_role_slugs)
    expected_entropy = 0.0
    for option in options:
        option_probability = option_probabilities.get(option.id, 0.0)
        if option_probability <= 0:
            continue
        projected_scores = _project_role_scores_for_option(evidence_snapshot, option)
        projected_distribution = _build_role_distribution(projected_scores, active_role_slugs)
        expected_entropy += option_probability * _normalize_entropy(projected_distribution, active_role_slugs)
    return expected_entropy


def _estimate_role_option_probabilities(
    options: list,
    current_distribution: dict[str, float],
    active_role_slugs: list[str],
) -> dict[int, float]:
    if not options:
        return {}

    option_role_weights, role_weight_totals = _build_option_role_weights(options, active_role_slugs)

    option_probabilities = {option.id: 0.0 for option in options}
    for role_slug in active_role_slugs:
        role_probability = current_distribution.get(role_slug, 0.0)
        if role_probability <= 0:
            continue
        total_role_weight = role_weight_totals.get(role_slug, 0.0)
        if total_role_weight <= 0:
            for option in options:
                option_probabilities[option.id] += role_probability / len(options)
            continue
        for option in options:
            option_probabilities[option.id] += role_probability * (option_role_weights[option.id].get(role_slug, 0.0) / total_role_weight)

    total_probability = sum(option_probabilities.values())
    if total_probability <= 0:
        uniform_probability = 1.0 / len(options)
        return {option.id: uniform_probability for option in options}
    return {option_id: probability / total_probability for option_id, probability in option_probabilities.items()}


def _build_option_role_weights(options: list, active_role_slugs: list[str]) -> tuple[dict[int, dict[str, float]], dict[str, float]]:
    option_role_weights: dict[int, dict[str, float]] = {}
    role_weight_totals = dict.fromkeys(active_role_slugs, 0.0)
    for option in options:
        signal_weights = _get_option_role_weights(option)
        for role_slug, weight in signal_weights.items():
            role_weight_totals[role_slug] = role_weight_totals.get(role_slug, 0.0) + max(float(weight), 0.0)
        option_role_weights[option.id] = signal_weights
    return option_role_weights, role_weight_totals


def _get_option_role_weights(option) -> dict[str, float]:
    signal_weights = defaultdict(float)
    if option.dimension_signals:
        for role_slug, weight in _score_roles_from_dimensions(option.dimension_signals).items():
            signal_weights[role_slug] += max(float(weight), 0.0)
        return dict(signal_weights)

    for signal in option.role_signals.all():
        weight = max(float(signal.weight), 0.0)
        signal_weights[signal.role.slug] += weight
    return dict(signal_weights)


def _calculate_coverage_bonus(question: Question, dimension_evidence_counts: dict[str, int]) -> float:
    dimension_keys = {dimension_key for option in question.options.all() for dimension_key in (option.dimension_signals or {})}
    if not dimension_keys:
        return 0.0
    coverage_scores = [1.0 / (1.0 + float(dimension_evidence_counts.get(dimension_key, 0))) for dimension_key in dimension_keys]
    return sum(coverage_scores) / len(coverage_scores)


def _get_top_supporting_pillars(role_slug: str, dimension_scores: dict[str, float], *, limit: int = 3) -> list[str]:
    profile = ROLE_PROFILE_WEIGHTS.get(role_slug, {})
    weighted_dimensions = [
        (
            ROLE_DIMENSION_LABELS.get(dimension_key, dimension_key.replace('_', ' ').title()),
            max(float(profile_weight), 0.0) * max(float(dimension_scores.get(dimension_key, 0.0)), 0.0),
        )
        for dimension_key, profile_weight in profile.items()
    ]
    return [label for label, weighted_score in sorted(weighted_dimensions, key=lambda item: (-item[1], item[0]))[:limit] if weighted_score > 0]


def _project_role_scores_for_option(evidence_snapshot: RoleEvidenceSnapshot, option) -> dict[str, float]:
    if evidence_snapshot.uses_dimension_scoring and option.dimension_signals:
        projected_dimension_scores = dict(evidence_snapshot.dimension_scores)
        for dimension_key, weight in option.dimension_signals.items():
            projected_dimension_scores[dimension_key] = max(projected_dimension_scores.get(dimension_key, 0.0), 0.0) + max(float(weight), 0.0)
        projected_direct_scores = dict(evidence_snapshot.legacy_role_scores)
        for signal in option.role_signals.all():
            projected_direct_scores[signal.role.slug] = max(projected_direct_scores.get(signal.role.slug, 0.0), 0.0) + max(float(signal.weight), 0.0)
        return _combine_dimension_and_direct_role_scores(projected_dimension_scores, projected_direct_scores)

    projected_scores = dict(evidence_snapshot.legacy_role_scores)
    for signal in option.role_signals.all():
        projected_scores[signal.role.slug] = max(projected_scores.get(signal.role.slug, 0.0), 0.0) + max(float(signal.weight), 0.0)
    return projected_scores


def _get_role_tie_break_candidates(
    session: AssessmentSession,
    candidates: list[Question],
    *,
    snapshot: dict[str, object] | None = None,
) -> list[Question]:
    return []


def _get_selectable_role_candidates(
    session: AssessmentSession,
    candidates: list[Question],
    *,
    snapshot: dict[str, object] | None = None,
) -> list[Question]:
    snapshot = snapshot or _get_role_inference_snapshot(session)
    if int(snapshot['answered_core_questions']) < ROLE_DISCOVERY_CORE_QUESTION_TARGET:
        core_candidates = [question for question in candidates if question.item_group == Question.ItemGroup.CORE]
        return sorted(core_candidates, key=lambda question: (question.display_order, question.id))
    return []


def _get_candidates_for_stage(session: AssessmentSession, stage: str) -> list[Question]:
    base_queryset = _get_unanswered_questions(session)
    if stage == Question.Stage.ROLE:
        return _get_selectable_role_candidates(session, list(base_queryset.filter(stage=Question.Stage.ROLE)))

    target_role = get_skill_target_role(session)
    if target_role is None:
        return []
    return list(
        base_queryset.filter(stage=Question.Stage.SKILL)
        .filter(Q(role__isnull=True) | Q(role=target_role))
        .filter(Q(topic__isnull=True) | Q(topic__role=target_role))
    )


def _get_heuristic_score(session: AssessmentSession, question: Question):
    if question.stage == Question.Stage.ROLE:
        return _score_role_question(question)
    return _score_skill_question(session, question)


def _score_role_question(question: Question):
    dimension_count = len(question.options.first().dimension_signals) if question.options.exists() else 0
    return (
        dimension_count,
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
