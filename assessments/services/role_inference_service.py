"""Django-backed adapter over the pure scoring service."""

from assessments.models import AssessmentSession
from roadmaps.models import Question, Role

from . import scoring_service


def _active_role_questions():
    return Question.objects.filter(stage=Question.Stage.ROLE, is_active=True)


def _get_answered_role_question_count(session: AssessmentSession) -> int:
    return session.answers.filter(question__stage=Question.Stage.ROLE).count()


def answer_to_signal_dict(answer) -> dict:
    question = answer.question
    return {
        'agree_dimension_signals': question.agree_dimension_signals or {},
        'disagree_dimension_signals': question.disagree_dimension_signals or {},
        'trait_positive_dimension': question.trait_positive_dimension,
        'scale_value': answer.scale_value,
    }


def question_to_pick_dict(question: Question) -> dict:
    return {
        'id': question.id,
        'code': question.code,
        'display_order': question.display_order,
        'agree_dimension_signals': question.agree_dimension_signals or {},
        'disagree_dimension_signals': question.disagree_dimension_signals or {},
    }


def _build_role_evidence_snapshot(session: AssessmentSession) -> scoring_service.RoleEvidenceSnapshot:
    answers = session.answers.filter(question__stage=Question.Stage.ROLE).select_related('question')
    answer_dicts = [
        answer_to_signal_dict(answer)
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
    ranked_roles = list(Role.objects.filter(is_active=True, slug__in=[slug for slug, _score in sorted_scores]))
    role_names = {role.slug: role.name for role in ranked_roles}
    role_names_th = {role.slug: role.name_th for role in ranked_roles if role.name_th}
    return scoring_service.build_role_inference_snapshot(
        evidence_snapshot,
        active_role_slugs=active_role_slugs,
        role_names=role_names,
        role_names_th=role_names_th,
        answered_questions=_get_answered_role_question_count(session),
        available_questions=_active_role_questions().count(),
    )


def is_role_discovery_complete(session: AssessmentSession, *, snapshot: dict[str, object] | None = None) -> bool:
    snapshot = snapshot or get_role_inference_snapshot(session)
    return bool(snapshot['is_complete'])


def get_next_role_question(session: AssessmentSession, *, snapshot: dict[str, object] | None = None) -> Question | None:
    snapshot = snapshot or get_role_inference_snapshot(session)
    if snapshot['is_complete']:
        return None
    answered_question_ids = session.answers.values_list('question_id', flat=True)
    unanswered = list(_active_role_questions().exclude(id__in=answered_question_ids))
    by_id = {question.id: question for question in unanswered}
    chosen = scoring_service.select_next_role_question([question_to_pick_dict(question) for question in unanswered], snapshot)
    return by_id[chosen['id']] if chosen else None


def get_role_resolution_status(session: AssessmentSession, *, snapshot: dict[str, object] | None = None) -> str:
    snapshot = snapshot or get_role_inference_snapshot(session)
    return scoring_service.get_role_resolution_status(
        is_complete=bool(snapshot['is_complete']),
        best_fit_role_slug=session.best_fit_role.slug if session.best_fit_role_id else None,
        score_margin=float(snapshot['score_margin']),
    )
