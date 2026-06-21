"""Adaptive question-selection engine (heuristic, info-gain, and bandit policies).

Holds the per-stage candidate scoring, policy selection, uncertainty estimation, and
the selection-event bookkeeping used by the assessment flow. Imports only leaf modules
(``role_inference``, ``mastery``, ``guidance``) so it never depends on the orchestration
layer.
"""

import logging
import math
from dataclasses import dataclass
from functools import lru_cache

from django.conf import settings
from django.db.models import Q, Sum
from django.utils import timezone

from roadmaps.models import Question, Role
from roadmaps.questionnaire import ROLE_PROFILE_WEIGHTS

from .exceptions import AssessmentFlowError
from .guidance import get_skill_target_role
from .mastery import score_skill_question
from .models import AssessmentSession, QuestionBanditStat, QuestionSelectionEvent
from .role_inference import (
    _ROLE_DIMENSION_IDF,
    DEFAULT_ROLE_PRIOR_WEIGHT,
    ROLE_DISCOVERY_CONFIDENCE_THRESHOLD,
    ROLE_DISCOVERY_CORE_QUESTION_TARGET,
    ROLE_DISCOVERY_MIN_MARGIN,
    ROLE_EVIDENCE_LOGISTIC_SCALE,
    ROLE_EVIDENCE_SCORE_SCALE,
    ROLE_SCORE_SOFTMAX_TEMPERATURE,
    SOFTMAX_OMEGA,
    _build_role_distribution,
    _build_role_evidence_snapshot,
    _compute_role_distribution,
    _get_selectable_role_candidates,
    _is_role_resolution_exhausted_with_viable_winner,
    _is_top_role_specialization_satisfied,
    _log_sigmoid,
    _normalize_entropy,
    _score_dimension_overlap,
    _score_role_question,
)


logger = logging.getLogger('assessments.services')


LOG_TOP_ROLE_COUNT = 3
LOG_TOP_QUESTION_COUNT = 3
SUPPORTED_POLICY_MODES = {
    QuestionSelectionEvent.PolicyMode.HEURISTIC,
    QuestionSelectionEvent.PolicyMode.CORE_SEQUENCE,
    QuestionSelectionEvent.PolicyMode.INFO_GAIN,
    QuestionSelectionEvent.PolicyMode.SHADOW_BANDIT,
    QuestionSelectionEvent.PolicyMode.LIVE_BANDIT,
}

@dataclass(frozen=True)
class QuestionSelectionDecision:
    stage: str
    policy_mode: str
    candidates: list[Question]
    chosen_question: Question
    heuristic_question: Question
    bandit_question: Question
    candidate_scores: list[dict[str, object]]
    selection_score: float | None
    pre_selection_uncertainty: float


@lru_cache(maxsize=4096)
def _precompute_question_role_signals(
    question: Question,
    active_role_slugs: tuple[str, ...],
) -> tuple[tuple[float, ...], dict[int, list[float]]]:
    overlap_diffs: list[float] = []
    for role_slug in active_role_slugs:
        profile = ROLE_PROFILE_WEIGHTS.get(role_slug, {})
        agree_overlap = _score_dimension_overlap(question.agree_dimension_signals or {}, profile, _ROLE_DIMENSION_IDF)
        disagree_overlap = _score_dimension_overlap(question.disagree_dimension_signals or {}, profile, _ROLE_DIMENSION_IDF)
        if not question.agree_dimension_signals and question.trait_positive_dimension:
            agree_overlap = _score_dimension_overlap({question.trait_positive_dimension: 1.0}, profile, _ROLE_DIMENSION_IDF)
        overlap_diffs.append(agree_overlap - disagree_overlap)

    deltas: dict[int, list[float]] = {}
    for v in [-2, -1, 1, 2]:
        answer_direction = 1.0 if v > 0 else -1.0
        answer_strength = min(1.0, abs(float(v)) / 2.0)
        v_deltas = []
        for x in overlap_diffs:
            role_signal = answer_direction * x
            d = ROLE_EVIDENCE_SCORE_SCALE * answer_strength * _log_sigmoid(ROLE_EVIDENCE_LOGISTIC_SCALE * role_signal)
            v_deltas.append(d)
        deltas[v] = v_deltas
    return tuple(overlap_diffs), deltas


def _get_unanswered_questions(session: AssessmentSession):
    answered_question_ids = session.answers.values_list('question_id', flat=True)
    return (
        Question.objects.filter(is_active=True)
        .exclude(id__in=answered_question_ids)
        .select_related('role', 'topic')
        .prefetch_related('options__topic_signals__topic', 'topic__prerequisites')
    )


