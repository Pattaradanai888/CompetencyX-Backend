import math
from collections import defaultdict
from dataclasses import dataclass

from roadmaps.models import Question, Role
from roadmaps.questionnaire import ROLE_DIMENSION_LABELS, ROLE_PROFILE_WEIGHTS

from .models import AssessmentSession


ROLE_DISCOVERY_CONFIDENCE_THRESHOLD = 0.28
ROLE_DISCOVERY_MIN_MARGIN = 0.75
ROLE_DISCOVERY_CORE_QUESTION_TARGET = 36
ROLE_DISCOVERY_MIN_QUESTIONS = ROLE_DISCOVERY_CORE_QUESTION_TARGET
MIN_TIE_BREAK_ROLE_COUNT = 2
ROLE_TIE_BREAK_CLUSTER_SIZE = 3
ROLE_TIE_BREAK_QUESTION_TARGET = 6
ROLE_SELECTION_POLICY_INFO_GAIN = 'info_gain'
DEFAULT_ROLE_PRIOR_WEIGHT = 0.001
ROLE_SCORE_SOFTMAX_TEMPERATURE = 1.15
ROLE_EVIDENCE_LOGISTIC_SCALE = 0.7
ROLE_EVIDENCE_SCORE_SCALE = 3.0
ROLE_SPECIALIZATION_EVIDENCE_THRESHOLD = 0.5
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


@dataclass(frozen=True)
class RoleEvidenceSnapshot:
    role_scores: dict[str, float]
    dimension_scores: dict[str, float]
    dimension_evidence_counts: dict[str, int]
    uses_dimension_scoring: bool


class RoleQuestionSelectionError(ValueError):
    """Raised when no role-discovery question can be selected."""


def _get_answered_core_role_question_count(session: AssessmentSession) -> int:
    return session.answers.filter(question__stage=Question.Stage.ROLE, question__item_group=Question.ItemGroup.CORE).count()


def _get_answered_tie_break_question_count(session: AssessmentSession) -> int:
    return session.answers.filter(question__stage=Question.Stage.ROLE, question__item_group=Question.ItemGroup.TIE_BREAK).count()


def _is_core_role_profile_complete(session: AssessmentSession) -> bool:
    return _get_answered_core_role_question_count(session) >= ROLE_DISCOVERY_CORE_QUESTION_TARGET


def _compute_role_distribution(session: AssessmentSession) -> dict[str, float]:
    active_role_slugs = list(Role.objects.filter(is_active=True).values_list('slug', flat=True))
    return _build_role_distribution(_build_role_evidence_snapshot(session).role_scores, active_role_slugs)


def _build_role_evidence_snapshot(session: AssessmentSession) -> RoleEvidenceSnapshot:
    answers = session.answers.filter(question__stage=Question.Stage.ROLE).select_related('question')
    dimension_scores = defaultdict(float)
    dimension_evidence_counts = defaultdict(int)
    role_scores = defaultdict(float)
    uses_dimension_scoring = False
    for answer in answers:
        if answer.question.question_type != Question.Type.LIKERT_5:
            continue
        for dimension_key, weight in _get_likert_dimension_signals(answer.question, answer.scale_value).items():
            if weight <= 0:
                continue
            uses_dimension_scoring = True
            dimension_scores[dimension_key] += weight
            dimension_evidence_counts[dimension_key] += 1
        for role_slug, delta in _score_roles_for_answer(answer.question, answer.scale_value).items():
            role_scores[role_slug] += delta

    return RoleEvidenceSnapshot(
        role_scores=dict(role_scores) if uses_dimension_scoring else {},
        dimension_scores=dict(dimension_scores),
        dimension_evidence_counts=dict(dimension_evidence_counts),
        uses_dimension_scoring=uses_dimension_scoring,
    )


