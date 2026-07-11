"""Pure unit tests for the Django-free Monte Carlo engine.

No DB access: the engine operates on plain question dicts (shaped like
:mod:`simulation.loaders` output) and delegates math to
:mod:`assessments.services.scoring_service`.
"""

from collections import Counter

import pytest

from assessments.services import scoring_service
from simulation.engine import (
    LIKERT_VALUES,
    CatalogContext,
    SimulationConfig,
    _distribution_shape,
    _pre_generate_choices,
    _SampleState,
    _stats,
    aggregate_results,
    run_single_sample,
    run_trial,
)


ACTIVE_ROLE_SLUGS = ['backend-developer', 'frontend-developer']
ROLE_NAMES = {'backend-developer': 'Backend Developer', 'frontend-developer': 'Frontend Developer'}
CORE_TARGET = 2

CORE_QUESTION_BACKEND = {
    'id': 1,
    'display_order': 1,
    'item_group': 'core',
    'discriminates_between': [],
    'agree_dimension_signals': {'server_backend': 1.0, 'construction': 1.0},
    'disagree_dimension_signals': {'web_frontend': 1.0},
    'trait_positive_dimension': '',
}
CORE_QUESTION_PLATFORM = {
    'id': 2,
    'display_order': 2,
    'item_group': 'core',
    'discriminates_between': [],
    'agree_dimension_signals': {'architecture': 1.0, 'operations': 1.0},
    'disagree_dimension_signals': {'web_frontend': 1.0, 'design': 1.0},
    'trait_positive_dimension': '',
}
TIE_BREAK_QUESTION = {
    'id': 3,
    'display_order': 3,
    'item_group': 'tie_break',
    'discriminates_between': ['backend-developer', 'frontend-developer'],
    'agree_dimension_signals': {'server_backend': 1.0},
    'disagree_dimension_signals': {'web_frontend': 1.0},
    'trait_positive_dimension': '',
}
CATALOG = [CORE_QUESTION_BACKEND, CORE_QUESTION_PLATFORM, TIE_BREAK_QUESTION]
CATALOG_CTX = CatalogContext(
    questions=CATALOG,
    active_role_slugs=list(ACTIVE_ROLE_SLUGS),
    role_names=ROLE_NAMES,
    core_target=CORE_TARGET,
)

EXPECTED_SAMPLE_RESULT_KEYS = {
    'sample_index',
    'phase',
    'status',
    'resolution_status',
    'best_fit_role',
    'top_ranked_role',
    'answered_core_questions',
    'answered_tie_break_questions',
    'answered_role_questions',
    'confidence',
    'margin_share',
    'score_margin',
    'winner_share',
}


def _make_result(**overrides) -> dict[str, object]:
    result = {
        'sample_index': 0,
        'phase': 'recommendation_ready',
        'status': 'completed',
        'resolution_status': 'resolved',
        'best_fit_role': 'backend-developer',
        'top_ranked_role': 'backend-developer',
        'answered_core_questions': 2,
        'answered_tie_break_questions': 0,
        'answered_role_questions': 2,
        'confidence': 0.9,
        'margin_share': 0.8,
        'score_margin': 1.5,
        'winner_share': 0.9,
    }
    result.update(overrides)
    return result


# --- _pre_generate_choices ---


def test_pre_generate_choices_same_seed_is_deterministic():
    weights = {-2: 0.1, -1: 0.2, 0: 0.4, 1: 0.2, 2: 0.1}
    first = _pre_generate_choices(5, 10, 3, weights, seed=42)
    second = _pre_generate_choices(5, 10, 3, weights, seed=42)
    assert first == second


def test_pre_generate_choices_shape_and_values():
    weights = {-2: 0.2, -1: 0.2, 0: 0.2, 1: 0.2, 2: 0.2}
    choices = _pre_generate_choices(4, 7, 2, weights, seed=1)
    assert len(choices) == 4
    assert all(len(per_sample) == 5 for per_sample in choices)
    assert all(value in LIKERT_VALUES for per_sample in choices for value in per_sample)


