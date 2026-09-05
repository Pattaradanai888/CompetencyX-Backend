"""Role-status and learner-guidance helpers.

This service is a leaf in the assessments dependency graph: it imports only the
role-inference service and ORM models. The Skill Assessment service can consume it
without importing assessment orchestration and creating a cycle.

The guidance summary is written in the session's language. Its sentences name
roles and the two surveys and nothing else: what to learn next is the Skill
Assessment's answer-derived suggestion, never a fixed list read off the
catalog (ADR-0005).
"""

from django.db.models import Count, Q

from assessments.models import AssessmentSession
from roadmaps.models import Question

from .role_inference_service import (
    get_role_inference_snapshot,
    get_role_resolution_status,
    is_core_role_profile_complete,
)


ROLE_RESULT_AVAILABLE_STATUSES = {'resolved', 'low_confidence'}

# One sentence per situation, in each language. ``{current}``, ``{preferred}``
# and ``{best}`` are role names in that language.
GUIDANCE_TEMPLATES = {
    'en': {
        'incomplete_with_current': (
            'You are currently a {current} and want to pursue {preferred}. '
            'Complete the role-discovery profile to compare your current fit against that target.'
        ),
        'incomplete_with_preferred': 'You want to pursue {preferred}. Complete the role-discovery profile to compare fit.',
        'incomplete': 'Complete the role-discovery profile to identify the best-fit roadmap.',
        'awaiting_with_current': (
            'You are currently a {current} and want to pursue {preferred}. '
            'Answer the role-discovery questions to see how close your current fit is to that target.'
        ),
        'awaiting': 'You want to pursue {preferred}. Answer the role-discovery questions to see how close your current fit is.',
        'no_roles': 'Answer the role-discovery questions to identify the best-fit roadmap.',
        'low_confidence': 'Your answers weakly point toward {best}. Treat this as a tentative fit and validate it in Skill Assessment.',
        'best_fit_only': 'Your current answers align best with {best}.',
        'aligned_with_current': 'You are currently a {current} and are tracking well toward {preferred}.',
        'aligned': 'You are tracking well toward {preferred}.',
        'mismatch_with_current': (
            'Your current answers look closer to {best}, but you can still pursue {preferred} from your current {current} role.'
        ),
        'mismatch': 'Your current answers look closer to {best}, but you can still pursue {preferred}.',
    },
    'th': {
        'incomplete_with_current': (
            'ตอนนี้คุณเป็น {current} และอยากไปทาง {preferred} '
            'ทำแบบสำรวจ Role Discovery ให้ครบเพื่อเทียบความเหมาะสมในปัจจุบันกับเป้าหมายนั้น'
        ),
        'incomplete_with_preferred': 'คุณอยากไปทาง {preferred} ทำแบบสำรวจ Role Discovery ให้ครบเพื่อเทียบความเหมาะสม',
        'incomplete': 'ทำแบบสำรวจ Role Discovery ให้ครบเพื่อหา roadmap ที่เหมาะกับคุณที่สุด',
        'awaiting_with_current': (
            'ตอนนี้คุณเป็น {current} และอยากไปทาง {preferred} '
            'ตอบคำถาม Role Discovery เพื่อดูว่าความเหมาะสมในปัจจุบันใกล้เป้าหมายนั้นแค่ไหน'
        ),
        'awaiting': 'คุณอยากไปทาง {preferred} ตอบคำถาม Role Discovery เพื่อดูว่าความเหมาะสมในปัจจุบันใกล้เป้าหมายแค่ไหน',
        'no_roles': 'ตอบคำถาม Role Discovery เพื่อหา roadmap ที่เหมาะกับคุณที่สุด',
        'low_confidence': 'คำตอบของคุณเอนไปทาง {best} เพียงเล็กน้อย ให้ถือเป็นทิศทางเบื้องต้น แล้วตรวจสอบต่อใน Skill Assessment',
        'best_fit_only': 'คำตอบของคุณตอนนี้สอดคล้องกับ {best} มากที่สุด',
        'aligned_with_current': 'ตอนนี้คุณเป็น {current} และกำลังไปในทิศทางของ {preferred} ได้ดี',
        'aligned': 'คุณกำลังไปในทิศทางของ {preferred} ได้ดี',
        'mismatch_with_current': 'คำตอบของคุณตอนนี้ใกล้เคียง {best} มากกว่า แต่คุณยังไปทาง {preferred} จากบทบาท {current} ในปัจจุบันได้',
        'mismatch': 'คำตอบของคุณตอนนี้ใกล้เคียง {best} มากกว่า แต่คุณยังไปทาง {preferred} ได้',
    },
}


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


