# ruff: noqa: E402, C901, PLR0912, PLR0913, PLR0915, PLR2004, S311, PLW0603
import argparse
import concurrent.futures
import math
import os
import random
import sys
from collections import Counter, defaultdict


# Set up Django settings before importing models
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.runtime')
import django


django.setup()

from roadmaps.models import Question, Role
from roadmaps.questionnaire import ROLE_PROFILE_WEIGHTS


LIKERT_VALUES = (-2, -1, 0, 1, 2)

ROLE_DISCOVERY_CONFIDENCE_THRESHOLD = 0.289
ROLE_DISCOVERY_MIN_MARGIN = 0.300
ROLE_DISCOVERY_CORE_QUESTION_TARGET = 36
DEFAULT_ROLE_PRIOR_WEIGHT = 0.00076
ROLE_SCORE_SOFTMAX_TEMPERATURE = 2.242
ROLE_EVIDENCE_LOGISTIC_SCALE = 1.989
ROLE_EVIDENCE_SCORE_SCALE = 5.229
ROLE_SPECIALIZATION_EVIDENCE_THRESHOLD = 0.322
SOFTMAX_OMEGA = 0.203

BASELINE_DIST = {
    -2: 0.10,
    -1: 0.20,
     0: 0.40,
     1: 0.20,
     2: 0.10,
}

ROLE_SPECIALIZATION_REQUIREMENTS = {
    'android-developer': ('android_platform',),
    'bi-analyst': ('business_intelligence',),
    'blockchain-developer': ('blockchain_platform',),
    'developer-relations': ('developer_community',),
    'game-developer': ('game_client',),
    'ios-developer': ('ios_platform',),
    'mlops-engineer': ('ml_platform',),
    'postgresql-developer-dba': ('database_postgresql',),
    'server-side-game-developer': ('game_server',),
    'technical-writer': ('technical_documentation',),
}

# Process-local static cache for question selection
GLOBAL_STATIC_CACHE = {}


def _log_sigmoid(value: float) -> float:
    if value >= 0:
        return -math.log1p(math.exp(-value))
    return value - math.log1p(math.exp(value))


def _compute_role_dimension_idf(role_profile_weights: dict) -> dict[str, float]:
    role_count = len(role_profile_weights)
    dimension_role_counts = defaultdict(int)
    for profile in role_profile_weights.values():
        for dimension_key, weight in profile.items():
            if max(float(weight), 0.0) > 0:
                dimension_role_counts[dimension_key] += 1
    return {
        dimension_key: math.log((role_count + 1.0) / (role_count_for_dimension + 1.0)) + 1.0
        for dimension_key, role_count_for_dimension in dimension_role_counts.items()
    }


ROLE_DIMENSION_IDF = _compute_role_dimension_idf(ROLE_PROFILE_WEIGHTS)


def _score_role_question(q: dict) -> tuple:
    agree_signals = q.get('agree_dimension_signals') or {}
    disagree_signals = q.get('disagree_dimension_signals') or {}
    dimension_count = len(set(agree_signals.keys()) | set(disagree_signals.keys()))
    if dimension_count == 0 and q.get('trait_positive_dimension'):
        dimension_count = 1
    return (
        dimension_count,
        q.get('discrimination_score', 0.0),
        -q.get('display_order', 0),
        -q.get('id', 0),
    )


def _get_likert_signal_sides(q: dict, scale_value: int | None) -> tuple[dict[str, float], dict[str, float], float]:
    if scale_value is None or scale_value == 0:
        return {}, {}, 0.0
    agree_signals = q.get('agree_dimension_signals') or {}
    disagree_signals = q.get('disagree_dimension_signals') or {}
    if not agree_signals and q.get('trait_positive_dimension'):
        agree_signals = {q['trait_positive_dimension']: 1.0}
    answer_strength = min(1.0, abs(float(scale_value)) / 2.0)
    if scale_value > 0:
        return agree_signals, disagree_signals, answer_strength
    return disagree_signals, agree_signals, answer_strength


def _score_dimension_overlap(signals: dict[str, float], profile: dict[str, float], idf_weights: dict[str, float]) -> float:
    score = 0.0
    for dimension_key, signal_weight in signals.items():
        try:
            clean_signal_weight = max(float(signal_weight), 0.0)
        except (TypeError, ValueError):
            continue
        if clean_signal_weight <= 0:
            continue
        score += clean_signal_weight * max(float(profile.get(dimension_key, 0.0)), 0.0) * idf_weights.get(dimension_key, 1.0)
    return score