def _get_likert_dimension_signals(question: Question, scale_value: int | None) -> dict[str, float]:
    if scale_value is None or scale_value == 0:
        return {}
    source_signals = question.agree_dimension_signals if scale_value > 0 else question.disagree_dimension_signals
    if not source_signals and scale_value > 0 and question.trait_positive_dimension:
        source_signals = {question.trait_positive_dimension: 1.0}
    multiplier = abs(float(scale_value))
    signals: dict[str, float] = {}
    for dimension_key, raw_weight in (source_signals or {}).items():
        try:
            weight = float(raw_weight)
        except (TypeError, ValueError):
            continue
        if not dimension_key or weight <= 0:
            continue
        signals[str(dimension_key)] = signals.get(str(dimension_key), 0.0) + (weight * multiplier)
    return signals


def _score_roles_from_dimensions(dimension_scores: dict[str, float]) -> dict[str, float]:
    if not dimension_scores:
        return {}

    role_scores: dict[str, float] = {}
    for role_slug, profile in ROLE_PROFILE_WEIGHTS.items():
        role_scores[role_slug] = _score_dimension_overlap(dimension_scores, profile, _ROLE_DIMENSION_IDF)
    return role_scores


def _score_roles_for_answer(question: Question, scale_value: int | None) -> dict[str, float]:
    selected_signals, rejected_signals, answer_strength = _get_likert_signal_sides(question, scale_value)
    if answer_strength <= 0 or (not selected_signals and not rejected_signals):
        return {}

    answer_direction = 1.0 if scale_value and scale_value > 0 else -1.0
    role_scores: dict[str, float] = {}
    for role_slug, profile in ROLE_PROFILE_WEIGHTS.items():
        agree_overlap = _score_dimension_overlap(question.agree_dimension_signals or {}, profile, _ROLE_DIMENSION_IDF)
        disagree_overlap = _score_dimension_overlap(question.disagree_dimension_signals or {}, profile, _ROLE_DIMENSION_IDF)
        if not question.agree_dimension_signals and question.trait_positive_dimension:
            agree_overlap = _score_dimension_overlap({question.trait_positive_dimension: 1.0}, profile, _ROLE_DIMENSION_IDF)
        role_signal = answer_direction * (agree_overlap - disagree_overlap)
        role_scores[role_slug] = ROLE_EVIDENCE_SCORE_SCALE * answer_strength * _log_sigmoid(ROLE_EVIDENCE_LOGISTIC_SCALE * role_signal)
    return role_scores


def _get_likert_signal_sides(question: Question, scale_value: int | None) -> tuple[dict[str, float], dict[str, float], float]:
    if scale_value is None or scale_value == 0:
        return {}, {}, 0.0
    agree_signals = question.agree_dimension_signals or {}
    disagree_signals = question.disagree_dimension_signals or {}
    if not agree_signals and question.trait_positive_dimension:
        agree_signals = {question.trait_positive_dimension: 1.0}
    answer_strength = min(1.0, abs(float(scale_value)) / 2.0)
    if scale_value > 0:
        return agree_signals, disagree_signals, answer_strength
    return disagree_signals, agree_signals, answer_strength


def _score_dimension_overlap(signals: dict[str, float], profile: dict[str, float], idf_weights: dict[str, float]) -> float:
    score = 0.0
    for dimension_key, signal_weight in (signals or {}).items():
        try:
            clean_signal_weight = max(float(signal_weight), 0.0)
        except (TypeError, ValueError):
            continue
        if clean_signal_weight <= 0:
            continue
        score += clean_signal_weight * max(float(profile.get(dimension_key, 0.0)), 0.0) * idf_weights.get(dimension_key, 1.0)
    return score


def _log_sigmoid(value: float) -> float:
    if value >= 0:
        return -math.log1p(math.exp(-value))
    return value - math.log1p(math.exp(value))


def _compute_role_dimension_idf() -> dict[str, float]:
    role_count = len(ROLE_PROFILE_WEIGHTS)
    dimension_role_counts = defaultdict(int)
    for profile in ROLE_PROFILE_WEIGHTS.values():
        for dimension_key, weight in profile.items():
            if max(float(weight), 0.0) > 0:
                dimension_role_counts[dimension_key] += 1
    return {
        dimension_key: math.log((role_count + 1.0) / (role_count_for_dimension + 1.0)) + 1.0
        for dimension_key, role_count_for_dimension in dimension_role_counts.items()
    }


