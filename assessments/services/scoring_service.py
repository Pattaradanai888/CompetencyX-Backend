"""Pure-Python role-discovery scoring math — single source of truth shared by
production (``role_inference``) and the in-memory simulator. No Django imports.
"""

import math
from collections import defaultdict
from dataclasses import dataclass

from roadmaps.questionnaire import ROLE_DIMENSION_LABELS, ROLE_PROFILE_WEIGHTS


# Evidence pipeline constants — tuned via the Monte Carlo simulator.
ROLE_DISCOVERY_MIN_SCORE_MARGIN = 0.300
ROLE_DISCOVERY_TOP_PAIR_COUNT = 2
ROLE_EVIDENCE_LOGISTIC_SCALE = 1.989
ROLE_EVIDENCE_SCORE_SCALE = 5.229


@dataclass(frozen=True)
class RoleEvidenceSnapshot:
    role_scores: dict[str, float]
    dimension_scores: dict[str, float]
    dimension_evidence_counts: dict[str, int]


def _log_sigmoid(value: float) -> float:
    if value >= 0:
        return -math.log1p(math.exp(-value))
    return value - math.log1p(math.exp(value))


def _compute_role_dimension_idf(role_profile_weights: dict[str, dict[str, float]]) -> dict[str, float]:
    role_count = len(role_profile_weights)
    dimension_role_counts: dict[str, int] = defaultdict(int)
    for profile in role_profile_weights.values():
        for dimension_key, weight in profile.items():
            if max(float(weight), 0.0) > 0:
                dimension_role_counts[dimension_key] += 1
    return {
        dimension_key: math.log((role_count + 1.0) / (role_count_for_dimension + 1.0)) + 1.0
        for dimension_key, role_count_for_dimension in dimension_role_counts.items()
    }


ROLE_DIMENSION_IDF: dict[str, float] = _compute_role_dimension_idf(ROLE_PROFILE_WEIGHTS)


def score_dimension_overlap(signals: dict[str, float], profile: dict[str, float]) -> float:
    score = 0.0
    for dimension_key, signal_weight in (signals or {}).items():
        try:
            clean_signal_weight = max(float(signal_weight), 0.0)
        except (TypeError, ValueError):
            continue
        if clean_signal_weight <= 0:
            continue
        score += clean_signal_weight * max(float(profile.get(dimension_key, 0.0)), 0.0) * ROLE_DIMENSION_IDF.get(dimension_key, 1.0)
    return score


def _resolve_signal_sides(question: dict, scale_value: int | None) -> tuple[dict[str, float], dict[str, float], float]:
    if scale_value is None or scale_value == 0:
        return {}, {}, 0.0
    agree_signals = question.get('agree_dimension_signals') or {}
    disagree_signals = question.get('disagree_dimension_signals') or {}
    answer_strength = min(1.0, abs(float(scale_value)) / 2.0)
    if scale_value > 0:
        return agree_signals, disagree_signals, answer_strength
    return disagree_signals, agree_signals, answer_strength


def _score_roles_for_answer(question: dict, scale_value: int | None) -> dict[str, float]:
    selected_signals, rejected_signals, answer_strength = _resolve_signal_sides(question, scale_value)
    if answer_strength <= 0 or (not selected_signals and not rejected_signals):
        return {}

    role_scores: dict[str, float] = {}
    for role_slug, profile in ROLE_PROFILE_WEIGHTS.items():
        selected_overlap = score_dimension_overlap(selected_signals, profile)
        rejected_overlap = score_dimension_overlap(rejected_signals, profile)
        role_signal = selected_overlap - rejected_overlap
        role_scores[role_slug] = ROLE_EVIDENCE_SCORE_SCALE * answer_strength * _log_sigmoid(ROLE_EVIDENCE_LOGISTIC_SCALE * role_signal)
    return role_scores


