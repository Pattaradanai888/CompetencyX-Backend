"""Assessment session orchestration.

The top layer of the assessments service: it wires together question selection,
role inference, mastery recomputation, phase transitions, and recommendation refresh.
This is the only assessments module that depends on ``recommendation_builder``.
"""

import logging

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from roadmaps.models import Question, Role
from roadmaps.serializers import QuestionSerializer

from . import recommendation_builder
from .exceptions import AssessmentFlowError
from .guidance import (
    build_guidance_summary,
    get_role_alignment_status,
    get_skill_target_role,
    serialize_milestones,
)
from .mastery import recompute_mastery
from .models import Answer, AssessmentSession
from .role_inference import (
    _get_role_inference_snapshot,
    _get_selectable_role_candidates,
    _get_sorted_role_scores,
    _has_remaining_role_questions,
    _is_role_inference_resolved,
    get_role_resolution_status,
)
from .selection import (
    _ensure_selection_event,
    _finalize_selection_event,
    _format_dimension_scores,
    _format_failed_resolution_gates,
    _format_top_roles,
    _get_candidates_for_stage,
    _get_pending_selection_event,
    _get_unanswered_questions,
    _select_question_for_session,
)


logger = logging.getLogger('assessments.services')


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
    selection_event = _get_pending_selection_event(session, expected_question)
    if selection_event is None:
        candidates = _get_candidates_for_stage(session, question.stage)
        if expected_question.id not in {candidate.id for candidate in candidates}:
            candidates = [*candidates, expected_question]
        selection_event = _ensure_selection_event(
            session,
            _select_question_for_session(session, candidates, stage=question.stage),
        )

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
    recompute_mastery(session, target_role=get_skill_target_role(session))
    _update_phase(session)
    recommendation_builder.refresh_recommendations(session)
    _finalize_selection_event(selection_event, session=session, question=question)
    return answer


def apply_recommendation_feedback_from_survey2(session: AssessmentSession) -> int:
    return recommendation_builder.apply_recommendation_feedback_from_survey2(session)


def get_current_question_data(session: AssessmentSession):
    question = get_current_question(session)
    if question is None:
        return None

    return QuestionSerializer(question, context={'language': session.language}).data


def build_session_state(session: AssessmentSession) -> dict[str, object]:
    role_resolved = _is_role_inference_resolved(session)
    return {
        'id': session.id,
        'status': session.status,
        'phase': session.phase,
        'language': session.language,
        'best_fit_confidence': session.best_fit_confidence if role_resolved else 0.0,
        'preferred_role': session.preferred_role,
        'best_fit_role': session.best_fit_role if role_resolved else None,
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


def _update_phase(session: AssessmentSession) -> None:
    previous_phase = session.phase
    previous_status = session.status
    role_answers_count = session.answers.filter(question__stage=Question.Stage.ROLE).count()
    skip_role_discovery = session.preferred_role_id is not None and role_answers_count == 0
    has_remaining_role_questions = _has_remaining_role_questions(session)
    if not skip_role_discovery and not _is_role_inference_resolved(session):
        session.phase = (
            AssessmentSession.Phase.ROLE_DISCOVERY
            if has_remaining_role_questions
            else AssessmentSession.Phase.ROLE_AMBIGUITY
        )
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