def _score_roles_for_answer(
    q: dict,
    scale_value: int | None,
    role_profile_weights: dict,
    role_dimension_idf: dict,
) -> dict[str, float]:
    selected_signals, rejected_signals, answer_strength = _get_likert_signal_sides(q, scale_value)
    if answer_strength <= 0 or (not selected_signals and not rejected_signals):
        return {}

    answer_direction = 1.0 if scale_value and scale_value > 0 else -1.0
    role_scores: dict[str, float] = {}
    for role_slug, profile in role_profile_weights.items():
        agree_overlap = _score_dimension_overlap(q.get('agree_dimension_signals') or {}, profile, role_dimension_idf)
        disagree_overlap = _score_dimension_overlap(q.get('disagree_dimension_signals') or {}, profile, role_dimension_idf)
        if not q.get('agree_dimension_signals') and q.get('trait_positive_dimension'):
            agree_overlap = _score_dimension_overlap({q['trait_positive_dimension']: 1.0}, profile, role_dimension_idf)
        role_signal = answer_direction * (agree_overlap - disagree_overlap)
        role_scores[role_slug] = ROLE_EVIDENCE_SCORE_SCALE * answer_strength * _log_sigmoid(ROLE_EVIDENCE_LOGISTIC_SCALE * role_signal)
    return role_scores


def _build_role_distribution(role_scores: dict[str, float], active_role_slugs: list[str]) -> dict[str, float]:
    if not active_role_slugs:
        return {}

    evidence_scores = {role_slug: float(role_scores.get(role_slug, 0.0)) for role_slug in active_role_slugs}
    max_score = max(evidence_scores.values(), default=0.0)
    if all(score == 0.0 for score in evidence_scores.values()):
        uniform_probability = 1.0 / len(active_role_slugs)
        return dict.fromkeys(active_role_slugs, uniform_probability)

    adjusted_scores = {
        role_slug: math.exp((score - max_score) * ROLE_SCORE_SOFTMAX_TEMPERATURE) + DEFAULT_ROLE_PRIOR_WEIGHT
        for role_slug, score in evidence_scores.items()
    }
    total = sum(adjusted_scores.values())
    if total <= 0:
        uniform_probability = 1.0 / len(active_role_slugs)
        return dict.fromkeys(active_role_slugs, uniform_probability)
    return {role_slug: score / total for role_slug, score in adjusted_scores.items()}


def _normalize_entropy(distribution: dict[str, float], active_role_slugs: list[str]) -> float:
    if len(active_role_slugs) <= 1:
        return 0.0
    if not distribution:
        return 1.0
    entropy = -sum(probability * math.log(probability) for probability in distribution.values() if probability > 0)
    return min(1.0, entropy / math.log(len(active_role_slugs)))