def get_sorted_role_scores(role_scores: dict[str, float]) -> list[tuple[str, float]]:
    return sorted(role_scores.items(), key=lambda item: (-item[1], item[0]))


def build_role_shares(role_scores: dict[str, float], active_role_slugs: list[str]) -> dict[str, float]:
    if not active_role_slugs:
        return {}
    scores = {slug: float(role_scores.get(slug, 0.0)) for slug in active_role_slugs}
    if all(score == 0.0 for score in scores.values()):
        uniform = 1.0 / len(active_role_slugs)
        return dict.fromkeys(active_role_slugs, uniform)
    # Scores are cumulative log-sigmoid (log-probabilities); convert to shares
    # via softmax with fixed temperature=1 (no tunable constants needed).
    max_score = max(scores.values())
    exp_scores = {slug: math.exp(score - max_score) for slug, score in scores.items()}
    total = sum(exp_scores.values())
    if total <= 0:
        uniform = 1.0 / len(active_role_slugs)
        return dict.fromkeys(active_role_slugs, uniform)
    return {slug: score / total for slug, score in exp_scores.items()}


def _get_top_supporting_pillars(role_slug: str, dimension_scores: dict[str, float], *, limit: int = 3) -> list[str]:
    profile = ROLE_PROFILE_WEIGHTS.get(role_slug, {})
    weighted_dimensions = [
        (
            ROLE_DIMENSION_LABELS.get(dimension_key, dimension_key.replace('_', ' ').title()),
            max(float(profile_weight), 0.0) * max(float(dimension_scores.get(dimension_key, 0.0)), 0.0),
        )
        for dimension_key, profile_weight in profile.items()
    ]
    return [label for label, weighted_score in sorted(weighted_dimensions, key=lambda item: (-item[1], item[0]))[:limit] if weighted_score > 0]


def compute_role_evidence_snapshot(answers: list[dict]) -> RoleEvidenceSnapshot:
    dimension_scores: dict[str, float] = defaultdict(float)
    dimension_evidence_counts: dict[str, int] = defaultdict(int)
    role_scores: dict[str, float] = defaultdict(float)

    for answer in answers:
        scale_value = answer.get('scale_value')
        selected, _rejected, strength = _resolve_signal_sides(answer, scale_value)
        if strength > 0:
            multiplier = abs(float(scale_value))
            for dimension_key, raw_weight in (selected or {}).items():
                try:
                    weight = float(raw_weight)
                except (TypeError, ValueError):
                    continue
                if not dimension_key or weight <= 0:
                    continue
                dimension_scores[dimension_key] += weight * multiplier
                dimension_evidence_counts[dimension_key] += 1
        for role_slug, delta in _score_roles_for_answer(answer, scale_value).items():
            role_scores[role_slug] += delta

    return RoleEvidenceSnapshot(
        role_scores=dict(role_scores),
        dimension_scores=dict(dimension_scores),
        dimension_evidence_counts=dict(dimension_evidence_counts),
    )