def get_role_alignment_status(session: AssessmentSession) -> str:
    if not is_core_role_profile_complete(session):
        return 'unknown'
    if session.best_fit_role_id is None:
        return 'unknown'
    if session.preferred_role_id is None:
        return 'aligned'
    if session.preferred_role_id == session.best_fit_role_id:
        return 'aligned'
    return 'mismatch'


def _language(session: AssessmentSession) -> str:
    return session.language if session.language in GUIDANCE_TEMPLATES else 'en'


def _role_name(role, language: str) -> str:
    """The role as the respondent reads it: its Thai name in a Thai session, when it has one."""
    if role is None:
        return ''
    if language == 'th' and role.name_th:
        return role.name_th
    return role.name


def _say(session: AssessmentSession, key: str) -> str:
    language = _language(session)
    return GUIDANCE_TEMPLATES[language][key].format(
        current=_role_name(session.current_role, language),
        preferred=_role_name(session.preferred_role, language),
        best=_role_name(session.best_fit_role, language),
    )


def _incomplete_profile_summary(session: AssessmentSession) -> str:
    if session.current_role_id is not None and session.preferred_role_id is not None:
        return _say(session, 'incomplete_with_current')
    if session.preferred_role_id is not None:
        return _say(session, 'incomplete_with_preferred')
    return _say(session, 'incomplete')


def _awaiting_best_fit_summary(session: AssessmentSession) -> str:
    if session.current_role_id is not None:
        return _say(session, 'awaiting_with_current')
    return _say(session, 'awaiting')


def _fit_summary(session: AssessmentSession, *, resolution_status: str) -> str:
    if resolution_status == 'low_confidence' and session.best_fit_role_id is not None:
        return _say(session, 'low_confidence')
    if session.preferred_role_id is None and session.best_fit_role_id is not None:
        return _say(session, 'best_fit_only')
    if get_role_alignment_status(session) == 'aligned':
        return _say(session, 'aligned_with_current' if session.current_role_id is not None else 'aligned')
    return _say(session, 'mismatch_with_current' if session.current_role_id is not None else 'mismatch')


def build_guidance_summary(session: AssessmentSession) -> str:
    if not is_core_role_profile_complete(session):
        return _incomplete_profile_summary(session)

    resolution_status = get_role_resolution_status(session)
    if session.preferred_role_id is None and session.best_fit_role_id is None:
        return _say(session, 'no_roles')
    if session.preferred_role_id is not None and session.best_fit_role_id is None:
        return _awaiting_best_fit_summary(session)
    return _fit_summary(session, resolution_status=resolution_status)


def get_visible_role_result(session: AssessmentSession) -> dict[str, object]:
    """Role resolution status plus the best-fit fields masked until a result is available."""
    role_resolution_status = get_role_resolution_status(session)
    role_result_available = role_resolution_status in ROLE_RESULT_AVAILABLE_STATUSES
    return {
        'role_resolution_status': role_resolution_status,
        'best_fit_role': session.best_fit_role if role_result_available else None,
        'best_fit_confidence': session.best_fit_confidence if role_result_available else 0.0,
    }


def get_role_insights(session: AssessmentSession) -> dict[str, object]:
    snapshot = get_role_inference_snapshot(session)
    return {
        **get_visible_role_result(session),
        'answered_role_questions': serialize_milestones(session)['answered_role_questions'],
        'pillar_profile': snapshot['pillar_profile'],
        'ranked_roles': snapshot['ranked_roles'] if is_core_role_profile_complete(session) else [],
        'guidance_summary': build_guidance_summary(session),
    }
