"""Django-free persona-fidelity harness for role-discovery content.

For every active role this module simulates "noisy personas": respondents
whose ideal answers are derived from the role's profile, perturbed by a fixed
noise model. Each sample runs the REAL question-selection flow (core in
display order, then margin-gated tie-breaks) through ``scoring_service``.

This measures self-consistency — whether the question bank plus the derived
weights can recover the role a persona was generated from — not human
validity. See docs/scoring-methodology.md for how it gates content changes.
"""

import hashlib
import json
import random
from collections import Counter, defaultdict

from assessments.services import scoring_service
from roadmaps.questionnaire import ROLE_PROFILE_WEIGHTS

from .engine import CatalogContext, _SampleState


# Probability of each actual answer given the persona's ideal answer.
# Ideal +2 -> mostly agrees, sometimes hesitates, rarely contradicts.
DEFAULT_NOISE_MODEL = {
    2: ((2, 1, 0, -1), (0.45, 0.35, 0.15, 0.05)),
    0: ((1, 0, -1), (0.3, 0.4, 0.3)),
    -2: ((-2, -1, 0, 1), (0.45, 0.35, 0.15, 0.05)),
}

# Overlap differences smaller than this are treated as "no clear side" and the
# persona's ideal answer is neutral.
IDEAL_ANSWER_NEUTRAL_BAND = 0.15


def compute_content_digest(catalog: CatalogContext) -> str:
    """Digest of everything that determines harness behavior besides the seed."""
    payload = {
        'questions': [
            {
                'display_order': question.get('display_order'),
                'item_group': question.get('item_group'),
                'discriminates_between': sorted(question.get('discriminates_between') or []),
                'agree': dict(sorted((question.get('agree_dimension_signals') or {}).items())),
                'disagree': dict(sorted((question.get('disagree_dimension_signals') or {}).items())),
            }
            for question in catalog.questions
        ],
        'profiles': {slug: dict(sorted(profile.items())) for slug, profile in sorted(ROLE_PROFILE_WEIGHTS.items())},
        'active_role_slugs': sorted(catalog.active_role_slugs),
        'min_score_margin': scoring_service.ROLE_DISCOVERY_MIN_SCORE_MARGIN,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode('utf-8')).hexdigest()


def ideal_scale_value(question: dict, profile: dict[str, float]) -> int:
    agree = scoring_service.score_dimension_overlap(question.get('agree_dimension_signals') or {}, profile)
    disagree = scoring_service.score_dimension_overlap(question.get('disagree_dimension_signals') or {}, profile)
    difference = agree - disagree
    if difference > IDEAL_ANSWER_NEUTRAL_BAND:
        return 2
    if difference < -IDEAL_ANSWER_NEUTRAL_BAND:
        return -2
    return 0


def sample_noisy_answer(ideal: int, rng: random.Random, noise_model=DEFAULT_NOISE_MODEL) -> int:
    values, weights = noise_model[ideal]
    return rng.choices(values, weights)[0]


def run_persona_sample(
    role_slug: str,
    catalog: CatalogContext,
    rng: random.Random,
    *,
    noise_model=DEFAULT_NOISE_MODEL,
) -> dict[str, object]:
    profile = ROLE_PROFILE_WEIGHTS[role_slug]
    state = _SampleState(
        active_role_slugs=list(catalog.active_role_slugs),
        role_names=catalog.role_names,
        core_target=catalog.core_target,
    )
    unanswered = list(catalog.questions)
    snapshot = state.inference_snapshot()
    answered_questions: list[tuple[dict, int]] = []
    is_resolved = False

    while True:
        candidates = scoring_service.select_role_candidates(unanswered, snapshot)
        if not candidates:
            break
        question = candidates[0]
        scale_value = sample_noisy_answer(ideal_scale_value(question, profile), rng, noise_model)
        state.apply_answer(question, scale_value)
        answered_questions.append((question, scale_value))
        unanswered = [candidate for candidate in unanswered if candidate['id'] != question['id']]
        snapshot = state.inference_snapshot()
        has_remaining = bool(scoring_service.select_role_candidates(unanswered, snapshot))
        is_resolved = scoring_service.is_role_resolution_exhausted_with_viable_winner(
            snapshot,
            has_remaining_tie_breaks_for_top_pair=has_remaining,
        )
        if is_resolved:
            break

    ranked = snapshot['ranked_roles']
    predicted = snapshot['top_role_slug']
    runner_up = ranked[1]['slug'] if len(ranked) > 1 else None
    return {
        'true_role': role_slug,
        'predicted_role': predicted,
        'runner_up_role': runner_up,
        'correct': predicted == role_slug,
        'resolved': is_resolved,
        'score_margin': float(snapshot['score_margin']),
        'confidence': float(snapshot['confidence']),
        'answered_total': state.answered_total,
        'answered_tie_break': state.answered_tie_break,
        'answered_questions': answered_questions,
    }


