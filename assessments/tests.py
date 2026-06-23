"""Tests for the pure scoring module and the in-memory simulator.

Two concerns:
- Pure unit tests verify :mod:`assessments.scoring` math in isolation (no DB).
- Parity tests seed the full MVP catalog and assert that the pure scoring
  path produces snapshots identical to the DB-backed ``role_inference``
  path. This is the drift detector: if ``scoring`` and ``role_inference``
  ever disagree, these tests fail.
"""

from django.core.management import call_command
from rest_framework.test import APITestCase

from assessments import scoring
from assessments.flow import create_assessment_session, submit_answer
from assessments.role_inference import _get_role_inference_snapshot
from roadmaps.models import Question, Role
from roadmaps.questionnaire import ROLE_PROFILE_WEIGHTS
from simulation.engine import LIKERT_VALUES, aggregate_results, run_single_sample


SAMPLE_QUESTION = {
    'id': 1,
    'item_group': 'core',
    'display_order': 1,
    'discriminates_between': [],
    'agree_dimension_signals': {'construction': 1.0, 'application_build': 0.5},
    'disagree_dimension_signals': {'requirements': 1.0, 'people_product': 0.5},
    'trait_positive_dimension': '',
}


def test_score_dimension_overlap_rewards_aligned_profile():
    backend_profile = ROLE_PROFILE_WEIGHTS['backend-developer']
    score = scoring._score_dimension_overlap({'construction': 1.0}, backend_profile)
    assert score > 0


def test_score_dimension_overlap_ignores_zero_signal_weight():
    profile = {'construction': 1.0}
    assert scoring._score_dimension_overlap({'construction': 0.0}, profile) == 0.0


def test_build_role_shares_uniform_when_no_evidence():
    slugs = ['role-a', 'role-b', 'role-c']
    distribution = scoring._build_role_shares({}, slugs)
    assert set(distribution) == set(slugs)
    assert all(abs(value - 1 / 3) < 1e-9 for value in distribution.values())


def test_build_role_shares_concentrates_on_winner():
    slugs = ['role-a', 'role-b']
    distribution = scoring._build_role_shares({'role-a': 5.0, 'role-b': 0.0}, slugs)
    assert distribution['role-a'] > distribution['role-b']
    assert distribution['role-a'] > 0.5


def test_compute_role_evidence_snapshot_accumulates_signals():
    answers = [
        {**SAMPLE_QUESTION, 'scale_value': 2},
        {**SAMPLE_QUESTION, 'scale_value': 2},
    ]
    evidence = scoring.compute_role_evidence_snapshot(answers)
    assert evidence.dimension_scores['construction'] == 4.0
    assert evidence.dimension_evidence_counts['construction'] == 2
    assert 'backend-developer' in evidence.role_scores


def test_compute_role_evidence_snapshot_neutral_answer_is_no_evidence():
    evidence = scoring.compute_role_evidence_snapshot([{**SAMPLE_QUESTION, 'scale_value': 0}])
    assert evidence.dimension_scores == {}


def test_build_role_inference_snapshot_shape():
    evidence = scoring.compute_role_evidence_snapshot([{**SAMPLE_QUESTION, 'scale_value': 2}])
    snapshot = scoring.build_role_inference_snapshot(
        evidence,
        active_role_slugs=list(ROLE_PROFILE_WEIGHTS),
        role_names={},
        answered_core=1,
        core_target=46,
        answered_tie_break=0,
    )
    assert snapshot['top_role_slug'] is not None
    assert snapshot['answered_core_questions'] == 1
    assert snapshot['core_question_target'] == 46
    assert isinstance(snapshot['ranked_roles'], list)
    assert len(snapshot['ranked_roles']) == len(ROLE_PROFILE_WEIGHTS)
    assert 'fit_share' in snapshot['ranked_roles'][0]


def test_select_role_candidates_returns_core_first():
    questions = [
        {'id': 10, 'item_group': 'tie_break', 'display_order': 1, 'discriminates_between': ['a', 'b']},
        {'id': 5, 'item_group': 'core', 'display_order': 3, 'discriminates_between': []},
        {'id': 6, 'item_group': 'core', 'display_order': 1, 'discriminates_between': []},
    ]
    selected = scoring.select_role_candidates(questions, snapshot=None)
    assert [q['id'] for q in selected] == [6, 5]


def test_select_role_candidates_tie_break_filters_top_pair():
    snapshot = {
        'ranked_roles': [{'slug': 'a'}, {'slug': 'b'}],
        'score_margin': 0.01,
    }
    questions = [
        {'id': 1, 'item_group': 'tie_break', 'display_order': 2, 'discriminates_between': ['a', 'b']},
        {'id': 2, 'item_group': 'tie_break', 'display_order': 1, 'discriminates_between': ['a', 'c']},
        {'id': 3, 'item_group': 'tie_break', 'display_order': 3, 'discriminates_between': ['a', 'b']},
    ]
    selected = scoring.select_role_candidates(questions, snapshot=snapshot)
    assert [q['id'] for q in selected] == [1, 3]


def test_select_role_candidates_empty_when_margin_already_clear():
    snapshot = {
        'ranked_roles': [{'slug': 'a'}, {'slug': 'b'}],
        'score_margin': scoring.ROLE_DISCOVERY_MIN_SCORE_MARGIN + 0.01,
    }
    questions = [{'id': 1, 'item_group': 'tie_break', 'display_order': 1, 'discriminates_between': ['a', 'b']}]
    assert scoring.select_role_candidates(questions, snapshot=snapshot) == []


