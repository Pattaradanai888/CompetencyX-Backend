"""Unit tests for the Django-free persona-fidelity harness."""

import random

from simulation.engine import CatalogContext
from simulation.personas import (
    compare_to_baseline,
    compute_content_digest,
    ideal_scale_value,
    run_persona_sample,
    run_persona_suite,
    sample_noisy_answer,
)
from simulation.realistic_personas import PARAMS, make_persona, run_realistic_suite


def _make_catalog():
    # Two synthetic roles distinguished by construction-vs-requirements votes.
    questions = [
        {
            'id': 1,
            'code': 'role-rd-test-build',
            'display_order': 1,
            'item_group': 'core',
            'discriminates_between': [],
            'agree_dimension_signals': {'construction': 1.0},
            'disagree_dimension_signals': {'requirements': 1.0},
            'trait_positive_dimension': 'construction',
        },
        {
            'id': 2,
            'code': 'role-rd-test-run',
            'display_order': 2,
            'item_group': 'core',
            'discriminates_between': [],
            'agree_dimension_signals': {'operations': 1.0},
            'disagree_dimension_signals': {'people_product': 1.0},
            'trait_positive_dimension': 'operations',
        },
    ]
    return CatalogContext(
        questions=questions,
        active_role_slugs=['backend-developer', 'ux-designer'],
        role_names={'backend-developer': 'Backend', 'ux-designer': 'UX'},
        available_questions=2,
    )


def test_ideal_scale_value_follows_profile_side():
    question = {
        'agree_dimension_signals': {'construction': 1.0},
        'disagree_dimension_signals': {'requirements': 1.0},
    }
    assert ideal_scale_value(question, {'construction': 1.0}) == 2
    assert ideal_scale_value(question, {'requirements': 1.0}) == -2
    assert ideal_scale_value(question, {'testing': 1.0}) == 0


def test_sample_noisy_answer_is_deterministic_per_seed():
    picks_a = [sample_noisy_answer(2, random.Random(7)) for _ in range(10)]
    picks_b = [sample_noisy_answer(2, random.Random(7)) for _ in range(10)]
    assert picks_a == picks_b


def test_zero_noise_persona_recovers_its_role():
    catalog = _make_catalog()
    exact_noise = {2: ((2,), (1.0,)), 0: ((0,), (1.0,)), -2: ((-2,), (1.0,))}
    sample = run_persona_sample('backend-developer', catalog, random.Random(1), noise_model=exact_noise)
    assert sample['true_role'] == 'backend-developer'
    assert sample['correct'] is True
    assert sample['answered_total'] == 2


def test_run_persona_suite_reports_expected_shape_and_determinism():
    catalog = _make_catalog()
    summary_a = run_persona_suite(catalog, samples_per_role=5, seed=11)
    summary_b = run_persona_suite(catalog, samples_per_role=5, seed=11)
    assert summary_a == summary_b
    assert summary_a['total_samples'] == 10
    assert set(summary_a['per_role_accuracy']) == {'backend-developer', 'ux-designer'}
    assert 0.0 <= summary_a['top1_accuracy'] <= 1.0


def test_compare_to_baseline_flags_digest_change_and_regression():
    summary = {'top1_accuracy': 0.90, 'resolved_rate': 0.6, 'precision_resolved': 0.99}
    baseline = {
        'content_digest': 'abc',
        'metrics': {'top1_accuracy': 0.95, 'resolved_rate': 0.6, 'precision_resolved': 0.99},
    }
    failures = compare_to_baseline(summary, baseline, content_digest='abc', tolerance=0.02)
    assert len(failures) == 1
    assert 'top1_accuracy' in failures[0]

    failures = compare_to_baseline(summary, baseline, content_digest='different', tolerance=0.10)
    assert len(failures) == 1
    assert 'digest' in failures[0]


def test_compare_to_baseline_passes_within_tolerance():
    summary = {'top1_accuracy': 0.94, 'resolved_rate': 0.65, 'precision_resolved': 0.99}
    baseline = {
        'content_digest': 'abc',
        'metrics': {'top1_accuracy': 0.95, 'resolved_rate': 0.66, 'precision_resolved': 0.995},
    }
    assert compare_to_baseline(summary, baseline, content_digest='abc', tolerance=0.02) == []


def test_content_digest_changes_with_question_signals():
    catalog = _make_catalog()
    digest_a = compute_content_digest(catalog)
    mutated_questions = [dict(q) for q in catalog.questions]
    mutated_questions[0] = {**mutated_questions[0], 'agree_dimension_signals': {'construction': 0.6}}
    digest_b = compute_content_digest(
        CatalogContext(
            questions=mutated_questions,
            active_role_slugs=catalog.active_role_slugs,
            role_names=catalog.role_names,
            available_questions=catalog.available_questions,
        ),
    )
    assert digest_a != digest_b


def test_zero_noise_persona_finds_its_role_among_the_candidates():
    catalog = _make_catalog()
    exact_noise = {2: ((2,), (1.0,)), 0: ((0,), (1.0,)), -2: ((-2,), (1.0,))}
    sample = run_persona_sample('ux-designer', catalog, random.Random(1), noise_model=exact_noise)
    assert sample['in_candidates'] is True


def test_realistic_persona_ground_truth_is_a_known_role():
    persona = make_persona(random.Random(3), dict(PARAMS))
    assert persona['truth'] in persona['truth_top2']
    assert persona['kind'] in {'pure', 'blend', 'undecided'}


def test_realistic_suite_reports_per_scenario_and_is_deterministic():
    catalog = _make_catalog()
    report_a = run_realistic_suite(catalog, samples=6, seed=5, scenarios=['base'])
    report_b = run_realistic_suite(catalog, samples=6, seed=5, scenarios=['base'])
    assert report_a == report_b
    base = report_a['scenarios']['base']
    assert 0.0 <= base['top3_accuracy'] <= 1.0
    assert base['avg_answered_questions'] == 2
    assert report_a['summary']['top3_accuracy_worst'] == base['top3_accuracy']