_ROLE_DIMENSION_IDF: dict[str, float] = _compute_role_dimension_idf()


def _get_sorted_role_scores(role_scores: dict[str, float]) -> list[tuple[str, float]]:
    return sorted(role_scores.items(), key=lambda item: (-item[1], item[0]))


def _has_remaining_role_questions(session: AssessmentSession) -> bool:
    unanswered_role_questions = list(
        Question.objects.filter(stage=Question.Stage.ROLE, is_active=True).exclude(id__in=session.answers.values_list('question_id', flat=True))
    )
    return bool(_get_selectable_role_candidates(session, unanswered_role_questions))


def _get_role_inference_snapshot(session: AssessmentSession) -> dict[str, object]:
    evidence_snapshot = _build_role_evidence_snapshot(session)
    active_role_slugs = list(Role.objects.filter(is_active=True).values_list('slug', flat=True))
    role_scores = {role_slug: evidence_snapshot.role_scores.get(role_slug, 0.0) for role_slug in active_role_slugs}
    sorted_scores = _get_sorted_role_scores(role_scores)
    role_distribution = _build_role_distribution(role_scores, active_role_slugs)
    top_slug, top_score = sorted_scores[0] if sorted_scores else (None, 0.0)
    runner_up_score = sorted_scores[1][1] if len(sorted_scores) > 1 else 0.0
    winner_share = role_distribution.get(top_slug, 0.0) if top_slug else 0.0
    margin_share = top_score - runner_up_score
    entropy = _normalize_entropy(role_distribution, active_role_slugs)
    answered_core_questions = _get_answered_core_role_question_count(session)
    evidence_factor = min(1.0, answered_core_questions / max(ROLE_DISCOVERY_CORE_QUESTION_TARGET, 1))
    confidence = max(0.0, min(1.0, winner_share * evidence_factor)) if evidence_snapshot.uses_dimension_scoring else 0.0
    total_dimension_score = sum(max(score, 0.0) for score in evidence_snapshot.dimension_scores.values())
    pillar_profile = [
        {
            'key': dimension_key,
            'label': ROLE_DIMENSION_LABELS.get(dimension_key, dimension_key.replace('_', ' ').title()),
            'raw_score': raw_score,
            'normalized_score': (raw_score / total_dimension_score) if total_dimension_score else 0.0,
            'evidence_count': evidence_snapshot.dimension_evidence_counts.get(dimension_key, 0),
        }
        for dimension_key, raw_score in sorted(
            evidence_snapshot.dimension_scores.items(),
            key=lambda item: (-item[1], item[0]),
        )
        if raw_score > 0
    ]
    role_names = {role.slug: role.name for role in Role.objects.filter(is_active=True, slug__in=[slug for slug, _score in sorted_scores])}
    ranked_roles = [
        {
            'slug': role_slug,
            'name': role_names.get(role_slug, role_slug),
            'fit_score': score,
            'fit_share': role_distribution.get(role_slug, 0.0),
            'top_supporting_pillars': _get_top_supporting_pillars(role_slug, evidence_snapshot.dimension_scores),
        }
        for role_slug, score in sorted_scores
    ]
    return {
        'sorted_scores': sorted_scores,
        'top_role_slug': top_slug,
        'winner_share': winner_share,
        'margin_share': margin_share,
        'entropy': entropy,
        'evidence_factor': evidence_factor,
        'confidence': confidence,
        'uses_dimension_scoring': evidence_snapshot.uses_dimension_scoring,
        'dimension_scores': evidence_snapshot.dimension_scores,
        'dimension_evidence_counts': evidence_snapshot.dimension_evidence_counts,
        'observed_pillars': sum(1 for score in evidence_snapshot.dimension_scores.values() if score > 0),
        'answered_core_questions': answered_core_questions,
        'answered_tie_break_questions': _get_answered_tie_break_question_count(session),
        'pillar_profile': pillar_profile,
        'ranked_roles': ranked_roles,
    }