def test_pre_generate_choices_prefix_longer_than_questions_yields_empty():
    weights = {-2: 0.2, -1: 0.2, 0: 0.2, 1: 0.2, 2: 0.2}
    choices = _pre_generate_choices(3, 4, 9, weights, seed=1)
    assert choices == [[], [], []]


def test_pre_generate_choices_degenerate_weights_always_pick_that_value():
    weights = {-2: 0.0, -1: 0.0, 0: 0.0, 1: 0.0, 2: 1.0}
    choices = _pre_generate_choices(3, 6, 0, weights, seed=7)
    assert all(value == 2 for per_sample in choices for value in per_sample)


# --- _SampleState.apply_answer ---


def test_apply_answer_counts_core_and_tie_break_separately():
    state = _SampleState(active_role_slugs=list(ACTIVE_ROLE_SLUGS), role_names=ROLE_NAMES, core_target=CORE_TARGET)
    state.apply_answer(CORE_QUESTION_BACKEND, 1)
    state.apply_answer(TIE_BREAK_QUESTION, 1)
    assert state.answered_core == 1
    assert state.answered_tie_break == 1
    assert state.answered_total == 2
    assert state.answered_question_ids == {1, 3}


def test_apply_answer_accumulates_dimension_and_role_scores():
    state = _SampleState(active_role_slugs=list(ACTIVE_ROLE_SLUGS), role_names=ROLE_NAMES, core_target=CORE_TARGET)
    state.apply_answer(CORE_QUESTION_BACKEND, 2)
    # Agreement selects agree_dimension_signals: weight * |scale_value|.
    assert state.dimension_scores['server_backend'] == 2.0
    assert state.dimension_scores['construction'] == 2.0
    assert state.dimension_evidence_counts['server_backend'] == 1
    # Backend-aligned agreement penalizes frontend more than backend.
    assert state.role_scores['backend-developer'] > state.role_scores['frontend-developer']


def test_apply_answer_disagreement_selects_disagree_signals():
    state = _SampleState(active_role_slugs=list(ACTIVE_ROLE_SLUGS), role_names=ROLE_NAMES, core_target=CORE_TARGET)
    state.apply_answer(CORE_QUESTION_BACKEND, -2)
    assert state.dimension_scores == {'web_frontend': 2.0}
    assert state.role_scores['frontend-developer'] > state.role_scores['backend-developer']


def test_apply_answer_neutral_adds_no_evidence_but_still_counts():
    state = _SampleState(active_role_slugs=list(ACTIVE_ROLE_SLUGS), role_names=ROLE_NAMES, core_target=CORE_TARGET)
    state.apply_answer(CORE_QUESTION_BACKEND, 0)
    assert state.dimension_scores == {}
    assert state.dimension_evidence_counts == {}
    assert state.role_scores['backend-developer'] == 0.0
    assert state.answered_core == 1
    assert state.answered_total == 1


# --- run_single_sample ---


def test_run_single_sample_is_deterministic_for_identical_inputs():
    args = (7, CATALOG_CTX, [2, -1, 1], [])
    assert run_single_sample(*args) == run_single_sample(*args)


def test_run_single_sample_result_has_stable_keys():
    result = run_single_sample(0, CATALOG_CTX, [2, 2, 2], [])
    assert set(result) == EXPECTED_SAMPLE_RESULT_KEYS


def test_run_single_sample_strong_backend_prefix_resolves_without_tie_break():
    result = run_single_sample(0, CATALOG_CTX, [2, 2, 2], [])
    assert result['resolution_status'] == 'resolved'
    assert result['best_fit_role'] == 'backend-developer'
    assert result['top_ranked_role'] == 'backend-developer'
    # Margin clears after the two core questions, so the tie-break is never asked.
    assert result['answered_core_questions'] == 2
    assert result['answered_tie_break_questions'] == 0
    assert result['score_margin'] >= scoring_service.ROLE_DISCOVERY_MIN_SCORE_MARGIN


