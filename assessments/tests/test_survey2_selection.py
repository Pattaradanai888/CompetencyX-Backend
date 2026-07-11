"""Deterministic behavior of the adaptive Survey 2 question selector."""

import random

import pytest

from assessments.models import AssessmentSession, Survey2Question
from assessments.services.survey2_service import select_next_survey2_question


class _FixedRng:
    """Stub rng with a fixed random() outcome and first-element choice()."""

    def __init__(self, random_value):
        self._random_value = random_value

    def random(self):
        return self._random_value

    def choice(self, sequence):
        return sequence[0]


@pytest.fixture
def session_with_questions(db):
    # The reused test DB may carry the seeded catalog; only our two questions
    # should be selectable.
    Survey2Question.objects.update(is_active=False)
    session = AssessmentSession.objects.create()
    Survey2Question.objects.create(question_id='q-alpha', prompt='Alpha', dimension_key='dim-a', display_order=1)
    Survey2Question.objects.create(question_id='q-beta', prompt='Beta', dimension_key='dim-a', display_order=2)
    return session


def test_returns_none_when_everything_is_answered(session_with_questions):
    answers = {'q-alpha': 3, 'q-beta': 4}
    assert select_next_survey2_question(session_with_questions, answers) is None


def test_greedy_path_is_deterministic(session_with_questions):
    # random() >= epsilon forces the greedy branch; with no learned Q-values the
    # tie-break prefers the highest question id ('q-beta' over 'q-alpha').
    rng = _FixedRng(1.0)
    first = select_next_survey2_question(session_with_questions, {}, rng=rng)
    second = select_next_survey2_question(session_with_questions, {}, rng=rng)
    assert first == second

    remaining = select_next_survey2_question(session_with_questions, {first['id']: 3}, rng=rng)
    assert remaining['id'] != first['id']


def test_exploration_path_uses_injected_rng(session_with_questions):
    rng = _FixedRng(0.0)
    chosen = select_next_survey2_question(session_with_questions, {}, rng=rng)
    assert chosen['id'] == 'q-alpha'


def test_seeded_random_instance_is_reproducible(session_with_questions):
    picks_a = [select_next_survey2_question(session_with_questions, {}, rng=random.Random(42))['id'] for _ in range(5)]  # noqa: S311
    picks_b = [select_next_survey2_question(session_with_questions, {}, rng=random.Random(42))['id'] for _ in range(5)]  # noqa: S311
    assert picks_a == picks_b
