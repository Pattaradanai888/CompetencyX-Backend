"""Django-backed adapter over :mod:`assessments.scoring`: loads ORM rows,
hands plain dicts to the pure scoring functions, re-exports names other modules
already import.
"""

from roadmaps.models import Question, Role

from . import scoring
from .models import AssessmentSession


# Re-exports for backward-compatible imports (flow.py, guidance.py, api/tests.py).
ROLE_DISCOVERY_CONFIDENCE_THRESHOLD = scoring.ROLE_DISCOVERY_CONFIDENCE_THRESHOLD
ROLE_DISCOVERY_MIN_SCORE_MARGIN = scoring.ROLE_DISCOVERY_MIN_SCORE_MARGIN
_build_role_distribution = scoring._build_role_distribution
_get_sorted_role_scores = scoring._get_sorted_role_scores
_score_dimension_overlap = scoring._score_dimension_overlap


def _get_answered_core_role_question_count(session: AssessmentSession) -> int:
    return session.answers.filter(question__stage=Question.Stage.ROLE, question__item_group=Question.ItemGroup.CORE).count()


def _get_active_core_role_question_count() -> int:
    return Question.objects.filter(stage=Question.Stage.ROLE, item_group=Question.ItemGroup.CORE, is_active=True).count()


def _get_answered_tie_break_question_count(session: AssessmentSession) -> int:
    return session.answers.filter(question__stage=Question.Stage.ROLE, question__item_group=Question.ItemGroup.TIE_BREAK).count()


def _is_core_role_profile_complete(session: AssessmentSession) -> bool:
    core_question_count = _get_active_core_role_question_count()
    return core_question_count > 0 and _get_answered_core_role_question_count(session) >= core_question_count


def _answer_to_signal_dict(answer) -> dict:
    question = answer.question
    return {
        'agree_dimension_signals': question.agree_dimension_signals or {},
        'disagree_dimension_signals': question.disagree_dimension_signals or {},
        'trait_positive_dimension': question.trait_positive_dimension,
        'scale_value': answer.scale_value,
    }


def _build_role_evidence_snapshot(session: AssessmentSession) -> scoring.RoleEvidenceSnapshot:
    answers = session.answers.filter(question__stage=Question.Stage.ROLE).select_related('question')
    answer_dicts = [
        _answer_to_signal_dict(answer)
        for answer in answers
        if answer.question.question_type == Question.Type.LIKERT_5
    ]
    return scoring.compute_role_evidence_snapshot(answer_dicts)


def _get_role_inference_snapshot(session: AssessmentSession) -> dict[str, object]:
    evidence_snapshot = _build_role_evidence_snapshot(session)
    active_role_slugs = list(Role.objects.filter(is_active=True).values_list('slug', flat=True))
    sorted_scores = scoring._get_sorted_role_scores(
        {role_slug: evidence_snapshot.role_scores.get(role_slug, 0.0) for role_slug in active_role_slugs},
    )
    role_names = {
        role.slug: role.name
        for role in Role.objects.filter(is_active=True, slug__in=[slug for slug, _score in sorted_scores])
    }
    return scoring.build_role_inference_snapshot(
        evidence_snapshot,
        active_role_slugs=active_role_slugs,
        role_names=role_names,
        answered_core=_get_answered_core_role_question_count(session),
        core_target=_get_active_core_role_question_count(),
        answered_tie_break=_get_answered_tie_break_question_count(session),
    )


def _is_role_resolution_exhausted_with_viable_winner(
    session: AssessmentSession,
    *,
    snapshot: dict[str, object] | None = None,
) -> bool:
    snapshot = snapshot or _get_role_inference_snapshot(session)
    if snapshot['top_role_slug'] is None:
        return False
    if int(snapshot['answered_core_questions']) < int(snapshot['core_question_target']):
        return False

    answered_question_ids = session.answers.values_list('question_id', flat=True)
    remaining_tie_breaks = list(
        Question.objects.filter(
            stage=Question.Stage.ROLE,
            item_group=Question.ItemGroup.TIE_BREAK,
            is_active=True,
        ).exclude(id__in=answered_question_ids),
    )
    has_remaining_tie_breaks = bool(_get_selectable_role_candidates(session, remaining_tie_breaks, snapshot=snapshot))
    return scoring.is_role_resolution_exhausted_with_viable_winner(
        snapshot,
        has_remaining_tie_breaks_for_top_pair=has_remaining_tie_breaks,
    )


def _is_role_inference_resolved(session: AssessmentSession) -> bool:
    snapshot = _get_role_inference_snapshot(session)
    return _is_role_resolution_exhausted_with_viable_winner(session, snapshot=snapshot)


def get_role_resolution_status(session: AssessmentSession) -> str:
    is_core_complete = _is_core_role_profile_complete(session)
    has_remaining_role_questions = _has_remaining_role_questions(session) if is_core_complete else False
    is_resolved = (
        _is_role_resolution_exhausted_with_viable_winner(session)
        if session.best_fit_role_id is not None and is_core_complete
        else False
    )
    return scoring.get_role_resolution_status(
        is_core_complete=is_core_complete,
        best_fit_role_slug=session.best_fit_role.slug if session.best_fit_role_id else None,
        is_resolved=is_resolved,
        has_remaining_role_questions=has_remaining_role_questions,
    )


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


def _has_remaining_role_questions(session: AssessmentSession) -> bool:
    answered_question_ids = session.answers.values_list('question_id', flat=True)
    unanswered_role_questions = list(
        Question.objects.filter(stage=Question.Stage.ROLE, is_active=True).exclude(id__in=answered_question_ids),
    )
    return bool(_get_selectable_role_candidates(session, unanswered_role_questions))


def _get_selectable_role_candidates(
    session: AssessmentSession,
    candidates: list[Question],
    *,
    snapshot: dict[str, object] | None = None,
) -> list[Question]:
    core_candidates = [question for question in candidates if question.item_group == Question.ItemGroup.CORE]
    if core_candidates:
        return sorted(core_candidates, key=lambda question: (question.display_order, question.id))
    if not candidates:
        return []

    snapshot = snapshot or _get_role_inference_snapshot(session)
    question_index = {question.id: question for question in candidates}
    candidate_dicts = [
        {
            'id': question.id,
            'item_group': question.item_group,
            'display_order': question.display_order,
            'discriminates_between': list(question.discriminates_between or []),
        }
        for question in candidates
    ]
    selected_dicts = scoring.select_role_candidates(candidate_dicts, snapshot)
    return [question_index[question_dict['id']] for question_dict in selected_dicts]