def test_run_single_sample_all_neutral_prefix_ends_low_confidence():
    result = run_single_sample(0, CATALOG_CTX, [0, 0, 0], [])
    assert result['resolution_status'] == 'low_confidence'
    # Zero margin forces the tie-break question to be consumed too.
    assert result['answered_core_questions'] == 2
    assert result['answered_tie_break_questions'] == 1
    assert result['score_margin'] == 0.0
    assert result['confidence'] == 0.5
    # low_confidence still surfaces the top-ranked role as best fit.
    assert result['best_fit_role'] == result['top_ranked_role']


def test_run_single_sample_falls_back_to_pre_generated_choices_after_prefix():
    from_prefix = run_single_sample(0, CATALOG_CTX, [2, 2], [])
    from_choices = run_single_sample(0, CATALOG_CTX, [], [2, 2, 2])
    assert {key: from_prefix[key] for key in from_prefix if key != 'sample_index'} == {
        key: from_choices[key] for key in from_choices if key != 'sample_index'
    }


# --- aggregate_results ---


def test_aggregate_results_exact_rates_coverage_and_conditional_keys():
    results = [
        _make_result(sample_index=0, best_fit_role='backend-developer'),
        _make_result(sample_index=1, best_fit_role='backend-developer'),
        _make_result(
            sample_index=2,
            resolution_status='low_confidence',
            best_fit_role='frontend-developer',
            top_ranked_role='frontend-developer',
            confidence=0.4,
            margin_share=0.1,
            score_margin=0.2,
            winner_share=0.55,
            answered_role_questions=3,
        ),
        _make_result(
            sample_index=3,
            status='abandoned',
            resolution_status='unknown',
            best_fit_role=None,
            top_ranked_role=None,
            confidence=0.1,
            margin_share=0.0,
            score_margin=0.0,
            winner_share=0.5,
            answered_role_questions=3,
        ),
    ]
    likert_weights = {-2: 0.1, -1: 0.2, 0: 0.4, 1: 0.2, 2: 0.1}
    summary = aggregate_results(
        results,
        catalog=CATALOG_CTX,
        config=SimulationConfig(samples=4, seed=42, likert_weights=likert_weights, prefix_answers=[2, 0]),
    )
    assert summary['samples'] == 4
    assert summary['seed'] == 42
    assert summary['prefix_answers'] == [2, 0]
    assert summary['likert_weights'] == likert_weights
    assert summary['random_answer_values'] == list(LIKERT_VALUES)
    assert summary['active_role_count'] == 2
    assert summary['completed_count'] == 3
    assert summary['completed_rate'] == 0.75
    assert summary['resolved_count'] == 2
    assert summary['resolved_rate'] == 0.5
    assert summary['low_confidence_count'] == 1
    assert summary['low_confidence_rate'] == 0.25
    assert summary['best_fit_role_coverage_count'] == 2
    assert summary['best_fit_role_coverage_rate'] == 1.0
    assert summary['missing_best_fit_roles'] == []
    assert summary['resolved_role_coverage_count'] == 1
    assert summary['resolved_role_coverage_rate'] == 0.5
    assert summary['missing_resolved_roles'] == ['frontend-developer']
    assert summary['resolved_roles'] == {'backend-developer': 2}
    assert summary['low_confidence_roles'] == {'frontend-developer': 1}
    assert summary['answered_role_questions'] == {'mean': 2.5, 'min': 2.0, 'max': 3.0, 'median': 2.5}
    assert summary['worst_case_95pct_margin_of_error'] == round(1.96 * ((0.25 / 4) ** 0.5), 4)
    for key in ('resolved_confidence', 'low_confidence_confidence'):
        assert key in summary


def test_aggregate_results_omits_conditional_sections_when_empty():
    results = [
        _make_result(
            sample_index=0,
            resolution_status='unknown',
            best_fit_role=None,
            top_ranked_role=None,
        ),
    ]
    summary = aggregate_results(
        results,
        catalog=CATALOG_CTX,
        config=SimulationConfig(samples=1, seed=1, likert_weights={-2: 0.2, -1: 0.2, 0: 0.2, 1: 0.2, 2: 0.2}),
    )
    assert summary['resolved_rate'] == 0.0
    assert summary['missing_best_fit_roles'] == sorted(ACTIVE_ROLE_SLUGS)
    for key in ('resolved_confidence', 'resolved_roles', 'low_confidence_confidence', 'low_confidence_roles'):
        assert key not in summary


