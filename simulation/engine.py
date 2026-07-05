"""Django-free Monte Carlo simulator for role-discovery scoring. Workers import
this without ``django.setup()``; all math delegates to :mod:`assessments.scoring`.
"""

import concurrent.futures
import math
import random
from collections import Counter
from dataclasses import dataclass, field

from assessments import scoring


LIKERT_VALUES = (-2, -1, 0, 1, 2)
BASELINE_LIKERT_WEIGHTS = {-2: 0.10, -1: 0.20, 0: 0.40, 1: 0.20, 2: 0.10}


@dataclass
class _SampleState:

    active_role_slugs: list[str]
    role_names: dict[str, str]
    core_target: int
    role_scores: dict[str, float] = field(default_factory=dict)
    dimension_scores: dict[str, float] = field(default_factory=dict)
    dimension_evidence_counts: dict[str, int] = field(default_factory=dict)
    answered_question_ids: set[int] = field(default_factory=set)
    answered_core: int = 0
    answered_tie_break: int = 0
    answered_total: int = 0

    def __post_init__(self) -> None:
        if not self.role_scores:
            self.role_scores = dict.fromkeys(self.active_role_slugs, 0.0)

    def apply_answer(self, question: dict, scale_value: int) -> None:
        selected, _rejected, strength = scoring._resolve_signal_sides(question, scale_value)
        if strength > 0:
            multiplier = abs(float(scale_value))
            for dimension_key, raw_weight in (selected or {}).items():
                try:
                    weight = float(raw_weight)
                except (TypeError, ValueError):
                    continue
                if not dimension_key or weight <= 0:
                    continue
                self.dimension_scores[dimension_key] = self.dimension_scores.get(dimension_key, 0.0) + weight * multiplier
                self.dimension_evidence_counts[dimension_key] = self.dimension_evidence_counts.get(dimension_key, 0) + 1
        for role_slug, delta in scoring._score_roles_for_answer(question, scale_value).items():
            self.role_scores[role_slug] = self.role_scores.get(role_slug, 0.0) + delta

        self.answered_question_ids.add(question['id'])
        if question.get('item_group') == 'tie_break':
            self.answered_tie_break += 1
        else:
            self.answered_core += 1
        self.answered_total += 1

    def evidence_snapshot(self) -> scoring.RoleEvidenceSnapshot:
        return scoring.RoleEvidenceSnapshot(
            role_scores=dict(self.role_scores),
            dimension_scores=dict(self.dimension_scores),
            dimension_evidence_counts=dict(self.dimension_evidence_counts),
        )

    def inference_snapshot(self) -> dict[str, object]:
        return scoring.build_role_inference_snapshot(
            self.evidence_snapshot(),
            active_role_slugs=self.active_role_slugs,
            role_names=self.role_names,
            answered_core=self.answered_core,
            core_target=self.core_target,
        )


def run_single_sample(  # noqa: PLR0913
    sample_index: int,
    questions: list[dict],
    active_role_slugs: list[str],
    role_names: dict[str, str],
    core_target: int,
    prefix_answers: list[int],
    pre_generated_choices: list[int],
) -> dict[str, object]:
    state = _SampleState(
        active_role_slugs=list(active_role_slugs),
        role_names=role_names,
        core_target=core_target,
    )

    choice_index = 0
    snapshot = state.inference_snapshot()
    unanswered = list(questions)
    is_resolved = False
    has_remaining = bool(scoring.select_role_candidates(unanswered, snapshot))

    while has_remaining and not is_resolved:
        question = scoring.select_role_candidates(unanswered, snapshot)[0]
        if state.answered_total < len(prefix_answers):
            scale_value = prefix_answers[state.answered_total]
        else:
            scale_value = pre_generated_choices[choice_index]
            choice_index += 1

        state.apply_answer(question, scale_value)
        snapshot = state.inference_snapshot()
        unanswered = [question_dict for question_dict in unanswered if question_dict['id'] != question['id']]
        has_remaining = bool(scoring.select_role_candidates(unanswered, snapshot))
        is_resolved = scoring.is_role_resolution_exhausted_with_viable_winner(
            snapshot,
            has_remaining_tie_breaks_for_top_pair=has_remaining,
        )

    is_core_complete = state.answered_core >= core_target > 0
    best_fit_role_slug = snapshot['top_role_slug'] or None
    resolution_status = scoring.get_role_resolution_status(
        is_core_complete=is_core_complete,
        best_fit_role_slug=best_fit_role_slug,
        is_resolved=is_resolved,
        has_remaining_role_questions=has_remaining,
    )

    return {
        'sample_index': sample_index,
        'phase': 'recommendation_ready',
        'status': 'completed',
        'resolution_status': resolution_status,
        'best_fit_role': best_fit_role_slug if resolution_status in {'resolved', 'low_confidence'} else None,
        'top_ranked_role': best_fit_role_slug,
        'answered_core_questions': state.answered_core,
        'answered_tie_break_questions': state.answered_tie_break,
        'answered_role_questions': state.answered_total,
        'confidence': float(snapshot['confidence']),
        'margin_share': float(snapshot['margin_share']),
        'score_margin': float(snapshot['score_margin']),
        'winner_share': float(snapshot['winner_share']),
    }


