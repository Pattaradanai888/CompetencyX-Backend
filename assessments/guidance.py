"""Role-status and learner-guidance helpers.

This module is intentionally a leaf in the assessments dependency graph: it imports
only from ``role_inference`` and the ORM models. Keeping ``get_role_alignment_status``
and friends here lets ``recommendation_builder`` and ``survey2_adaptive`` consume them
without importing the ``services``/``flow`` orchestration layer, which would create an
import cycle.
"""

from django.db.models import Count, Q

from roadmaps.models import Question

from .models import AssessmentSession
from .role_inference import (
    _get_role_inference_snapshot,
    _is_core_role_profile_complete,
    get_role_resolution_status,
    get_top_role_candidates,
)


MAX_GAP_TOPICS = 3
ROLE_RESULT_AVAILABLE_STATUSES = {'resolved', 'low_confidence'}


def serialize_milestones(session: AssessmentSession):
    role_stage = Q(question__stage=Question.Stage.ROLE)
    return session.answers.aggregate(
        answered_role_questions=Count('pk', filter=role_stage),
        answered_core_role_questions=Count(
            'pk',
            filter=role_stage & Q(question__item_group=Question.ItemGroup.CORE),
        ),
        answered_tie_break_questions=Count(
            'pk',
            filter=role_stage & Q(question__item_group=Question.ItemGroup.TIE_BREAK),
        ),
    )


def get_skill_target_role(session: AssessmentSession):
    if get_role_resolution_status(session) not in ROLE_RESULT_AVAILABLE_STATUSES:
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
    return list(role.topics.filter(is_active=True).order_by('display_order', 'id')[:limit])


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

    if resolution_status == 'low_confidence' and best_fit_role is not None:
        base_message = f'Your answers weakly point toward {best_fit_role.name}. Treat this as a tentative fit and validate it in Survey 2.'
    elif preferred_role is None and best_fit_role is not None:
        base_message = f'Your current answers align best with {best_fit_role.name}.'
    elif alignment_status == 'aligned':
        base_message = f'You are tracking well toward {preferred_role.name}.'
    else:
        base_message = f'Your current answers look closer to {best_fit_role.name}, but you can still pursue {preferred_role.name}.'

    if gap_names:
        return f'{base_message} Focus next on {gap_names}.'
    return base_message


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
    role_resolution_status = get_role_resolution_status(session)
    role_result_available = role_resolution_status in ROLE_RESULT_AVAILABLE_STATUSES
    return {
        'role_resolution_status': role_resolution_status,
        'best_fit_role': session.best_fit_role if role_result_available else None,
        'best_fit_confidence': session.best_fit_confidence if role_result_available else 0.0,
        'answered_role_questions': serialize_milestones(session)['answered_role_questions'],
        'pillar_profile': snapshot['pillar_profile'],
        'ranked_roles': snapshot['ranked_roles'],
        'guidance_summary': build_guidance_summary(session),
    }