# --- _stats ---


def test_stats_odd_count_uses_middle_value():
    assert _stats([3.0, 1.0, 2.0]) == {'mean': 2.0, 'min': 1.0, 'max': 3.0, 'median': 2.0}


def test_stats_even_count_averages_middle_pair():
    assert _stats([4.0, 1.0, 3.0, 2.0]) == {'mean': 2.5, 'min': 1.0, 'max': 4.0, 'median': 2.5}


def test_stats_empty_list_returns_zeros():
    assert _stats([]) == {'mean': 0.0, 'min': 0.0, 'max': 0.0, 'median': 0.0}


# --- _distribution_shape ---


def test_distribution_shape_uniform_has_full_entropy():
    shape = _distribution_shape(Counter({'a': 5, 'b': 5}), role_count=2)
    assert shape == {'normalized_entropy': 1.0, 'max_share': 0.5, 'min_seen_share': 0.5}


def test_distribution_shape_single_role_has_zero_entropy_and_max_share_one():
    shape = _distribution_shape(Counter({'a': 10}), role_count=2)
    assert shape == {'normalized_entropy': 0.0, 'max_share': 1.0, 'min_seen_share': 1.0}


def test_distribution_shape_empty_counter_returns_zeros():
    assert _distribution_shape(Counter(), role_count=3) == {'normalized_entropy': 0.0, 'max_share': 0.0, 'min_seen_share': 0.0}


def test_distribution_shape_single_role_universe_pins_entropy_to_one():
    shape = _distribution_shape(Counter({'a': 4}), role_count=1)
    assert shape['normalized_entropy'] == 1.0


# --- run_trial ---


def test_run_trial_restores_scoring_constants_after_success():
    original_margin = scoring_service.ROLE_DISCOVERY_MIN_SCORE_MARGIN
    original_logistic = scoring_service.ROLE_EVIDENCE_LOGISTIC_SCALE
    original_score_scale = scoring_service.ROLE_EVIDENCE_SCORE_SCALE
    trial = run_trial(
        trial_id=1,
        params={
            'ROLE_DISCOVERY_MIN_SCORE_MARGIN': 999.0,
            'ROLE_EVIDENCE_LOGISTIC_SCALE': 0.5,
            'ROLE_EVIDENCE_SCORE_SCALE': 1.0,
        },
        catalog=CATALOG_CTX,
        config=SimulationConfig(samples=2, seed=42, likert_weights={-2: 0.1, -1: 0.2, 0: 0.4, 1: 0.2, 2: 0.1}, metric='resolved_rate'),
        pre_generated_choices=[[2, 2, 2], [0, 0, 0]],
    )
    assert original_margin == scoring_service.ROLE_DISCOVERY_MIN_SCORE_MARGIN
    assert original_logistic == scoring_service.ROLE_EVIDENCE_LOGISTIC_SCALE
    assert original_score_scale == scoring_service.ROLE_EVIDENCE_SCORE_SCALE
    assert trial['trial_id'] == 1
    assert trial['metric'] == 'resolved_rate'
    # An impossible margin threshold means nothing resolves.
    assert trial['resolved_rate'] == 0.0
    assert trial['metric_value'] == 0.0


def test_run_trial_restores_scoring_constants_after_exception():
    original_margin = scoring_service.ROLE_DISCOVERY_MIN_SCORE_MARGIN
    with pytest.raises(IndexError):
        run_trial(
            trial_id=2,
            params={'ROLE_DISCOVERY_MIN_SCORE_MARGIN': 999.0},
            catalog=CATALOG_CTX,
            config=SimulationConfig(samples=1, seed=42, likert_weights={-2: 0.2, -1: 0.2, 0: 0.2, 1: 0.2, 2: 0.2}),
            pre_generated_choices=[[]],  # No choices available -> IndexError mid-sample.
        )
    assert original_margin == scoring_service.ROLE_DISCOVERY_MIN_SCORE_MARGIN
