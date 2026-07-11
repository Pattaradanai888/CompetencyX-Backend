"""Django-backed adapter over the pure scoring service."""

from assessments.models import AssessmentSession
from roadmaps.models import Question, Role

from . import scoring_service


def _get_answered_core_role_question_count(session: AssessmentSession) -> int:
    return session.answers.filter(question__stage=Question.Stage.ROLE, question__item_group=Question.ItemGroup.CORE).count()


def _get_active_core_role_question_count() -> int:
    return Question.objects.filter(stage=Question.Stage.ROLE, item_group=Question.ItemGroup.CORE, is_active=True).count()


def _get_answered_tie_break_question_count(session: AssessmentSession) -> int:
    return session.answers.filter(question__stage=Question.Stage.ROLE, question__item_group=Question.ItemGroup.TIE_BREAK).count()


def is_core_role_profile_complete(session: AssessmentSession) -> bool:
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


def _build_role_evidence_snapshot(session: AssessmentSession) -> scoring_service.RoleEvidenceSnapshot:
    answers = session.answers.filter(question__stage=Question.Stage.ROLE).select_related('question')
    answer_dicts = [
        _answer_to_signal_dict(answer)
        for answer in answers
        if answer.question.question_type == Question.Type.LIKERT_5
    ]
    return scoring_service.compute_role_evidence_snapshot(answer_dicts)


def get_role_inference_snapshot(session: AssessmentSession) -> dict[str, object]:
    evidence_snapshot = _build_role_evidence_snapshot(session)
    active_role_slugs = list(Role.objects.filter(is_active=True).values_list('slug', flat=True))
    sorted_scores = scoring_service.get_sorted_role_scores(
        {role_slug: evidence_snapshot.role_scores.get(role_slug, 0.0) for role_slug in active_role_slugs},
    )
    role_names = {
        role.slug: role.name
        for role in Role.objects.filter(is_active=True, slug__in=[slug for slug, _score in sorted_scores])
    }
    return scoring_service.build_role_inference_snapshot(
        evidence_snapshot,
        active_role_slugs=active_role_slugs,
        role_names=role_names,
        answered_core=_get_answered_core_role_question_count(session),
        core_target=_get_active_core_role_question_count(),
        answered_tie_break=_get_answered_tie_break_question_count(session),
    )


def is_role_resolution_exhausted_with_viable_winner(
    session: AssessmentSession,
    *,
    snapshot: dict[str, object] | None = None,
) -> bool:
    snapshot = snapshot or get_role_inference_snapshot(session)
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
    has_remaining_tie_breaks = bool(get_selectable_role_candidates(session, remaining_tie_breaks, snapshot=snapshot))
    return scoring_service.is_role_resolution_exhausted_with_viable_winner(
        snapshot,
        has_remaining_tie_breaks_for_top_pair=has_remaining_tie_breaks,
    )


def is_role_inference_resolved(session: AssessmentSession) -> bool:
    snapshot = get_role_inference_snapshot(session)
    return is_role_resolution_exhausted_with_viable_winner(session, snapshot=snapshot)


def get_role_resolution_status(session: AssessmentSession) -> str:
    is_core_complete = is_core_role_profile_complete(session)
    has_remaining_questions = has_remaining_role_questions(session) if is_core_complete else False
    is_resolved = (
        is_role_resolution_exhausted_with_viable_winner(session)
        if session.best_fit_role_id is not None and is_core_complete
        else False
    )
    return scoring_service.get_role_resolution_status(
        is_core_complete=is_core_complete,
        best_fit_role_slug=session.best_fit_role.slug if session.best_fit_role_id else None,
        is_resolved=is_resolved,
        has_remaining_role_questions=has_remaining_questions,
    )


def has_remaining_role_questions(session: AssessmentSession) -> bool:
    answered_question_ids = session.answers.values_list('question_id', flat=True)
    unanswered_role_questions = list(
        Question.objects.filter(stage=Question.Stage.ROLE, is_active=True).exclude(id__in=answered_question_ids),
    )
    return bool(get_selectable_role_candidates(session, unanswered_role_questions))


def get_selectable_role_candidates(
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

    snapshot = snapshot or get_role_inference_snapshot(session)
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
    selected_dicts = scoring_service.select_role_candidates(candidate_dicts, snapshot)
    return [question_index[question_dict['id']] for question_dict in selected_dicts]
