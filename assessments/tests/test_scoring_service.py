"""Pure unit tests for the scoring service math (no DB)."""

from assessments.services import scoring_service
from roadmaps.questionnaire import ROLE_PROFILE_WEIGHTS


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
    score = scoring_service.score_dimension_overlap({'construction': 1.0}, backend_profile)
    assert score > 0


def test_score_dimension_overlap_ignores_zero_signal_weight():
    profile = {'construction': 1.0}
    assert scoring_service.score_dimension_overlap({'construction': 0.0}, profile) == 0.0


def test_build_role_shares_uniform_when_no_evidence():
    slugs = ['role-a', 'role-b', 'role-c']
    distribution = scoring_service.build_role_shares({}, slugs)
    assert set(distribution) == set(slugs)
    assert all(abs(value - 1 / 3) < 1e-9 for value in distribution.values())


def test_build_role_shares_concentrates_on_winner():
    slugs = ['role-a', 'role-b']
    distribution = scoring_service.build_role_shares({'role-a': 5.0, 'role-b': 0.0}, slugs)
    assert distribution['role-a'] > distribution['role-b']
    assert distribution['role-a'] > 0.5


def test_compute_role_evidence_snapshot_accumulates_signals():
    answers = [
        {**SAMPLE_QUESTION, 'scale_value': 2},
        {**SAMPLE_QUESTION, 'scale_value': 2},
    ]
    evidence = scoring_service.compute_role_evidence_snapshot(answers)
    assert evidence.dimension_scores['construction'] == 4.0
    assert evidence.dimension_evidence_counts['construction'] == 2
    assert 'backend-developer' in evidence.role_scores


def test_compute_role_evidence_snapshot_neutral_answer_is_no_evidence():
    evidence = scoring_service.compute_role_evidence_snapshot([{**SAMPLE_QUESTION, 'scale_value': 0}])
    assert evidence.dimension_scores == {}


def test_build_role_inference_snapshot_shape():
    evidence = scoring_service.compute_role_evidence_snapshot([{**SAMPLE_QUESTION, 'scale_value': 2}])
    snapshot = scoring_service.build_role_inference_snapshot(
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
    selected = scoring_service.select_role_candidates(questions, snapshot=None)
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
    selected = scoring_service.select_role_candidates(questions, snapshot=snapshot)
    assert [q['id'] for q in selected] == [1, 3]


def test_select_role_candidates_empty_when_margin_already_clear():
    snapshot = {
        'ranked_roles': [{'slug': 'a'}, {'slug': 'b'}],
        'score_margin': scoring_service.ROLE_DISCOVERY_MIN_SCORE_MARGIN + 0.01,
    }
    questions = [{'id': 1, 'item_group': 'tie_break', 'display_order': 1, 'discriminates_between': ['a', 'b']}]
    assert scoring_service.select_role_candidates(questions, snapshot=snapshot) == []


def test_is_role_resolution_gate_requires_all_conditions():
    base_snapshot = {
        'top_role_slug': 'a',
        'answered_core_questions': 46,
        'core_question_target': 46,
        'score_margin': scoring_service.ROLE_DISCOVERY_MIN_SCORE_MARGIN,
    }
    assert scoring_service.is_role_resolution_exhausted_with_viable_winner(base_snapshot, has_remaining_tie_breaks_for_top_pair=False) is True
    assert scoring_service.is_role_resolution_exhausted_with_viable_winner(base_snapshot, has_remaining_tie_breaks_for_top_pair=True) is False

    low_margin = {**base_snapshot, 'score_margin': 0.01}
    assert scoring_service.is_role_resolution_exhausted_with_viable_winner(low_margin, has_remaining_tie_breaks_for_top_pair=False) is False

    no_top_role = {**base_snapshot, 'top_role_slug': None}
    assert scoring_service.is_role_resolution_exhausted_with_viable_winner(no_top_role, has_remaining_tie_breaks_for_top_pair=False) is False