def _is_role_inference_resolved(session: AssessmentSession) -> bool:
    snapshot = _get_role_inference_snapshot(session)
    return _is_role_resolution_exhausted_with_viable_winner(session, snapshot=snapshot)


def get_role_resolution_status(session: AssessmentSession) -> str:
    if not _is_core_role_profile_complete(session):
        return 'in_progress'
    if session.best_fit_role_id is None:
        return 'unknown'
    if _is_role_inference_resolved(session):
        return 'resolved'
    if _has_remaining_role_questions(session):
        return 'in_progress'
    return 'ambiguous'


def get_top_role_candidates(session: AssessmentSession, *, limit: int = 3) -> list[dict[str, object]]:
    snapshot = _get_role_inference_snapshot(session)
    return [
        {
            'slug': role['slug'],
            'name': role['name'],
            'score': role['fit_score'],
            'share': role['fit_share'],
        }
        for role in snapshot['ranked_roles'][:limit]
    ]


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


def _is_role_resolution_exhausted_with_viable_winner(
    session: AssessmentSession,
    *,
    snapshot: dict[str, object] | None = None,
) -> bool:
    snapshot = snapshot or _get_role_inference_snapshot(session)
    if snapshot['top_role_slug'] is None:
        return False
    if int(snapshot['answered_core_questions']) < ROLE_DISCOVERY_CORE_QUESTION_TARGET:
        return False
    return (
        float(snapshot['confidence']) >= ROLE_DISCOVERY_CONFIDENCE_THRESHOLD
        and float(snapshot['margin_share']) >= ROLE_DISCOVERY_MIN_MARGIN
        and _is_top_role_specialization_satisfied(snapshot)
    )


def _is_top_role_specialization_satisfied(snapshot: dict[str, object]) -> bool:
    return not _get_unmet_top_role_specialization_dimensions(snapshot)


def _get_unmet_top_role_specialization_dimensions(snapshot: dict[str, object]) -> tuple[str, ...]:
    top_role_slug = snapshot.get('top_role_slug')
    if not top_role_slug:
        return ()
    return _get_unmet_role_specialization_dimensions(str(top_role_slug), snapshot)


def _get_unmet_role_specialization_dimensions(role_slug: str, snapshot: dict[str, object]) -> tuple[str, ...]:
    required_dimensions = ROLE_SPECIALIZATION_REQUIREMENTS.get(role_slug, ())
    if not required_dimensions:
        return ()
    dimension_scores = snapshot.get('dimension_scores') or {}
    if any(float(dimension_scores.get(dimension_key, 0.0)) >= ROLE_SPECIALIZATION_EVIDENCE_THRESHOLD for dimension_key in required_dimensions):
        return ()
    return required_dimensions


def _question_targets_specialization(question: Question, role_slug: str, required_dimensions: tuple[str, ...]) -> bool:
    if role_slug not in (question.discriminates_between or []):
        return False
    dimension_keys = set(question.agree_dimension_signals or {}) | set(question.disagree_dimension_signals or {})
    return bool(dimension_keys & set(required_dimensions))


