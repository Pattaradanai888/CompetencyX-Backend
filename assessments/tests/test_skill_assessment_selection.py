"""Deterministic behavior of the Skill Assessment question selector.

The selector used to be epsilon-greedy over a learned Q-table. Its reward was
``(answer_value - 1) / 4``, so it learned to ask the items a respondent agrees
with most -- the opposite of what an adaptive questionnaire needs. ADR-0003
replaced it with authored roadmap order.
"""

import pytest

from assessments.models import AssessmentSession, SkillAssessmentQuestion
from assessments.services.skill_assessment_service import select_next_skill_assessment_question


@pytest.fixture
def session_with_questions(db):
    # The reused test DB may carry the seeded catalog; only our two questions
    # should be selectable.
    SkillAssessmentQuestion.objects.update(is_active=False)
    session = AssessmentSession.objects.create()
    SkillAssessmentQuestion.objects.create(question_id='q-beta', prompt='Beta', dimension_key='dim-a', display_order=2)
    SkillAssessmentQuestion.objects.create(question_id='q-alpha', prompt='Alpha', dimension_key='dim-a', display_order=1)
    return session


def test_returns_none_when_everything_is_answered(session_with_questions):
    answers = {'q-alpha': 3, 'q-beta': 4}
    assert select_next_skill_assessment_question(session_with_questions, answers) is None


def test_selects_the_lowest_display_order_unanswered_question(session_with_questions):
    assert select_next_skill_assessment_question(session_with_questions, {})['id'] == 'q-alpha'


def test_skips_questions_that_are_already_answered(session_with_questions):
    assert select_next_skill_assessment_question(session_with_questions, {'q-alpha': 3})['id'] == 'q-beta'


def test_repeated_calls_for_the_same_answers_return_the_same_question(session_with_questions):
    picks = [select_next_skill_assessment_question(session_with_questions, {})['id'] for _ in range(5)]
    assert picks == ['q-alpha'] * 5


def test_ties_on_display_order_break_on_question_id(session_with_questions):
    SkillAssessmentQuestion.objects.filter(question_id='q-beta').update(display_order=1)

    assert select_next_skill_assessment_question(session_with_questions, {})['id'] == 'q-alpha'
