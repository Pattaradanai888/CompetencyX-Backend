"""Assessment session orchestration.

The top layer of the assessments service: it wires together question selection,
role inference, phase transitions, and recommendation refresh.
This is the only assessments module that depends on ``recommendation_builder``.

Survey 1 question selection is deterministic: the next question is always the
first eligible unanswered question ordered by ``display_order``. The adaptive
bandit / info-gain selector and the selection-event log have been removed.
"""

import logging

from django.db import transaction
from django.utils import timezone

from roadmaps.models import Question, Role
from roadmaps.serializers import QuestionSerializer

from . import recommendation_builder
from .exceptions import AssessmentFlowError
from .guidance import (
    build_guidance_summary,
    get_role_alignment_status,
    serialize_milestones,
)
from .models import Answer, AssessmentSession
from .role_inference import (
    ROLE_DISCOVERY_MIN_SCORE_MARGIN,
    _get_role_inference_snapshot,
    _get_selectable_role_candidates,
    _get_sorted_role_scores,
    _has_remaining_role_questions,
    _is_role_inference_resolved,
    _is_role_resolution_exhausted_with_viable_winner,
    get_role_resolution_status,
)


logger = logging.getLogger('assessments.services')


LOG_TOP_ROLE_COUNT = 3


def create_assessment_session(*, preferred_role=None, profile=None, language=AssessmentSession.Language.EN) -> AssessmentSession:
    session = AssessmentSession.objects.create(
        preferred_role=preferred_role,
        best_fit_role=None,
        best_fit_confidence=0.0,
        phase=AssessmentSession.Phase.ROLE_DISCOVERY,
        language=language,
        profile=profile or {},
    )
    logger.info(
        'assessment.session_created session_id=%s preferred_role=%s language=%s profile_keys=%s',
        session.id,
        preferred_role.slug if preferred_role else None,
        language,
        sorted((profile or {}).keys()),
    )
    return session


def get_current_question(session: AssessmentSession):
    if session.status == AssessmentSession.Status.COMPLETED:
        return None
    if session.phase == AssessmentSession.Phase.ROLE_AMBIGUITY:
        return None

    candidates = _eligible_questions_for_session(session)
    return candidates[0] if candidates else None


@transaction.atomic
def submit_answer(  # noqa: PLR0913
    *,
    session: AssessmentSession,
    question: Question,
    option=None,
    scale_value=None,
    response_time_ms=None,
    confidence_indicator='',
):
    logger.info(
        (
            'assessment.answer_submission_received session_id=%s phase=%s '
            'question_id=%s question_code=%s option_id=%s scale_value=%s '
            'response_time_ms=%s confidence_indicator=%s'
        ),
        session.id,
        session.phase,
        question.id,
        question.code,
        option.id if option else None,
        scale_value,
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
            'scale_value': scale_value,
            'response_time_ms': response_time_ms,
            'confidence_indicator': confidence_indicator,
        },
    )
    if not created:
        msg = 'This question has already been answered for the session.'
        raise AssessmentFlowError(msg)

    logger.info(
        'assessment.answer_recorded session_id=%s answer_id=%s question_id=%s question_stage=%s option_key=%s scale_value=%s',
        session.id,
        answer.id,
        question.id,
        question.stage,
        option.key if option else '',
        scale_value,
    )
    _recompute_best_fit_role(session)
    _update_phase(session)
    recommendation_builder.refresh_recommendations(session)
    return answer


def apply_recommendation_feedback_from_survey2(session: AssessmentSession) -> int:
    return recommendation_builder.apply_recommendation_feedback_from_survey2(session)


def get_current_question_data(session: AssessmentSession):
    question = get_current_question(session)
    if question is None:
        return None

    return QuestionSerializer(question, context={'language': session.language}).data