def _select_question_for_session(
    current_role_scores: dict[str, float],
    current_distribution: dict[str, float],
    candidates: list[dict],
    active_role_slugs: list[str],
    role_profile_weights: dict,
    role_dimension_idf: dict,
    pre_selection_uncertainty: float,
    question_static_cache: dict,
) -> dict:
    num_roles = len(active_role_slugs)
    if num_roles <= 1:
        expected_entropies = {q['id']: 0.0 for q in candidates}
    else:
        inv_log_num_roles = 1.0 / math.log(num_roles)
        current_scores_list = [current_role_scores[slug] for slug in active_role_slugs]
        current_dist_list = [current_distribution[slug] for slug in active_role_slugs]

        expected_entropies = {}

        for question in candidates:
            q_id = question['id']
            cache_key = (q_id, tuple(active_role_slugs))
            if cache_key not in question_static_cache:
                overlap_diffs = []
                for role_slug in active_role_slugs:
                    profile = role_profile_weights.get(role_slug, {})
                    agree_overlap = _score_dimension_overlap(question.get('agree_dimension_signals') or {}, profile, role_dimension_idf)
                    disagree_overlap = _score_dimension_overlap(question.get('disagree_dimension_signals') or {}, profile, role_dimension_idf)
                    if not question.get('agree_dimension_signals') and question.get('trait_positive_dimension'):
                        agree_overlap = _score_dimension_overlap({question['trait_positive_dimension']: 1.0}, profile, role_dimension_idf)
                    x = agree_overlap - disagree_overlap
                    overlap_diffs.append(x)

                # Precompute role score deltas for v in [-2, -1, 1, 2]
                deltas = {}
                for v in [-2, -1, 1, 2]:
                    answer_direction = 1.0 if v > 0 else -1.0
                    answer_strength = min(1.0, abs(float(v)) / 2.0)
                    v_deltas = []
                    for x in overlap_diffs:
                        role_signal = answer_direction * x
                        d = ROLE_EVIDENCE_SCORE_SCALE * answer_strength * _log_sigmoid(ROLE_EVIDENCE_LOGISTIC_SCALE * role_signal)
                        v_deltas.append(d)
                    deltas[v] = v_deltas
                question_static_cache[cache_key] = (overlap_diffs, deltas)

            overlap_diffs, deltas = question_static_cache[cache_key]

            # Compute P(v) for all v in [-2, -1, 0, 1, 2]
            p_neg2 = 0.0
            p_neg1 = 0.0
            p_0 = 0.0
            p_pos1 = 0.0
            p_pos2 = 0.0
            for idx in range(num_roles):
                curr_dist = current_dist_list[idx]
                x = overlap_diffs[idx]
                e1 = math.exp(SOFTMAX_OMEGA * x)
                e2 = e1 * e1
                u_neg2 = 0.10 / e2
                u_neg1 = 0.20 / e1
                u_0 = 0.40
                u_pos1 = 0.20 * e1
                u_pos2 = 0.10 * e2
                inv_total_u = 1.0 / (u_neg2 + u_neg1 + u_0 + u_pos1 + u_pos2)
                p_neg2 += (u_neg2 * inv_total_u) * curr_dist
                p_neg1 += (u_neg1 * inv_total_u) * curr_dist
                p_0 += (u_0 * inv_total_u) * curr_dist
                p_pos1 += (u_pos1 * inv_total_u) * curr_dist
                p_pos2 += (u_pos2 * inv_total_u) * curr_dist

            expected_entropy = 0.0
            for v in [-2, -1, 1, 2]:
                p_v = p_neg2 if v == -2 else (p_neg1 if v == -1 else (p_pos1 if v == 1 else p_pos2))
                if p_v <= 0:
                    continue

                v_deltas = deltas[v]
                # Single-pass entropy calculation
                max_score = -999999.0
                new_scores = []
                all_zero = True
                for idx in range(num_roles):
                    ns = current_scores_list[idx] + v_deltas[idx]
                    new_scores.append(ns)
                    max_score = max(max_score, ns)
                    if ns != 0.0:
                        all_zero = False

                if all_zero:
                    new_entropy = 1.0
                else:
                    total = 0.0
                    sum_adj_log_adj = 0.0
                    for ns in new_scores:
                        adj = math.exp((ns - max_score) * ROLE_SCORE_SOFTMAX_TEMPERATURE) + DEFAULT_ROLE_PRIOR_WEIGHT
                        total += adj
                        sum_adj_log_adj += adj * math.log(adj)

                    if total <= 0:
                        new_entropy = 1.0
                    else:
                        entropy = math.log(total) - sum_adj_log_adj / total
                        new_entropy = min(1.0, entropy * inv_log_num_roles)

                expected_entropy += p_v * new_entropy

            # Bypass evaluation for v = 0 response: use pre_selection_uncertainty
            if p_0 > 0:
                expected_entropy += p_0 * pre_selection_uncertainty

            expected_entropies[q_id] = expected_entropy

    def selection_key(q: dict) -> tuple:
        h_score = _score_role_question(q)
        return (
            expected_entropies[q['id']],
            -h_score[0],
            -h_score[1],
            q['display_order'],
            q['id']
        )

    return min(candidates, key=selection_key)