def _pre_generate_choices(
    samples: int,
    questions_per_sample: int,
    prefix_length: int,
    likert_weights: dict[int, float],
    seed: int,
) -> list[list[int]]:
    rng = random.Random(seed)  # noqa: S311
    population = list(LIKERT_VALUES)
    weights = [likert_weights[value] for value in population]
    needed = max(questions_per_sample - prefix_length, 0)
    return [
        [rng.choices(population, weights=weights, k=1)[0] for _ in range(needed)]
        for _ in range(samples)
    ]


def run_samples(  # noqa: PLR0913
    *,
    samples: int,
    questions: list[dict],
    active_role_slugs: list[str],
    role_names: dict[str, str],
    core_target: int,
    prefix_answers: list[int],
    likert_weights: dict[int, float],
    seed: int,
    workers: int | None = None,
) -> list[dict[str, object]]:
    questions_per_sample = len(questions)
    pre_generated_choices = _pre_generate_choices(
        samples,
        questions_per_sample,
        len(prefix_answers),
        likert_weights,
        seed,
    )
    worker_count = workers if workers and workers > 0 else None

    results: list[dict[str, object]] = []
    with concurrent.futures.ProcessPoolExecutor(max_workers=worker_count) as executor:
        futures = [
            executor.submit(
                run_single_sample,
                index,
                questions,
                list(active_role_slugs),
                role_names,
                core_target,
                list(prefix_answers),
                pre_generated_choices[index],
            )
            for index in range(samples)
        ]
        results.extend(future.result() for future in concurrent.futures.as_completed(futures))

    results.sort(key=lambda result: result['sample_index'])
    return results


def aggregate_results(  # noqa: PLR0913
    results: list[dict[str, object]],
    *,
    samples: int,
    seed: int,
    likert_weights: dict[int, float],
    active_role_slugs: list[str],
    prefix_answers: list[int],
) -> dict[str, object]:
    resolved = [result for result in results if result['resolution_status'] == 'resolved']
    low_confidence = [result for result in results if result['resolution_status'] == 'low_confidence']
    ambiguous = [result for result in results if result['phase'] == 'role_ambiguity']
    completed = [result for result in results if result['status'] == 'completed']

    best_fit_counts = Counter(result['best_fit_role'] for result in results if result['best_fit_role'])
    resolved_counts = Counter(result['best_fit_role'] for result in resolved if result['best_fit_role'])
    role_count = len(active_role_slugs)

    summary: dict[str, object] = {
        'samples': samples,
        'seed': seed,
        'prefix_answers': list(prefix_answers),
        'likert_weights': {key: likert_weights[key] for key in LIKERT_VALUES},
        'random_answer_values': list(LIKERT_VALUES),
        'active_role_count': role_count,
        'completed_count': len(completed),
        'completed_rate': round(len(completed) / samples, 4),
        'resolved_count': len(resolved),
        'resolved_rate': round(len(resolved) / samples, 4),
        'low_confidence_count': len(low_confidence),
        'low_confidence_rate': round(len(low_confidence) / samples, 4),
        'ambiguous_count': len(ambiguous),
        'ambiguous_rate': round(len(ambiguous) / samples, 4),
        'best_fit_role_coverage_count': len(best_fit_counts),
        'best_fit_role_coverage_rate': round(len(best_fit_counts) / role_count, 4),
        'missing_best_fit_roles': sorted(set(active_role_slugs) - set(best_fit_counts)),
        'best_fit_role_uniformity': _distribution_shape(best_fit_counts, role_count),
        'resolved_role_coverage_count': len(resolved_counts),
        'resolved_role_coverage_rate': round(len(resolved_counts) / role_count, 4),
        'missing_resolved_roles': sorted(set(active_role_slugs) - set(resolved_counts)),
        'resolved_role_uniformity': _distribution_shape(resolved_counts, role_count),
        'answered_role_questions': _stats([result['answered_role_questions'] for result in results]),
        'worst_case_95pct_margin_of_error': round(1.96 * ((0.25 / samples) ** 0.5), 4),
    }

    if resolved:
        summary['resolved_confidence'] = _stats([result['confidence'] for result in resolved])
        summary['resolved_margin_share'] = _stats([result['margin_share'] for result in resolved])
        summary['resolved_score_margin'] = _stats([result['score_margin'] for result in resolved])
        summary['resolved_winner_share'] = _stats([result['winner_share'] for result in resolved])
        summary['resolved_roles'] = dict(resolved_counts.most_common())

    if low_confidence:
        summary['low_confidence_confidence'] = _stats([result['confidence'] for result in low_confidence])
        summary['low_confidence_margin_share'] = _stats([result['margin_share'] for result in low_confidence])
        summary['low_confidence_score_margin'] = _stats([result['score_margin'] for result in low_confidence])
        summary['low_confidence_roles'] = dict(Counter(result['best_fit_role'] for result in low_confidence if result['best_fit_role']).most_common())

    if ambiguous:
        summary['ambiguous_confidence'] = _stats([result['confidence'] for result in ambiguous])
        summary['ambiguous_margin_share'] = _stats([result['margin_share'] for result in ambiguous])
        summary['ambiguous_score_margin'] = _stats([result['score_margin'] for result in ambiguous])

    return summary