def build_session_state(session: AssessmentSession) -> dict[str, object]:
    role_resolution_status = get_role_resolution_status(session)
    role_result_available = role_resolution_status in {'resolved', 'low_confidence'}
    return {
        'id': session.id,
        'status': session.status,
        'phase': session.phase,
        'language': session.language,
        'best_fit_confidence': session.best_fit_confidence if role_result_available else 0.0,
        'preferred_role': session.preferred_role,
        'best_fit_role': session.best_fit_role if role_result_available else None,
        'profile': session.profile,
        'started_at': session.started_at,
        'updated_at': session.updated_at,
        'completed_at': session.completed_at,
        'milestones': serialize_milestones(session),
        'role_alignment_status': get_role_alignment_status(session),
        'role_resolution_status': role_resolution_status,
        'guidance_summary': build_guidance_summary(session),
        'current_question': get_current_question_data(session),
    }


def _eligible_questions_for_session(session: AssessmentSession) -> list[Question]:
    base_queryset = _get_unanswered_questions(session)
    if session.phase == AssessmentSession.Phase.ROLE_DISCOVERY:
        return _get_selectable_role_candidates(session, list(base_queryset.filter(stage=Question.Stage.ROLE)))
    return []


def _get_unanswered_questions(session: AssessmentSession):
    answered_question_ids = session.answers.values_list('question_id', flat=True)
    return (
        Question.objects.filter(is_active=True)
        .exclude(id__in=answered_question_ids)
        .select_related('role', 'topic')
        .prefetch_related('options__topic_signals__topic', 'topic__prerequisites')
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
            'margin=%.4f pillars=%s top=%s dims=%s failed_gates=%s'
        ),
        session.id,
        session.best_fit_role.slug if session.best_fit_role else None,
        session.best_fit_confidence,
        float(snapshot['winner_share']),
        float(snapshot['margin_share']),
        int(snapshot['observed_pillars']),
        _format_top_roles(snapshot['ranked_roles']),
        _format_dimension_scores(snapshot),
        _format_failed_resolution_gates(session, snapshot),
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
    if _is_role_resolution_exhausted_with_viable_winner(session, snapshot=snapshot):
        return []
    answered_question_ids = session.answers.values_list('question_id', flat=True)
    remaining_tie_breaks = list(
        Question.objects.filter(
            stage=Question.Stage.ROLE,
            item_group=Question.ItemGroup.TIE_BREAK,
            is_active=True,
        ).exclude(id__in=answered_question_ids)
    )
    gates = {
        'top_role_exists': snapshot['top_role_slug'] is not None,
        'answered_core_questions': int(snapshot['answered_core_questions']) >= int(snapshot['core_question_target']),
        'tie_breaks_exhausted': not _get_selectable_role_candidates(session, remaining_tie_breaks, snapshot=snapshot),
        'score_margin': float(snapshot['score_margin']) >= ROLE_DISCOVERY_MIN_SCORE_MARGIN,
    }
    return [name for name, passed in gates.items() if not passed]


def _update_phase(session: AssessmentSession) -> None:
    previous_phase = session.phase
    previous_status = session.status
    has_remaining_role_questions = _has_remaining_role_questions(session)
    if not _is_role_inference_resolved(session):
        if has_remaining_role_questions:
            session.phase = AssessmentSession.Phase.ROLE_DISCOVERY
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

    session.phase = AssessmentSession.Phase.RECOMMENDATION_READY
    session.status = AssessmentSession.Status.COMPLETED
    session.completed_at = timezone.now()

    session.save(update_fields=['phase', 'status', 'completed_at', 'updated_at'])
    logger.info(
        (
            'assessment.phase_updated session_id=%s previous_phase=%s new_phase=%s '
            'previous_status=%s new_status=%s role_confidence=%.4f completed_at=%s'
        ),
        session.id,
        previous_phase,
        session.phase,
        previous_status,
        session.status,
        session.best_fit_confidence,
        session.completed_at.isoformat() if session.completed_at else None,
    )