class InMemorySession:
    def __init__(self, active_role_slugs: list[str]):
        self.active_role_slugs = active_role_slugs
        self.answers = []
        self.role_scores = dict.fromkeys(active_role_slugs, 0.0)
        self.dimension_scores = defaultdict(float)
        self.dimension_evidence_counts = defaultdict(int)
        self.uses_dimension_scoring = False
        self.phase = 'role_discovery'
        self.status = 'in_progress'

    def add_answer(self, q: dict, scale_value: int, role_profile_weights: dict, role_dimension_idf: dict):
        self.answers.append({'question_id': q['id'], 'scale_value': scale_value})

        if scale_value != 0:
            agree_signals = q.get('agree_dimension_signals') or {}
            disagree_signals = q.get('disagree_dimension_signals') or {}
            if not agree_signals and q.get('trait_positive_dimension'):
                agree_signals = {q['trait_positive_dimension']: 1.0}

            source_signals = agree_signals if scale_value > 0 else disagree_signals
            multiplier = abs(float(scale_value))
            for dimension_key, raw_weight in source_signals.items():
                try:
                    weight = float(raw_weight)
                except (TypeError, ValueError):
                    continue
                if not dimension_key or weight <= 0:
                    continue
                self.uses_dimension_scoring = True
                self.dimension_scores[dimension_key] += weight * multiplier
                self.dimension_evidence_counts[dimension_key] += 1

        deltas = _score_roles_for_answer(q, scale_value, role_profile_weights, role_dimension_idf)
        for role_slug, delta in deltas.items():
            self.role_scores[role_slug] += delta

    def get_role_inference_snapshot(self, role_profile_weights: dict, role_dimension_idf: dict) -> dict:
        role_scores = {role_slug: (self.role_scores.get(role_slug, 0.0) if self.uses_dimension_scoring else 0.0)
                       for role_slug in self.active_role_slugs}
        sorted_scores = sorted(role_scores.items(), key=lambda item: (-item[1], item[0]))
        role_distribution = _build_role_distribution(role_scores, self.active_role_slugs)
        top_slug, top_score = sorted_scores[0] if sorted_scores else (None, 0.0)
        runner_up_score = sorted_scores[1][1] if len(sorted_scores) > 1 else 0.0
        winner_share = role_distribution.get(top_slug, 0.0) if top_slug else 0.0
        margin_share = top_score - runner_up_score
        entropy = _normalize_entropy(role_distribution, self.active_role_slugs)

        answered_core_questions = len(self.answers)
        evidence_factor = min(1.0, answered_core_questions / float(ROLE_DISCOVERY_CORE_QUESTION_TARGET))
        confidence = max(0.0, min(1.0, winner_share * evidence_factor)) if self.uses_dimension_scoring else 0.0

        return {
            'sorted_scores': sorted_scores,
            'top_role_slug': top_slug,
            'winner_share': winner_share,
            'margin_share': margin_share,
            'entropy': entropy,
            'evidence_factor': evidence_factor,
            'confidence': confidence,
            'uses_dimension_scoring': self.uses_dimension_scoring,
            'dimension_scores': self.dimension_scores,
            'dimension_evidence_counts': self.dimension_evidence_counts,
            'answered_core_questions': answered_core_questions,
            'ranked_roles': [{'slug': slug, 'fit_score': score} for slug, score in sorted_scores],
        }

    def is_role_inference_resolved(self, snapshot: dict) -> bool:
        if snapshot['top_role_slug'] is None:
            return False
        if snapshot['answered_core_questions'] < ROLE_DISCOVERY_CORE_QUESTION_TARGET:
            return False

        top_role_slug = snapshot['top_role_slug']
        required_dimensions = ROLE_SPECIALIZATION_REQUIREMENTS.get(top_role_slug, ())
        specialization_satisfied = True
        if required_dimensions:
            specialization_satisfied = any(
                float(self.dimension_scores.get(dim, 0.0)) >= ROLE_SPECIALIZATION_EVIDENCE_THRESHOLD
                for dim in required_dimensions
            )

        return (
            snapshot['confidence'] >= ROLE_DISCOVERY_CONFIDENCE_THRESHOLD
            and snapshot['margin_share'] >= ROLE_DISCOVERY_MIN_MARGIN
            and specialization_satisfied
        )

    def get_role_resolution_status(self, snapshot: dict, has_remaining_questions: bool) -> str:
        if snapshot['answered_core_questions'] < ROLE_DISCOVERY_CORE_QUESTION_TARGET:
            return 'in_progress'
        if snapshot['top_role_slug'] is None:
            return 'unknown'
        if self.is_role_inference_resolved(snapshot):
            return 'resolved'
        if has_remaining_questions:
            return 'in_progress'
        return 'ambiguous'

    def update_phase(self, snapshot: dict, has_remaining_questions: bool):
        resolved = self.is_role_inference_resolved(snapshot)
        if not resolved and has_remaining_questions:
            self.phase = 'role_discovery'
            self.status = 'in_progress'
        elif not resolved:
            self.phase = 'role_ambiguity'
            self.status = 'in_progress'
        else:
            self.phase = 'skill_assessment'
            self.status = 'in_progress'