def build_role_inference_snapshot(  # noqa: PLR0913
    evidence: RoleEvidenceSnapshot,
    *,
    active_role_slugs: list[str],
    role_names: dict[str, str] | None = None,
    answered_core: int,
    core_target: int,
    answered_tie_break: int = 0,
) -> dict[str, object]:
    role_names = {} if role_names is None else role_names
    role_scores = {role_slug: evidence.role_scores.get(role_slug, 0.0) for role_slug in active_role_slugs}
    sorted_scores = get_sorted_role_scores(role_scores)
    role_shares = build_role_shares(role_scores, active_role_slugs)
    top_slug, top_score = sorted_scores[0] if sorted_scores else (None, 0.0)
    runner_up_slug = sorted_scores[1][0] if len(sorted_scores) > 1 else None
    runner_up_score = sorted_scores[1][1] if len(sorted_scores) > 1 else 0.0
    winner_share = role_shares.get(top_slug, 0.0) if top_slug else 0.0
    has_evidence = bool(evidence.role_scores)
    confidence = max(0.0, min(1.0, winner_share * min(1.0, answered_core / max(core_target, 1)))) if has_evidence else 0.0
    total_dimension_score = sum(max(score, 0.0) for score in evidence.dimension_scores.values())
    pillar_profile = [
        {
            'key': dimension_key,
            'label': ROLE_DIMENSION_LABELS.get(dimension_key, dimension_key.replace('_', ' ').title()),
            'raw_score': raw_score,
            'normalized_score': (raw_score / total_dimension_score) if total_dimension_score else 0.0,
            'evidence_count': evidence.dimension_evidence_counts.get(dimension_key, 0),
        }
        for dimension_key, raw_score in sorted(
            evidence.dimension_scores.items(),
            key=lambda item: (-item[1], item[0]),
        )
        if raw_score > 0
    ]
    ranked_roles = [
        {
            'slug': role_slug,
            'name': role_names.get(role_slug, role_slug),
            'fit_score': score,
            'fit_share': role_shares.get(role_slug, 0.0),
            'top_supporting_pillars': _get_top_supporting_pillars(role_slug, evidence.dimension_scores),
        }
        for role_slug, score in sorted_scores
    ]
    return {
        'top_role_slug': top_slug,
        'winner_share': winner_share,
        'margin_share': winner_share - role_shares.get(runner_up_slug, 0.0),
        'score_margin': top_score - runner_up_score,
        'confidence': confidence,
        'core_question_target': core_target,
        'dimension_scores': evidence.dimension_scores,
        'observed_pillars': sum(1 for score in evidence.dimension_scores.values() if score > 0),
        'answered_core_questions': answered_core,
        'pillar_profile': pillar_profile,
        'ranked_roles': ranked_roles,
    }


def select_role_candidates(
    unanswered_questions: list[dict],
    snapshot: dict[str, object] | None = None,
    *,
    top_pair_count: int | None = None,
) -> list[dict]:
    top_pair_count = ROLE_DISCOVERY_TOP_PAIR_COUNT if top_pair_count is None else top_pair_count

    core_candidates = [question for question in unanswered_questions if question.get('item_group') == 'core']
    if core_candidates:
        return sorted(core_candidates, key=lambda question: (question.get('display_order', 0), question.get('id', 0)))

    if snapshot is None:
        return []
    ranked_roles = snapshot.get('ranked_roles') or []
    if len(ranked_roles) < top_pair_count or float(snapshot.get('score_margin', 0.0)) >= ROLE_DISCOVERY_MIN_SCORE_MARGIN:
        return []
    top_pair = {str(ranked_roles[0]['slug']), str(ranked_roles[1]['slug'])}

    tie_break_candidates = [
        question
        for question in unanswered_questions
        if question.get('item_group') == 'tie_break'
        and top_pair.issubset(set(question.get('discriminates_between') or []))
    ]
    return sorted(tie_break_candidates, key=lambda question: (question.get('display_order', 0), question.get('id', 0)))


def is_role_resolution_exhausted_with_viable_winner(
    snapshot: dict[str, object],
    *,
    has_remaining_tie_breaks_for_top_pair: bool,
) -> bool:
    if snapshot['top_role_slug'] is None:
        return False
    if int(snapshot['answered_core_questions']) < int(snapshot['core_question_target']):
        return False
    if has_remaining_tie_breaks_for_top_pair:
        return False
    return float(snapshot['score_margin']) >= ROLE_DISCOVERY_MIN_SCORE_MARGIN


def get_role_resolution_status(
    *,
    is_core_complete: bool,
    best_fit_role_slug: str | None,
    is_resolved: bool,
    has_remaining_role_questions: bool,
) -> str:
    if not is_core_complete:
        return 'in_progress'
    if best_fit_role_slug is None:
        return 'unknown'
    if is_resolved:
        return 'resolved'
    if has_remaining_role_questions:
        return 'in_progress'
    return 'low_confidence'