def _question_vote(question: dict, scale_value: int, role_slug: str) -> float:
    return scoring_service._score_roles_for_answer(question, scale_value).get(role_slug, 0.0)


def run_persona_suite(
    catalog: CatalogContext,
    *,
    samples_per_role: int,
    seed: int,
    noise_model=DEFAULT_NOISE_MODEL,
) -> dict[str, object]:
    rng = random.Random(seed)
    role_slugs = [slug for slug in catalog.active_role_slugs if slug in ROLE_PROFILE_WEIGHTS]

    per_role_correct: Counter = Counter()
    confusion: Counter = Counter()
    question_discrimination_counts: dict[object, int] = defaultdict(int)
    question_seen_counts: dict[object, int] = defaultdict(int)
    total = correct = resolved = correct_resolved = 0
    answered_total_sum = tie_break_used = 0

    for role_slug in role_slugs:
        for _ in range(samples_per_role):
            sample = run_persona_sample(role_slug, catalog, rng, noise_model=noise_model)
            total += 1
            answered_total_sum += sample['answered_total']
            tie_break_used += bool(sample['answered_tie_break'])
            if sample['correct']:
                correct += 1
                per_role_correct[role_slug] += 1
            else:
                confusion[(role_slug, sample['predicted_role'])] += 1
            if sample['resolved']:
                resolved += 1
                correct_resolved += sample['correct']

            contrast_role = sample['runner_up_role'] if sample['correct'] else sample['predicted_role']
            if contrast_role:
                for question, scale_value in sample['answered_questions']:
                    question_seen_counts[question['id']] += 1
                    if _question_vote(question, scale_value, role_slug) != _question_vote(question, scale_value, contrast_role):
                        question_discrimination_counts[question['id']] += 1

    dead_question_ids = sorted(
        question_id
        for question_id, seen in question_seen_counts.items()
        if seen > 0 and question_discrimination_counts[question_id] == 0
    )
    return {
        'samples_per_role': samples_per_role,
        'seed': seed,
        'total_samples': total,
        'top1_accuracy': round(correct / total, 4) if total else 0.0,
        'resolved_rate': round(resolved / total, 4) if total else 0.0,
        'precision_resolved': round(correct_resolved / resolved, 4) if resolved else 0.0,
        'avg_answered_questions': round(answered_total_sum / total, 2) if total else 0.0,
        'tie_break_usage_rate': round(tie_break_used / total, 4) if total else 0.0,
        'per_role_accuracy': {
            slug: round(per_role_correct[slug] / samples_per_role, 4) if samples_per_role else 0.0
            for slug in sorted(role_slugs)
        },
        'confusion_pairs': [
            {'true_role': true_role, 'predicted_role': predicted_role, 'count': count}
            for (true_role, predicted_role), count in confusion.most_common()
        ],
        'dead_question_ids': dead_question_ids,
    }


def build_baseline(summary: dict[str, object], *, content_digest: str) -> dict[str, object]:
    return {
        'content_digest': content_digest,
        'seed': summary['seed'],
        'samples_per_role': summary['samples_per_role'],
        'metrics': {
            'top1_accuracy': summary['top1_accuracy'],
            'resolved_rate': summary['resolved_rate'],
            'precision_resolved': summary['precision_resolved'],
        },
        'per_role_accuracy': summary['per_role_accuracy'],
    }


def compare_to_baseline(
    summary: dict[str, object],
    baseline: dict[str, object],
    *,
    content_digest: str,
    tolerance: float,
) -> list[str]:
    """Return a list of failure messages; empty means the check passes."""
    failures = []
    if baseline.get('content_digest') != content_digest:
        failures.append(
            'content digest differs from baseline — content or weights changed; '
            'review the report and re-pin with --write-baseline if intentional',
        )
    for metric, baseline_value in baseline.get('metrics', {}).items():
        current = float(summary.get(metric, 0.0))
        if current < float(baseline_value) - tolerance:
            failures.append(f'{metric} {current:.4f} fell below baseline {float(baseline_value):.4f} - {tolerance}')
    return failures