def _init_worker(temp: float, conf: float, margin: float, omega: float, scale: float, logistic: float, spec: float, prior: float):
    global ROLE_SCORE_SOFTMAX_TEMPERATURE
    global ROLE_DISCOVERY_CONFIDENCE_THRESHOLD
    global ROLE_DISCOVERY_MIN_MARGIN
    global SOFTMAX_OMEGA
    global ROLE_EVIDENCE_SCORE_SCALE
    global ROLE_EVIDENCE_LOGISTIC_SCALE
    global ROLE_SPECIALIZATION_EVIDENCE_THRESHOLD
    global DEFAULT_ROLE_PRIOR_WEIGHT

    ROLE_SCORE_SOFTMAX_TEMPERATURE = temp
    ROLE_DISCOVERY_CONFIDENCE_THRESHOLD = conf
    ROLE_DISCOVERY_MIN_MARGIN = margin
    SOFTMAX_OMEGA = omega
    ROLE_EVIDENCE_SCORE_SCALE = scale
    ROLE_EVIDENCE_LOGISTIC_SCALE = logistic
    ROLE_SPECIALIZATION_EVIDENCE_THRESHOLD = spec
    DEFAULT_ROLE_PRIOR_WEIGHT = prior


def run_single_inmemory_sample(
    sample_index: int,
    prefix_answers: list[int],
    likert_weights: dict[int, float],
    preferred_role_slug: str | None,
    active_role_slugs: list[str],
    questions_list: list[dict],
    role_profile_weights: dict,
    role_dimension_idf: dict,
    pre_generated_choices: list[int],
) -> dict:
    session = InMemorySession(active_role_slugs)
    answered_role_questions = 0
    random_choice_idx = 0

    while True:
        answered_ids = {ans['question_id'] for ans in session.answers}
        unanswered_questions = [q for q in questions_list if q['id'] not in answered_ids]

        candidates = [q for q in unanswered_questions if q['item_group'] == 'core']
        candidates.sort(key=lambda q: (q['display_order'], q['id']))

        if not candidates:
            break

        if session.phase != 'role_discovery' or session.status == 'completed':
            break

        current_role_scores = {slug: (session.role_scores.get(slug, 0.0) if session.uses_dimension_scoring else 0.0)
                               for slug in active_role_slugs}
        current_distribution = _build_role_distribution(current_role_scores, active_role_slugs)
        pre_selection_uncertainty = _normalize_entropy(current_distribution, active_role_slugs)

        chosen_question = _select_question_for_session(
            current_role_scores=current_role_scores,
            current_distribution=current_distribution,
            candidates=candidates,
            active_role_slugs=active_role_slugs,
            role_profile_weights=role_profile_weights,
            role_dimension_idf=role_dimension_idf,
            pre_selection_uncertainty=pre_selection_uncertainty,
            question_static_cache=GLOBAL_STATIC_CACHE,
        )

        if answered_role_questions < len(prefix_answers):
            scale_value = prefix_answers[answered_role_questions]
        else:
            scale_value = pre_generated_choices[random_choice_idx]
            random_choice_idx += 1

        session.add_answer(chosen_question, scale_value, role_profile_weights, role_dimension_idf)
        answered_role_questions += 1

        snapshot = session.get_role_inference_snapshot(role_profile_weights, role_dimension_idf)

        has_remaining = False
        answered_ids_after = {ans['question_id'] for ans in session.answers}
        for q in questions_list:
            if q['id'] not in answered_ids_after and q['item_group'] == 'core':
                has_remaining = True
                break

        session.update_phase(snapshot, has_remaining)

    snapshot = session.get_role_inference_snapshot(role_profile_weights, role_dimension_idf)

    answered_ids_final = {ans['question_id'] for ans in session.answers}
    has_remaining_final = any(q['id'] not in answered_ids_final and q['item_group'] == 'core' for q in questions_list)
    resolution_status = session.get_role_resolution_status(snapshot, has_remaining_final)

    best_fit_role_slug = snapshot['top_role_slug'] if resolution_status == 'resolved' else None

    return {
        'answered_role_questions': answered_role_questions,
        'resolution_status': resolution_status,
        'phase': session.phase,
        'confidence': float(snapshot['confidence']),
        'resolved_role_slug': best_fit_role_slug,
        'top_ranked_role_slug': snapshot['top_role_slug'],
    }


