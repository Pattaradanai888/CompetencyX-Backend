"""Public facade for the assessments service layer.

The implementation is split across focused modules:

* :mod:`assessments.exceptions` -- assessment-flow exceptions.
* :mod:`assessments.guidance` -- role-status and learner-guidance helpers.
* :mod:`assessments.flow` -- session orchestration (create / answer / state).

Everything that historically lived in ``assessments.services`` is re-exported here so
existing imports (``from assessments.services import ...``) keep working unchanged.
"""

from .exceptions import AssessmentFlowError
from .flow import (
    apply_recommendation_feedback_from_survey2,
    build_session_state,
    create_assessment_session,
    get_current_question,
    get_current_question_data,
    submit_answer,
)
from .guidance import (
    MAX_GAP_TOPICS,
    build_guidance_summary,
    get_preferred_role_gap_topics,
    get_role_alignment_status,
    get_role_insights,
    get_skill_target_role,
    serialize_milestones,
)
from .role_inference import get_role_resolution_status


__all__ = [
    'MAX_GAP_TOPICS',
    'AssessmentFlowError',
    'apply_recommendation_feedback_from_survey2',
    'build_guidance_summary',
    'build_session_state',
    'create_assessment_session',
    'get_current_question',
    'get_current_question_data',
    'get_preferred_role_gap_topics',
    'get_role_alignment_status',
    'get_role_insights',
    'get_role_resolution_status',
    'get_skill_target_role',
    'serialize_milestones',
    'submit_answer',
]