def test_is_role_resolution_gate_requires_all_conditions():
    base_snapshot = {
        'top_role_slug': 'a',
        'answered_core_questions': 46,
        'core_question_target': 46,
        'score_margin': scoring.ROLE_DISCOVERY_MIN_SCORE_MARGIN,
    }
    assert scoring.is_role_resolution_exhausted_with_viable_winner(base_snapshot, has_remaining_tie_breaks_for_top_pair=False) is True
    assert scoring.is_role_resolution_exhausted_with_viable_winner(base_snapshot, has_remaining_tie_breaks_for_top_pair=True) is False

    low_margin = {**base_snapshot, 'score_margin': 0.01}
    assert scoring.is_role_resolution_exhausted_with_viable_winner(low_margin, has_remaining_tie_breaks_for_top_pair=False) is False

    no_top_role = {**base_snapshot, 'top_role_slug': None}
    assert scoring.is_role_resolution_exhausted_with_viable_winner(no_top_role, has_remaining_tie_breaks_for_top_pair=False) is False


class ScoringParityTests(APITestCase):
    """The drift detector: pure scoring must match the DB-backed path."""

    @classmethod
    def setUpTestData(cls):
        call_command('seed_mvp_content')
        cls.active_role_slugs = list(Role.objects.filter(is_active=True).values_list('slug', flat=True))
        cls.role_names = dict(Role.objects.filter(is_active=True).values_list('slug', 'name'))
        cls.core_target = Question.objects.filter(
            stage=Question.Stage.ROLE,
            item_group=Question.ItemGroup.CORE,
            is_active=True,
        ).count()

    def _build_session_answer_dicts(self, session):
        return [
            {
                'agree_dimension_signals': dict(answer.question.agree_dimension_signals or {}),
                'disagree_dimension_signals': dict(answer.question.disagree_dimension_signals or {}),
                'trait_positive_dimension': answer.question.trait_positive_dimension,
                'scale_value': answer.scale_value,
            }
            for answer in session.answers.select_related('question')
            if answer.question.stage == Question.Stage.ROLE
        ]

    def test_db_snapshot_matches_pure_snapshot(self):
        session = create_assessment_session(profile={})
        likert_questions = list(
            Question.objects.filter(stage=Question.Stage.ROLE, is_active=True).order_by('display_order', 'id'),
        )
        for index, question in enumerate(likert_questions[:12]):
            scale_value = [2, -1, 1, 0, 2, -2, 1, -1, 2, 0, 1, -1][index]
            submit_answer(session=session, question=question, scale_value=scale_value)
            session.refresh_from_db()

        db_snapshot = _get_role_inference_snapshot(session)

        answer_dicts = self._build_session_answer_dicts(session)
        evidence = scoring.compute_role_evidence_snapshot(answer_dicts)
        pure_snapshot = scoring.build_role_inference_snapshot(
            evidence,
            active_role_slugs=self.active_role_slugs,
            role_names=self.role_names,
            answered_core=sum(1 for answer in answer_dicts),
            core_target=self.core_target,
            answered_tie_break=0,
        )

        assert pure_snapshot['top_role_slug'] == db_snapshot['top_role_slug']
        assert abs(float(pure_snapshot['confidence']) - float(db_snapshot['confidence'])) < 1e-9
        assert abs(float(pure_snapshot['margin_share']) - float(db_snapshot['margin_share'])) < 1e-9
        assert abs(float(pure_snapshot['score_margin']) - float(db_snapshot['score_margin'])) < 1e-9
        assert abs(float(pure_snapshot['winner_share']) - float(db_snapshot['winner_share'])) < 1e-9
        assert len(pure_snapshot['ranked_roles']) == len(db_snapshot['ranked_roles'])
        assert pure_snapshot['ranked_roles'][0]['slug'] == db_snapshot['ranked_roles'][0]['slug']

    def test_run_single_sample_returns_consistent_outcome(self):
        questions = [
            {
                'id': question.id,
                'display_order': question.display_order,
                'item_group': question.item_group,
                'discriminates_between': list(question.discriminates_between or []),
                'agree_dimension_signals': dict(question.agree_dimension_signals or {}),
                'disagree_dimension_signals': dict(question.disagree_dimension_signals or {}),
                'trait_positive_dimension': question.trait_positive_dimension,
            }
            for question in Question.objects.filter(stage=Question.Stage.ROLE, is_active=True).order_by('display_order', 'id')
        ]
        fixed_answers = list((LIKERT_VALUES * 10)[:len(questions)])
        result = run_single_sample(
            0,
            questions,
            list(self.active_role_slugs),
            self.role_names,
            self.core_target,
            [],
            fixed_answers,
        )
        assert result['answered_role_questions'] >= self.core_target
        assert result['resolution_status'] in {'resolved', 'low_confidence', 'unknown'}
        assert result['best_fit_role'] is None or result['best_fit_role'] in self.active_role_slugs

    def test_aggregate_results_shape(self):
        questions = []
        results = [
            {
                'sample_index': 0,
                'phase': 'recommendation_ready',
                'status': 'completed',
                'resolution_status': 'resolved',
                'best_fit_role': 'backend-developer',
                'top_ranked_role': 'backend-developer',
        'answered_core_questions': 46,
        'answered_tie_break_questions': 0,
        'answered_role_questions': 46,
                'confidence': 0.5,
                'margin_share': 0.3,
                'score_margin': 4.0,
                'winner_share': 0.6,
            },
        ]
        summary = aggregate_results(
            results,
            samples=1,
            seed=42,
            likert_weights={-2: 0.2, -1: 0.2, 0: 0.2, 1: 0.2, 2: 0.2},
            active_role_slugs=list(self.active_role_slugs),
            prefix_answers=[],
        )
        assert summary['resolved_count'] == 1
        assert summary['resolved_rate'] == 1.0
        assert summary['resolved_roles']['backend-developer'] == 1
        assert 'worst_case_95pct_margin_of_error' in summary
        questions.clear()