def _format_counter(counts: Counter[str], sample_count: int, *, limit: int | None = None, all_slugs: list[str] | None = None):
    normalized_counts = Counter(counts)
    for slug in all_slugs or []:
        normalized_counts.setdefault(slug, 0)
    items = sorted(normalized_counts.items(), key=lambda item: (-item[1], item[0]))
    if limit is not None:
        items = items[:limit]
    return [
        {
            'slug': slug,
            'count': count,
            'probability': count / sample_count,
        }
        for slug, count in items
    ]


def _distribution_metrics(counts: Counter[str], sample_count: int, role_slugs: list[str]) -> dict[str, object]:
    total_count = sum(counts[slug] for slug in role_slugs)
    if total_count <= 0:
        return {
            'sample_rate': 0.0,
            'hit_role_count': 0,
            'zero_hit_role_count': len(role_slugs),
            'role_coverage_rate': 0.0,
            'effective_role_count': 0.0,
            'normalized_entropy': 0.0,
            'top_role_slug': None,
            'top_role_probability': 0.0,
            'top_3_probability_mass': 0.0,
        }

    probabilities = [counts[slug] / total_count for slug in role_slugs]
    non_zero_probabilities = [probability for probability in probabilities if probability > 0]
    entropy = -sum(probability * math.log(probability) for probability in non_zero_probabilities)
    normalized_entropy = entropy / math.log(len(role_slugs)) if len(role_slugs) > 1 else 0.0
    concentration = sum(probability**2 for probability in probabilities)
    top_slug, top_count = max(((slug, counts[slug]) for slug in role_slugs), key=lambda item: (item[1], item[0]))
    sorted_probabilities = sorted(probabilities, reverse=True)
    return {
        'sample_rate': total_count / sample_count,
        'hit_role_count': sum(1 for probability in probabilities if probability > 0),
        'zero_hit_role_count': sum(1 for probability in probabilities if probability == 0),
        'role_coverage_rate': sum(1 for probability in probabilities if probability > 0) / len(role_slugs),
        'effective_role_count': (1 / concentration) if concentration > 0 else 0.0,
        'normalized_entropy': normalized_entropy,
        'top_role_slug': top_slug,
        'top_role_probability': top_count / total_count,
        'top_3_probability_mass': sum(sorted_probabilities[:3]),
    }