def _select_role_info_gain_question(session: AssessmentSession, candidates: list[Question]) -> tuple[Question, list[dict[str, object]]]:
    if _get_answered_core_role_question_count(session) < ROLE_DISCOVERY_CORE_QUESTION_TARGET:
        ordered_core_candidates = sorted(
            [question for question in candidates if question.item_group == Question.ItemGroup.CORE],
            key=lambda question: (question.display_order, question.id),
        )
        if ordered_core_candidates:
            return (
                ordered_core_candidates[0],
                [
                    {
                        'question_id': question.id,
                        'question_code': question.code,
                        'policy_score': 0.0,
                        'selection_score': float(ROLE_DISCOVERY_CORE_QUESTION_TARGET - question.display_order),
                        'heuristic_score': list(_score_role_question(question)),
                    }
                    for question in ordered_core_candidates
                ],
            )

    eligible_candidates = sorted(candidates, key=lambda question: (question.display_order, question.id))
    if not eligible_candidates:
        msg = 'No role questions are selectable for this session.'
        raise RoleQuestionSelectionError(msg)

    active_role_slugs = list(Role.objects.filter(is_active=True).values_list('slug', flat=True))
    current_distribution = _compute_role_distribution(session)
    current_entropy = _normalize_entropy(current_distribution, active_role_slugs)
    evidence_snapshot = _build_role_evidence_snapshot(session)
    coverage_snapshot = evidence_snapshot.dimension_evidence_counts
    scored_candidates: list[dict[str, object]] = []

    for question in eligible_candidates:
        expected_entropy = _calculate_expected_role_entropy(question, current_distribution, evidence_snapshot, active_role_slugs)
        expected_information_gain = max(0.0, current_entropy - expected_entropy)
        coverage_bonus = _calculate_coverage_bonus(question, coverage_snapshot)
        discrimination_prior = min(1.0, max(float(question.discrimination_score), 0.0) / 5.0)
        selection_score = expected_information_gain + (0.2 * coverage_bonus) + (0.05 * discrimination_prior)
        heuristic_score = _score_role_question(question)
        scored_candidates.append(
            {
                'question_id': question.id,
                'question_code': question.code,
                'policy_score': expected_information_gain,
                'selection_score': selection_score,
                'heuristic_score': list(heuristic_score),
                'expected_entropy': expected_entropy,
                'coverage_bonus': coverage_bonus,
            }
        )

    chosen_candidate = max(
        scored_candidates,
        key=lambda candidate: (
            float(candidate['selection_score']),
            tuple(candidate['heuristic_score']),
        ),
    )
    return (
        next(question for question in eligible_candidates if question.id == chosen_candidate['question_id']),
        scored_candidates,
    )


def _calculate_expected_role_entropy(
    question: Question,
    _current_distribution: dict[str, float],
    evidence_snapshot: RoleEvidenceSnapshot,
    active_role_slugs: list[str],
) -> float:
    if question.question_type != Question.Type.LIKERT_5:
        return 1.0

    scale_values = (-2, -1, 0, 1, 2)
    scale_probability = 1.0 / len(scale_values)
    expected_entropy = 0.0
    for scale_value in scale_values:
        projected_scores = _project_role_scores_for_scale(evidence_snapshot, question, scale_value)
        projected_distribution = _build_role_distribution(projected_scores, active_role_slugs)
        expected_entropy += scale_probability * _normalize_entropy(projected_distribution, active_role_slugs)
    return expected_entropy


def _calculate_expected_cluster_entropy(
    question: Question,
    evidence_snapshot: RoleEvidenceSnapshot,
    active_role_slugs: list[str],
    top_cluster: set[str],
) -> float:
    if question.question_type != Question.Type.LIKERT_5:
        return 1.0

    scale_values = (-2, -1, 0, 1, 2)
    scale_probability = 1.0 / len(scale_values)
    expected_entropy = 0.0
    for scale_value in scale_values:
        projected_scores = _project_role_scores_for_scale(evidence_snapshot, question, scale_value)
        expected_entropy += scale_probability * _cluster_entropy(projected_scores, active_role_slugs, top_cluster)
    return expected_entropy


def _cluster_entropy(role_scores: dict[str, float], active_role_slugs: list[str], top_cluster: set[str]) -> float:
    cluster_roles = [role_slug for role_slug in active_role_slugs if role_slug in top_cluster]
    if len(cluster_roles) <= 1:
        return 0.0
    cluster_distribution = _build_role_distribution(role_scores, cluster_roles)
    return _normalize_entropy(cluster_distribution, cluster_roles)


def _get_top_role_cluster(snapshot: dict[str, object]) -> set[str]:
    return {role['slug'] for role in snapshot['ranked_roles'][:ROLE_TIE_BREAK_CLUSTER_SIZE] if role.get('slug')}


def _tie_break_matches_cluster(question: Question, top_cluster: set[str]) -> bool:
    return len(set(question.discriminates_between or []) & top_cluster) >= MIN_TIE_BREAK_ROLE_COUNT