def _get_policy_mode() -> str:
    configured_mode = getattr(settings, 'ASSESSMENT_BANDIT_POLICY_MODE', QuestionSelectionEvent.PolicyMode.SHADOW_BANDIT)
    if configured_mode not in SUPPORTED_POLICY_MODES:
        return QuestionSelectionEvent.PolicyMode.SHADOW_BANDIT
    return configured_mode


def _select_question_for_session(session: AssessmentSession, candidates: list[Question], *, stage: str) -> QuestionSelectionDecision:  # noqa: C901, PLR0912, PLR0915
    if not candidates:
        if stage == Question.Stage.ROLE:
            msg = 'No role questions are selectable for this session.'
        else:
            msg = 'No skill questions are selectable for this session.'
        raise AssessmentFlowError(msg)

    pre_selection_uncertainty = _calculate_stage_uncertainty(session, stage)
    heuristic_question = max(candidates, key=lambda question: _get_heuristic_score(session, question))
    candidate_scores: list[dict[str, object]] = []
    selection_score: float | None = None

    if stage == Question.Stage.ROLE:
        policy_mode = _get_policy_mode()

        if policy_mode == QuestionSelectionEvent.PolicyMode.INFO_GAIN:
            evidence_snapshot = _build_role_evidence_snapshot(session)
            active_role_slugs = list(Role.objects.filter(is_active=True).values_list('slug', flat=True))
            current_role_scores = {
                role_slug: evidence_snapshot.role_scores.get(role_slug, 0.0)
                for role_slug in active_role_slugs
            }
            current_distribution = _build_role_distribution(current_role_scores, active_role_slugs)

            num_roles = len(active_role_slugs)
            if num_roles <= 1:
                expected_entropies = {q.id: 0.0 for q in candidates}
            else:
                inv_log_num_roles = 1.0 / math.log(num_roles)
                current_scores_list = [current_role_scores[slug] for slug in active_role_slugs]
                current_dist_list = [current_distribution[slug] for slug in active_role_slugs]

                expected_entropies = {}

                for question in candidates:
                    overlap_diffs, deltas = _precompute_question_role_signals(question, tuple(active_role_slugs))

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
                        p_v = p_neg2 if v == -2 else (p_neg1 if v == -1 else (p_pos1 if v == 1 else p_pos2))  # noqa: PLR2004
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

                    expected_entropies[question.id] = expected_entropy

            def selection_key(q: Question) -> tuple:
                h_score = _get_heuristic_score(session, q)
                return (
                    expected_entropies[q.id],
                    -h_score[0],
                    -h_score[1],
                    q.display_order,
                    q.id
                )

            chosen_question = min(candidates, key=selection_key)
            bandit_question = chosen_question
            selection_score = float(pre_selection_uncertainty - expected_entropies[chosen_question.id])

            for question in candidates:
                q_expected_entropy = expected_entropies[question.id]
                q_info_gain = float(pre_selection_uncertainty - q_expected_entropy)
                candidate_scores.append(
                    {
                        'question_id': question.id,
                        'question_code': question.code,
                        'policy_score': q_info_gain,
                        'selection_score': q_info_gain,
                        'heuristic_score': list(_get_heuristic_score(session, question)),
                        'expected_entropy': q_expected_entropy,
                    }
                )
        else:
            chosen_question = candidates[0]
            policy_mode = QuestionSelectionEvent.PolicyMode.CORE_SEQUENCE
            bandit_question = chosen_question
            selection_score = float(ROLE_DISCOVERY_CORE_QUESTION_TARGET - chosen_question.display_order)
            candidate_scores.extend(
                {
                    'question_id': question.id,
                    'question_code': question.code,
                    'policy_score': 0.0,
                    'selection_score': float(ROLE_DISCOVERY_CORE_QUESTION_TARGET - question.display_order),
                    'heuristic_score': [0.0],
                }
                for question in candidates
            )
    else:
        total_stage_pulls = _get_total_stage_pulls(stage)
        bandit_question = _select_bandit_question(session, candidates, stage=stage, total_stage_pulls=total_stage_pulls)
        policy_mode = _get_policy_mode()
        chosen_question = bandit_question if policy_mode == QuestionSelectionEvent.PolicyMode.LIVE_BANDIT else heuristic_question
        for question in candidates:
            heuristic_score = _get_heuristic_score(session, question)
            question_ucb = float(_compute_ucb_score_for_question(question, stage=stage, total_stage_pulls=total_stage_pulls))
            if question.id == chosen_question.id:
                selection_score = question_ucb
            candidate_scores.append(
                {
                    'question_id': question.id,
                    'question_code': question.code,
                    'policy_score': question_ucb,
                    'selection_score': question_ucb,
                    'heuristic_score': list(heuristic_score),
                }
            )

    return QuestionSelectionDecision(
        stage=stage,
        policy_mode=policy_mode,
        candidates=candidates,
        chosen_question=chosen_question,
        heuristic_question=heuristic_question,
        bandit_question=bandit_question,
        candidate_scores=candidate_scores,
        selection_score=selection_score,
        pre_selection_uncertainty=pre_selection_uncertainty,
    )