def main():
    parser = argparse.ArgumentParser(description='Simulate Monte Carlo role probabilities in parallel & in memory.')
    parser.add_argument('--samples', type=int, default=100)
    parser.add_argument('--answers', default='')
    parser.add_argument('--likert-weights', default='1,1,1,1,1')
    parser.add_argument('--random-seed', type=int, default=12345)
    parser.add_argument('--preferred-role-slug', default=None)
    parser.add_argument('--top-roles', type=int, default=10)
    parser.add_argument('--temp', type=float, default=1.15)
    parser.add_argument('--conf', type=float, default=0.28)
    parser.add_argument('--margin', type=float, default=0.75)
    parser.add_argument('--omega', type=float, default=0.35)
    parser.add_argument('--scale', type=float, default=3.0)
    parser.add_argument('--logistic', type=float, default=0.7)
    parser.add_argument('--spec', type=float, default=0.5)
    parser.add_argument('--prior', type=float, default=0.001)

    args = parser.parse_args()

    # Check if any hyperparameter argument was provided in the command line
    has_hyperparameter_args = any(
        arg.startswith(('--temp', '--conf', '--margin', '--omega', '--scale', '--logistic', '--spec', '--prior'))
        for arg in sys.argv
    )
    if has_hyperparameter_args:
        global ROLE_SCORE_SOFTMAX_TEMPERATURE
        global ROLE_DISCOVERY_CONFIDENCE_THRESHOLD
        global ROLE_DISCOVERY_MIN_MARGIN
        global SOFTMAX_OMEGA
        global ROLE_EVIDENCE_SCORE_SCALE
        global ROLE_EVIDENCE_LOGISTIC_SCALE
        global ROLE_SPECIALIZATION_EVIDENCE_THRESHOLD
        global DEFAULT_ROLE_PRIOR_WEIGHT

        ROLE_SCORE_SOFTMAX_TEMPERATURE = args.temp
        ROLE_DISCOVERY_CONFIDENCE_THRESHOLD = args.conf
        ROLE_DISCOVERY_MIN_MARGIN = args.margin
        SOFTMAX_OMEGA = args.omega
        ROLE_EVIDENCE_SCORE_SCALE = args.scale
        ROLE_EVIDENCE_LOGISTIC_SCALE = args.logistic
        ROLE_SPECIALIZATION_EVIDENCE_THRESHOLD = args.spec
        DEFAULT_ROLE_PRIOR_WEIGHT = args.prior

    # Parse prefix answers
    prefix_answers = []
    if args.answers.strip():
        for val in args.answers.split(','):
            val_int = int(val.strip())
            if val_int not in LIKERT_VALUES:
                sys.exit(f"Invalid answer: {val_int}. Must be in -2,-1,0,1,2")
            prefix_answers.append(val_int)

    # Parse likert weights
    weights_parts = [part.strip() for part in args.likert_weights.split(',') if part.strip()]
    if len(weights_parts) != len(LIKERT_VALUES):
        sys.exit(f"--likert-weights must have exactly 5 comma-separated values for {LIKERT_VALUES}")

    likert_weights = {}
    for value, part in zip(LIKERT_VALUES, weights_parts, strict=True):
        weight = float(part)
        if weight < 0:
            sys.exit("--likert-weights cannot be negative")
        likert_weights[value] = weight
    if sum(likert_weights.values()) <= 0:
        sys.exit("--likert-weights must sum to > 0")

    # Fetch data from Django models
    active_role_slugs = list(Role.objects.filter(is_active=True).order_by('slug').values_list('slug', flat=True))

    serialized_questions = [
        {
            'id': q.id,
            'code': q.code,
            'stage': q.stage,
            'item_group': q.item_group,
            'question_type': q.question_type,
            'agree_dimension_signals': q.agree_dimension_signals,
            'disagree_dimension_signals': q.disagree_dimension_signals,
            'trait_positive_dimension': q.trait_positive_dimension,
            'discrimination_score': float(q.discrimination_score) if q.discrimination_score is not None else 0.0,
            'display_order': q.display_order,
        }
        for q in Question.objects.filter(stage=Question.Stage.ROLE, is_active=True)
    ]

    # Validate preferred role
    preferred_role_slug = None
    if args.preferred_role_slug:
        if not Role.objects.filter(slug=args.preferred_role_slug, is_active=True).exists():
            sys.exit(f"Unknown active role slug: {args.preferred_role_slug}")
        preferred_role_slug = args.preferred_role_slug

    # Pre-generate choices sequentially using sequential RNG
    rng = random.Random(args.random_seed)
    num_random_needed = ROLE_DISCOVERY_CORE_QUESTION_TARGET - len(prefix_answers)
    all_sample_choices = []
    for _ in range(args.samples):
        choices = [
            rng.choices(
                population=list(LIKERT_VALUES),
                weights=[likert_weights[v] for v in LIKERT_VALUES],
                k=1
            )[0]
            for _ in range(num_random_needed)
        ]
        all_sample_choices.append(choices)

    # Run samples in parallel using ProcessPoolExecutor
    results = []
    with concurrent.futures.ProcessPoolExecutor(
        initializer=_init_worker,
        initargs=(
            ROLE_SCORE_SOFTMAX_TEMPERATURE,
            ROLE_DISCOVERY_CONFIDENCE_THRESHOLD,
            ROLE_DISCOVERY_MIN_MARGIN,
            SOFTMAX_OMEGA,
            ROLE_EVIDENCE_SCORE_SCALE,
            ROLE_EVIDENCE_LOGISTIC_SCALE,
            ROLE_SPECIALIZATION_EVIDENCE_THRESHOLD,
            DEFAULT_ROLE_PRIOR_WEIGHT,
        )
    ) as executor:
        futures = [
            executor.submit(
                run_single_inmemory_sample,
                idx,
                prefix_answers,
                likert_weights,
                preferred_role_slug,
                active_role_slugs,
                serialized_questions,
                ROLE_PROFILE_WEIGHTS,
                ROLE_DIMENSION_IDF,
                all_sample_choices[idx]
            )
            for idx in range(args.samples)
        ]
        results = [f.result() for f in futures]

    # Aggregate results
    resolution_status_counts = Counter()
    phase_counts = Counter()
    resolved_role_counts = Counter()
    top_ranked_role_counts = Counter()
    answered_role_question_total = 0
    confidence_total = 0.0

    for sample in results:
        resolution_status_counts[sample['resolution_status']] += 1
        phase_counts[sample['phase']] += 1
        answered_role_question_total += sample['answered_role_questions']
        confidence_total += sample['confidence']
        if sample['resolved_role_slug'] is not None:
            resolved_role_counts[sample['resolved_role_slug']] += 1
        if sample['top_ranked_role_slug'] is not None:
            top_ranked_role_counts[sample['top_ranked_role_slug']] += 1

    summary = {
        'samples': args.samples,
        'prefix_answers': prefix_answers,
        'likert_values': list(LIKERT_VALUES),
        'likert_weights': {key: likert_weights[key] for key in LIKERT_VALUES},
        'preferred_role_slug': preferred_role_slug,
        'active_role_count': len(active_role_slugs),
        'average_answered_role_questions': answered_role_question_total / args.samples,
        'average_confidence': confidence_total / args.samples,
        'resolution_status_rates': _format_counter(resolution_status_counts, args.samples),
        'phase_rates': _format_counter(phase_counts, args.samples),
        'resolved_role_rates': _format_counter(resolved_role_counts, args.samples, limit=args.top_roles, all_slugs=active_role_slugs),
        'top_ranked_role_rates': _format_counter(top_ranked_role_counts, args.samples, limit=args.top_roles, all_slugs=active_role_slugs),
        'questionnaire_metrics': {
            'resolved_rate': resolution_status_counts['resolved'] / args.samples,
            'ambiguous_rate': resolution_status_counts['ambiguous'] / args.samples,
            'unknown_rate': resolution_status_counts['unknown'] / args.samples,
            'in_progress_rate': resolution_status_counts['in_progress'] / args.samples,
            'top_ranked_distribution': _distribution_metrics(top_ranked_role_counts, args.samples, active_role_slugs),
            'resolved_role_distribution': _distribution_metrics(resolved_role_counts, args.samples, active_role_slugs),
            'worst_case_95pct_margin_of_error': 1.96 * ((0.25 / args.samples) ** 0.5),
        },
    }

    # Print Text Summary matching exactly the format of estimate_role_probabilities.py
    sys.stdout.write(f"Samples: {summary['samples']}\n")
    sys.stdout.write(f"Prefix answers: {summary['prefix_answers'] or 'none'}\n")
    sys.stdout.write(f"Preferred role: {summary['preferred_role_slug'] or 'none'}\n")
    sys.stdout.write(f"Likert weights: {summary['likert_weights']}\n")
    sys.stdout.write(f"Avg answered role questions: {summary['average_answered_role_questions']:.2f}\n")
    sys.stdout.write(f"Avg confidence: {summary['average_confidence']:.4f}\n")
    sys.stdout.write('\n')
    sys.stdout.write('Resolution status rates:\n')
    for item in summary['resolution_status_rates']:
        sys.stdout.write(f"  {item['slug']}: {item['probability']:.4f} ({item['count']})\n")
    sys.stdout.write('\n')
    sys.stdout.write('Resolved role rates:\n')
    for item in summary['resolved_role_rates']:
        sys.stdout.write(f"  {item['slug']}: {item['probability']:.4f} ({item['count']})\n")
    sys.stdout.write('\n')
    sys.stdout.write('Top ranked role rates:\n')
    for item in summary['top_ranked_role_rates']:
        sys.stdout.write(f"  {item['slug']}: {item['probability']:.4f} ({item['count']})\n")
    sys.stdout.write('\n')
    sys.stdout.write('Questionnaire metrics:\n')
    metrics = summary['questionnaire_metrics']
    sys.stdout.write(f"  resolved_rate: {metrics['resolved_rate']:.4f}\n")
    sys.stdout.write(f"  ambiguous_rate: {metrics['ambiguous_rate']:.4f}\n")
    sys.stdout.write(f"  worst_case_95pct_margin_of_error: +/-{metrics['worst_case_95pct_margin_of_error']:.4f}\n")
    top_ranked_metrics = metrics['top_ranked_distribution']
    sys.stdout.write(f"  top_ranked.hit_role_count: {top_ranked_metrics['hit_role_count']}\n")
    sys.stdout.write(f"  top_ranked.effective_role_count: {top_ranked_metrics['effective_role_count']:.2f}\n")
    sys.stdout.write(f"  top_ranked.normalized_entropy: {top_ranked_metrics['normalized_entropy']:.4f}\n")
    sys.stdout.write(f"  top_ranked.top_3_probability_mass: {top_ranked_metrics['top_3_probability_mass']:.4f}\n")


if __name__ == '__main__':
    main()