def _calculate_coverage_bonus(question: Question, dimension_evidence_counts: dict[str, int]) -> float:
    dimension_keys = set(question.agree_dimension_signals or {}) | set(question.disagree_dimension_signals or {})
    if not dimension_keys and question.trait_positive_dimension:
        dimension_keys.add(question.trait_positive_dimension)
    dimension_keys.discard(None)
    dimension_keys.discard('')
    if not dimension_keys:
        return 0.0
    coverage_scores = [1.0 / (1.0 + float(dimension_evidence_counts.get(dimension_key, 0))) for dimension_key in dimension_keys]
    return sum(coverage_scores) / len(coverage_scores)


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


def _project_role_scores_for_scale(evidence_snapshot: RoleEvidenceSnapshot, question: Question, scale_value: int) -> dict[str, float]:
    projected_role_scores = dict(evidence_snapshot.role_scores)
    for role_slug, delta in _score_roles_for_answer(question, scale_value).items():
        projected_role_scores[role_slug] = projected_role_scores.get(role_slug, 0.0) + delta
    return projected_role_scores


def _get_role_tie_break_candidates(
    session: AssessmentSession,
    candidates: list[Question],
    *,
    snapshot: dict[str, object] | None = None,
) -> list[Question]:
    snapshot = snapshot or _get_role_inference_snapshot(session)
    if (
        int(snapshot['answered_core_questions']) < ROLE_DISCOVERY_CORE_QUESTION_TARGET
        or int(snapshot['answered_tie_break_questions']) >= ROLE_TIE_BREAK_QUESTION_TARGET
        or _is_role_resolution_exhausted_with_viable_winner(session, snapshot=snapshot)
    ):
        return []

    tie_break_candidates = [question for question in candidates if question.item_group == Question.ItemGroup.TIE_BREAK]
    selected_candidates: list[Question] = []

    top_role_slug = str(snapshot['top_role_slug'] or '')
    unmet_specialization_dimensions = _get_unmet_top_role_specialization_dimensions(snapshot)
    if tie_break_candidates and top_role_slug and unmet_specialization_dimensions:
        selected_candidates = [
            question
            for question in tie_break_candidates
            if _question_targets_specialization(question, top_role_slug, unmet_specialization_dimensions)
        ]

    if tie_break_candidates and not selected_candidates:
        top_cluster = _get_top_role_cluster(snapshot)
        matching_candidates = [question for question in tie_break_candidates if _tie_break_matches_cluster(question, top_cluster)]

        active_role_slugs = list(Role.objects.filter(is_active=True).values_list('slug', flat=True))
        evidence_snapshot = _build_role_evidence_snapshot(session)
        current_entropy = _cluster_entropy(evidence_snapshot.role_scores, active_role_slugs, top_cluster)
        for question in matching_candidates:
            expected_entropy = _calculate_expected_cluster_entropy(question, evidence_snapshot, active_role_slugs, top_cluster)
            if current_entropy - expected_entropy > 0.0:
                selected_candidates.append(question)

    return sorted(selected_candidates, key=lambda question: (question.display_order, question.id))


def _get_selectable_role_candidates(
    session: AssessmentSession,
    candidates: list[Question],
    *,
    snapshot: dict[str, object] | None = None,
) -> list[Question]:
    snapshot = snapshot or _get_role_inference_snapshot(session)
    if int(snapshot['answered_core_questions']) < ROLE_DISCOVERY_CORE_QUESTION_TARGET:
        core_candidates = [question for question in candidates if question.item_group == Question.ItemGroup.CORE]
        return sorted(core_candidates, key=lambda question: (question.display_order, question.id))
    return _get_role_tie_break_candidates(session, candidates, snapshot=snapshot)


def _score_role_question(question: Question):
    dimension_count = len(set(question.agree_dimension_signals or {}) | set(question.disagree_dimension_signals or {}))
    if dimension_count == 0 and question.trait_positive_dimension:
        dimension_count = 1
    return (
        dimension_count,
        question.discrimination_score,
        -question.display_order,
        -question.id,
    )