def _format_top_roles(ranked_roles: list[dict[str, object]], *, limit: int = LOG_TOP_ROLE_COUNT) -> list[dict[str, object]]:
    return [
        {
            'slug': role['slug'],
            'score': round(float(role['fit_score']), 4),
            'share': round(float(role['fit_share']), 4),
        }
        for role in ranked_roles[:limit]
    ]


def _format_dimension_scores(snapshot: dict[str, object]) -> dict[str, float]:
    return {key: round(float(value), 2) for key, value in sorted(snapshot['dimension_scores'].items()) if float(value) > 0}


def _format_failed_resolution_gates(session: AssessmentSession, snapshot: dict[str, object]) -> list[str]:
    if _is_role_resolution_exhausted_with_viable_winner(session, snapshot=snapshot):
        return []
    common_gates = {
        'top_role_exists': snapshot['top_role_slug'] is not None,
        'answered_core_questions': int(snapshot['answered_core_questions']) >= ROLE_DISCOVERY_CORE_QUESTION_TARGET,
        'confidence_met': float(snapshot['confidence']) >= ROLE_DISCOVERY_CONFIDENCE_THRESHOLD,
        'margin_met': float(snapshot['margin_share']) >= ROLE_DISCOVERY_MIN_MARGIN,
        'specialization_met': _is_top_role_specialization_satisfied(snapshot),
    }
    return [gate_name.removesuffix('_met') for gate_name, passed in common_gates.items() if not passed]


def _format_top_question_scores(candidate_scores: list[dict[str, object]], *, limit: int = LOG_TOP_QUESTION_COUNT) -> list[dict[str, object]]:
    sorted_scores = sorted(
        candidate_scores,
        key=lambda candidate: (
            -float(candidate.get('selection_score') or 0.0),
            candidate.get('question_code') or '',
        ),
    )
    formatted = []
    for candidate in sorted_scores[:limit]:
        formatted_candidate = {
            'code': candidate['question_code'],
            'selection': round(float(candidate.get('selection_score') or 0.0), 4),
        }
        if 'expected_entropy' in candidate:
            formatted_candidate['expected_entropy'] = round(float(candidate['expected_entropy']), 4)
        formatted.append(formatted_candidate)
    return formatted


def _get_total_stage_pulls(stage: str) -> int:
    return QuestionBanditStat.objects.filter(stage=stage).aggregate(total=Sum('pulls'))['total'] or 0


def _select_bandit_question(session: AssessmentSession, candidates: list[Question], *, stage: str, total_stage_pulls: int) -> Question:
    candidate_ids = [question.id for question in candidates]
    stats_by_question_id = {stat.question_id: stat for stat in QuestionBanditStat.objects.filter(stage=stage, question_id__in=candidate_ids)}
    unseen_candidates = [
        question for question in candidates if stats_by_question_id.get(question.id) is None or stats_by_question_id[question.id].pulls == 0
    ]
    if unseen_candidates:
        return max(unseen_candidates, key=lambda question: _get_heuristic_score(session, question))

    return max(
        candidates,
        key=lambda question: (
            _compute_ucb_score(stats_by_question_id[question.id], total_stage_pulls),
            _get_heuristic_score(session, question),
        ),
    )


def _compute_ucb_score_for_question(question: Question, *, stage: str, total_stage_pulls: int) -> float:
    stat = QuestionBanditStat.objects.filter(stage=stage, question=question).first()
    if stat is None:
        return 1.0
    return _compute_ucb_score(stat, total_stage_pulls)


def _compute_ucb_score(stat: QuestionBanditStat, total_stage_pulls: int) -> float:
    if stat.pulls == 0:
        return 1.0
    safe_total_stage_pulls = max(total_stage_pulls, 1)
    return stat.mean_reward + math.sqrt(2.0 * math.log(safe_total_stage_pulls) / stat.pulls)