def _stats(values: list[float]) -> dict[str, float]:
    if not values:
        return {'mean': 0.0, 'min': 0.0, 'max': 0.0, 'median': 0.0}
    values_int = [float(value) for value in values]
    sorted_values = sorted(values_int)
    count = len(sorted_values)
    mean = sum(sorted_values) / count
    mid = count // 2
    median = sorted_values[mid] if count % 2 else (sorted_values[mid - 1] + sorted_values[mid]) / 2.0
    return {
        'mean': round(mean, 4),
        'min': round(min(sorted_values), 4),
        'max': round(max(sorted_values), 4),
        'median': round(median, 4),
    }


def _distribution_shape(role_counts: Counter, role_count: int) -> dict[str, float]:
    total = sum(role_counts.values())
    if total == 0 or role_count == 0:
        return {'normalized_entropy': 0.0, 'max_share': 0.0, 'min_seen_share': 0.0}
    probabilities = [count / total for count in role_counts.values()]
    entropy = -sum(probability * math.log(probability) for probability in probabilities)
    normalized_entropy = entropy / math.log(role_count) if role_count > 1 else 1.0
    return {
        'normalized_entropy': round(normalized_entropy, 4),
        'max_share': round(max(probabilities), 4),
        'min_seen_share': round(min(probabilities), 4),
    }


# Hyperparameter trial runner — lives here (not in a command) so worker
# processes can import it without Django setup. Each trial overrides scoring
# constants, runs the same pre-generated answer stream, then restores originals.
TUNABLE_PARAM_NAMES = (
    'ROLE_DISCOVERY_MIN_SCORE_MARGIN',
    'ROLE_EVIDENCE_LOGISTIC_SCALE',
    'ROLE_EVIDENCE_SCORE_SCALE',
)

METRIC_HIGHER_IS_BETTER = {
    'resolved_rate',
    'resolved_role_coverage_rate',
    'resolved_uniformity',
}
METRIC_LOWER_IS_BETTER = {
    'low_confidence_rate',
    'ambiguous_rate',
}


def extract_metric(summary: dict[str, object], metric: str) -> float:
    if metric == 'resolved_uniformity':
        return float(summary['resolved_role_uniformity']['normalized_entropy'])
    return float(summary[metric])


def run_trial(  # noqa: PLR0913
    trial_id: int,
    params: dict[str, float],
    samples: int,
    questions: list[dict],
    active_role_slugs: list[str],
    role_names: dict[str, str],
    core_target: int,
    pre_generated_choices: list[list[int]],
    likert_weights: dict[int, float],
    seed: int,
    metric: str,
) -> dict[str, object]:
    originals = {name: getattr(scoring, name) for name in params}
    for name, value in params.items():
        setattr(scoring, name, value)
    try:
        results = [
            run_single_sample(
                index,
                questions,
                list(active_role_slugs),
                role_names,
                core_target,
                [],
                pre_generated_choices[index],
            )
            for index in range(samples)
        ]
    finally:
        for name, value in originals.items():
            setattr(scoring, name, value)

    summary = aggregate_results(
        results,
        samples=samples,
        seed=seed,
        likert_weights=likert_weights,
        active_role_slugs=list(active_role_slugs),
        prefix_answers=[],
    )
    return {
        'trial_id': trial_id,
        'params': params,
        'metric': metric,
        'metric_value': round(extract_metric(summary, metric), 4),
        'resolved_rate': summary['resolved_rate'],
        'low_confidence_rate': summary['low_confidence_rate'],
        'resolved_role_coverage_rate': summary['resolved_role_coverage_rate'],
        'resolved_uniformity': summary['resolved_role_uniformity']['normalized_entropy'],
    }
