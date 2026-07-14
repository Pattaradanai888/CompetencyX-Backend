"""Characterization tests pinning persisted Q-table state-key formats.

``SkillAssessmentQuestionQValue`` and ``RecommendationQValue`` rows are keyed on these
strings; any format drift silently orphans previously learned values. If one of
these tests fails, either revert the key-builder change or plan a Q-table
migration alongside it.
"""

import pytest

from assessments.models import AssessmentSession
from assessments.services.recommendation_service import _build_recommendation_state_key
from assessments.services.skill_assessment_service import build_skill_assessment_state_key
from recommendations.models import Recommendation
from roadmaps.models import Role


@pytest.mark.django_db
def test_skill_assessment_state_key_format_is_stable():
    session = AssessmentSession.objects.create()

    assert build_skill_assessment_state_key(session, {}) == 'none:unknown:in_progress:avg-2:progress-0'
    assert build_skill_assessment_state_key(session, {'a': 5, 'b': 4}) == 'none:unknown:in_progress:avg-3:progress-0'


@pytest.mark.django_db
def test_skill_assessment_state_key_uses_preferred_role_slug():
    role = Role.objects.create(slug='backend-developer', name='Backend Developer')
    session = AssessmentSession.objects.create(preferred_role=role)

    key = build_skill_assessment_state_key(session, {'a': 3, 'b': 3, 'c': 3})
    assert key == 'backend-developer:unknown:in_progress:avg-2:progress-1'


@pytest.mark.django_db
def test_recommendation_state_key_format_is_stable():
    role = Role.objects.create(slug='backend-developer', name='Backend Developer')
    session = AssessmentSession.objects.create(preferred_role=role)

    key = _build_recommendation_state_key(
        session,
        role=role,
        path_kind=Recommendation.PathKind.PREFERRED,
    )
    assert key == 'backend-developer:preferred:unknown:in_progress:confidence-0:mastery-0:weak-0'