def _ensure_selection_event(session: AssessmentSession, decision: QuestionSelectionDecision) -> QuestionSelectionEvent:
    existing_event = _get_pending_selection_event(session, decision.chosen_question)
    if existing_event is not None:
        return existing_event

    event = QuestionSelectionEvent.objects.create(
        session=session,
        stage=decision.stage,
        policy_mode=decision.policy_mode,
        chosen_question=decision.chosen_question,
        heuristic_question=decision.heuristic_question,
        shadow_bandit_question=decision.bandit_question if decision.policy_mode != QuestionSelectionEvent.PolicyMode.HEURISTIC else None,
        candidate_question_ids=[question.id for question in decision.candidates],
        candidate_question_codes=[question.code for question in decision.candidates],
        candidate_scores=decision.candidate_scores,
        selection_score=decision.selection_score,
        pre_selection_uncertainty=decision.pre_selection_uncertainty,
    )
    logger.info(
        ('assessment.question_selected session_id=%s stage=%s chosen=%s candidates=%s score=%s uncertainty=%.4f top_candidates=%s'),
        session.id,
        decision.stage,
        decision.chosen_question.code,
        len(decision.candidates),
        f'{decision.selection_score:.4f}' if decision.selection_score is not None else 'n/a',
        decision.pre_selection_uncertainty,
        _format_top_question_scores(decision.candidate_scores),
    )
    return event


def _get_pending_selection_event(session: AssessmentSession, question: Question):
    return (
        QuestionSelectionEvent.objects.filter(
            session=session,
            chosen_question=question,
            answered_at__isnull=True,
        )
        .order_by('-selected_at')
        .first()
    )


def _finalize_selection_event(selection_event: QuestionSelectionEvent, *, session: AssessmentSession, question: Question) -> None:
    post_answer_uncertainty = _calculate_stage_uncertainty(session, question.stage)
    reward = max(0.0, min(1.0, selection_event.pre_selection_uncertainty - post_answer_uncertainty))
    answered_at = timezone.now()
    selection_event.post_answer_uncertainty = post_answer_uncertainty
    selection_event.reward = reward
    selection_event.answered_at = answered_at
    selection_event.save(update_fields=['post_answer_uncertainty', 'reward', 'answered_at'])

    if selection_event.stage == Question.Stage.ROLE:
        logger.info(
            ('assessment.role_selection_evaluated session_id=%s stage=%s question_code=%s reward=%.4f post_answer_uncertainty=%.4f'),
            session.id,
            selection_event.stage,
            question.code,
            reward,
            post_answer_uncertainty,
        )
        return

    stat, _created = QuestionBanditStat.objects.get_or_create(
        question=selection_event.chosen_question,
        stage=selection_event.stage,
        defaults={
            'pulls': 0,
            'cumulative_reward': 0.0,
            'mean_reward': 0.0,
        },
    )
    stat.pulls += 1
    stat.cumulative_reward += reward
    stat.mean_reward = stat.cumulative_reward / stat.pulls
    stat.last_selected_at = answered_at
    stat.save(update_fields=['pulls', 'cumulative_reward', 'mean_reward', 'last_selected_at'])
    logger.info(
        (
            'assessment.bandit_reward_recorded session_id=%s stage=%s question_code=%s reward=%.4f '
            'post_answer_uncertainty=%.4f pulls=%s mean_reward=%.4f'
        ),
        session.id,
        selection_event.stage,
        question.code,
        reward,
        post_answer_uncertainty,
        stat.pulls,
        stat.mean_reward,
    )


def _calculate_stage_uncertainty(session: AssessmentSession, stage: str) -> float:
    if stage == Question.Stage.ROLE:
        return _calculate_role_uncertainty(session)
    return _calculate_skill_uncertainty(session)


def _calculate_role_uncertainty(session: AssessmentSession) -> float:
    active_role_slugs = list(Role.objects.filter(is_active=True).values_list('slug', flat=True))
    if len(active_role_slugs) <= 1:
        return 0.0
    role_distribution = _compute_role_distribution(session)
    return _normalize_entropy(role_distribution, active_role_slugs)


def _calculate_skill_uncertainty(session: AssessmentSession) -> float:
    target_role = get_skill_target_role(session)
    if target_role is None:
        return 1.0
    topics = list(target_role.topics.filter(is_active=True))
    if not topics:
        return 0.0
    mastery_by_topic_id = {mastery.topic_id: mastery for mastery in session.mastery_scores.all()}
    return sum(1.0 - mastery_by_topic_id.get(topic.id, _EmptyMastery()).confidence_score for topic in topics) / len(topics)


class _EmptyMastery:
    confidence_score = 0.0


def _get_candidates_for_stage(session: AssessmentSession, stage: str) -> list[Question]:
    base_queryset = _get_unanswered_questions(session)
    if stage == Question.Stage.ROLE:
        return _get_selectable_role_candidates(session, list(base_queryset.filter(stage=Question.Stage.ROLE)))

    target_role = get_skill_target_role(session)
    if target_role is None:
        return []
    return list(
        base_queryset.filter(stage=Question.Stage.SKILL)
        .filter(Q(role__isnull=True) | Q(role=target_role))
        .filter(Q(topic__isnull=True) | Q(topic__role=target_role))
    )


def _get_heuristic_score(session: AssessmentSession, question: Question):
    if question.stage == Question.Stage.ROLE:
        return _score_role_question(question)
    return score_skill_question(session, question)
