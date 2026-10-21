import math
import random
import re
import statistics
from collections import Counter
from concurrent.futures import ProcessPoolExecutor

from assessments.services import scoring_service
from roadmaps.questionnaire import ROLE_DIMENSIONS, ROLE_PROFILE_WEIGHTS

from .engine import CatalogContext, _SampleState


ANSWERS = (-2, -1, 0, 1, 2)

PARAMS = {
    'p_pure': 0.30,
    'p_blend': 0.50,
    'p_undecided': 0.20,
    'blend_dominant': (0.55, 0.85),
    'blend_neighbor_p': 0.7,
    'neighbor_k': 8,
    'idio_sigma': {'pure': 0.25, 'blend': 0.35, 'undecided': 0.6},
    'self_knowledge': {'pure': (0.8, 1.3), 'blend': (0.7, 1.2), 'undecided': (0.3, 0.7)},
    'item_noise_sigma': 0.6,
    'thresholds': (-1.2, -0.35, 0.35, 1.2),
    'p_ars': 0.25,
    'ars_shift': (0.2, 0.5),
    'p_mrs': 0.30,
    'mrs_widen': (0.3, 0.7),
    'p_ers': 0.10,
    'ers_pull': (0.3, 0.6),
    'p_careless': 0.08,
    'careless_onset': (0, 25),
    'careless_straightline_p': 0.4,
    'desirability_shift': 0.4,
    'experience_levels': ((0.6, 0.0), (0.3, 1.0), (0.1, 2.0)),
    'familiarity_bias': 3.0,
    'unfamiliar_mid_p': 0.6,
    'fatigue_start': 20,
    'fatigue_noise_per_item': 0.03,
    'fatigue_mid_per_item': 0.01,
}

SCENARIOS = {
    'base': {},
    'noisy': {'item_noise_sigma': 0.75, 'p_careless': 0.12},
    'clean': {'item_noise_sigma': 0.45, 'p_careless': 0.04},
    'undecided': {'p_undecided': 0.35, 'p_blend': 0.35},
    'midpoint': {'p_mrs': 0.5},
    'acquiescent': {'p_ars': 0.5, 'ars_shift': (0.3, 0.7)},
    'desirability': {'desirability_shift': 0.8},
    'jargon': {'familiarity_bias': 2.0},
}

DESIRABLE_CODES = frozenset({
    'role-rd-explaining', 'role-rd-leading', 'role-rd-process', 'role-rd-requirements', 'role-rd-coordination', 'role-rd-evidence',
})
JARGON_TH = ('เซิร์ฟเวอร์', 'ฐานข้อมูล', 'โมเดล', 'เครือข่าย', 'บล็อกเชน', 'ช่องโหว่', 'อัตโนมัติ', 'โค้ด', 'เบราว์เซอร์', 'ทรัพยากร')

ROLES = sorted(ROLE_PROFILE_WEIGHTS)
MEAN_PROFILE_WEIGHT = statistics.mean(value for profile in ROLE_PROFILE_WEIGHTS.values() for value in profile.values())


def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
    norm_a = math.sqrt(sum(value * value for value in a.values())) or 1.0
    norm_b = math.sqrt(sum(value * value for value in b.values())) or 1.0
    return sum(a.get(key, 0.0) * b.get(key, 0.0) for key in a) / (norm_a * norm_b)


NEIGHBORS = {
    role: sorted((other for other in ROLES if other != role), key=lambda other: -_cosine(ROLE_PROFILE_WEIGHTS[role], ROLE_PROFILE_WEIGHTS[other]))
    for role in ROLES
}


def prepare_items(questions: list[dict]) -> dict[object, dict]:
    raw_difficulty = {}
    items = {}
    for question in questions:
        text = question.get('th') or question.get('prompt') or ''
        english_words = len(re.findall(r'[A-Za-z]{3,}', text)) if question.get('th') else 8
        jargon = sum(1 for term in JARGON_TH if term in text)
        raw_difficulty[question['id']] = 0.35 * english_words + 0.5 * jargon + len(text) / 80.0
        scores = [_latent_score(question, profile) for profile in ROLE_PROFILE_WEIGHTS.values()]
        items[question['id']] = {
            'mu': statistics.mean(scores),
            'sd': statistics.pstdev(scores) or 1.0,
            'desirable': question.get('code') in DESIRABLE_CODES,
        }
    low, high = min(raw_difficulty.values(), default=0.0), max(raw_difficulty.values(), default=0.0)
    for question_id, value in raw_difficulty.items():
        items[question_id]['difficulty'] = (value - low) / ((high - low) or 1.0) * 4.0
    return items


def _latent_score(question: dict, latent: dict[str, float]) -> float:
    return scoring_service.score_dimension_overlap(question.get('agree_dimension_signals') or {}, latent) - scoring_service.score_dimension_overlap(
        question.get('disagree_dimension_signals') or {}, latent,
    )


def _preference_mix(kind: str, rng: random.Random, params: dict) -> dict[str, float]:
    first = rng.choice(ROLES)
    if kind == 'pure':
        return {first: 1.0}
    if kind == 'blend':
        pool = NEIGHBORS[first][:params['neighbor_k']] if rng.random() < params['blend_neighbor_p'] else NEIGHBORS[first]
        second = rng.choice(pool)
        weight = rng.uniform(*params['blend_dominant'])
        return {first: weight, second: 1 - weight}
    picks = rng.sample(ROLES, 3)
    weights = [rng.random() + 0.5 for _ in picks]
    return {role: weight / sum(weights) for role, weight in zip(picks, weights, strict=True)}


def _experience(rng: random.Random, params: dict) -> float:
    roll, cumulative = rng.random(), 0.0
    for share, level in params['experience_levels']:
        cumulative += share
        if roll <= cumulative:
            return level
    return 0.0


def _response_style(rng: random.Random, params: dict) -> tuple[list[float], float, int | None, list[str]]:
    thresholds = list(params['thresholds'])
    styles = []
    acquiescence = rng.uniform(*params['ars_shift']) if rng.random() < params['p_ars'] else 0.0
    if acquiescence:
        styles.append('acquiescent')
    if rng.random() < params['p_mrs']:
        widen = rng.uniform(*params['mrs_widen'])
        thresholds = [thresholds[0] - widen / 2, thresholds[1] - widen, thresholds[2] + widen, thresholds[3] + widen / 2]
        styles.append('midpoint')
    if rng.random() < params['p_ers']:
        pull = rng.uniform(*params['ers_pull'])
        thresholds = [thresholds[0] + pull, thresholds[1], thresholds[2], thresholds[3] - pull]
        styles.append('extreme')
    careless_from = rng.randint(*params['careless_onset']) if rng.random() < params['p_careless'] else None
    if careless_from is not None:
        styles.append('careless')
    return thresholds, acquiescence, careless_from, styles


def make_persona(rng: random.Random, params: dict) -> dict:
    roll = rng.random()
    kind = 'pure' if roll < params['p_pure'] else 'blend' if roll < params['p_pure'] + params['p_blend'] else 'undecided'
    mix = _preference_mix(kind, rng, params)
    latent = dict.fromkeys(ROLE_DIMENSIONS, 0.0)
    for role, weight in mix.items():
        for dimension, value in ROLE_PROFILE_WEIGHTS[role].items():
            latent[dimension] += weight * value
    sigma = params['idio_sigma'][kind]
    for dimension in ROLE_DIMENSIONS:
        latent[dimension] = max(0.0, latent[dimension] + rng.gauss(0, sigma * MEAN_PROFILE_WEIGHT))
    by_similarity = sorted(ROLES, key=lambda role: -_cosine(latent, ROLE_PROFILE_WEIGHTS[role]))
    experience = _experience(rng, params)
    thresholds, acquiescence, careless_from, styles = _response_style(rng, params)
    return {
        'kind': kind,
        'latent': latent,
        'truth': by_similarity[0],
        'truth_top2': set(by_similarity[:2]),
        'self_knowledge': rng.uniform(*params['self_knowledge'][kind]),
        'experience': experience,
        'thresholds': thresholds,
        'acquiescence': acquiescence,
        'careless_from': careless_from,
        'straight_line': rng.choice(ANSWERS) if rng.random() < params['careless_straightline_p'] else None,
        'styles': styles,
    }


def answer(persona: dict, question: dict, item: dict, position: int, rng: random.Random, params: dict) -> int:  # noqa: PLR0913
    if persona['careless_from'] is not None and position >= persona['careless_from']:
        return persona['straight_line'] if persona['straight_line'] is not None else rng.choice(ANSWERS)
    p_unfamiliar = 1 / (1 + math.exp(-(item['difficulty'] - persona['experience'] - params['familiarity_bias'])))
    if rng.random() < p_unfamiliar:
        return 0 if rng.random() < params['unfamiliar_mid_p'] else rng.choice((-1, 0, 1))
    z = (_latent_score(question, persona['latent']) - item['mu']) / item['sd']
    over = max(0, position - params['fatigue_start'])
    y = persona['self_knowledge'] * z + persona['acquiescence'] + (params['desirability_shift'] if item['desirable'] else 0.0)
    y += rng.gauss(0, params['item_noise_sigma'] + params['fatigue_noise_per_item'] * over)
    if over and rng.random() < params['fatigue_mid_per_item'] * over:
        return 0
    t = persona['thresholds']
    return -2 if y < t[0] else -1 if y < t[1] else 0 if y < t[2] else 1 if y < t[3] else 2


def run_session(persona: dict, catalog: CatalogContext, items: dict, rng: random.Random, params: dict) -> dict:
    state = _SampleState(
        active_role_slugs=list(catalog.active_role_slugs),
        role_names=catalog.role_names,
        available_questions=catalog.available_questions,
    )
    snapshot = state.inference_snapshot()
    unanswered = list(catalog.questions)
    while (question := scoring_service.select_next_role_question(unanswered, snapshot)) is not None:
        state.apply_answer(question, answer(persona, question, items[question['id']], state.answered_total, rng, params))
        unanswered = [candidate for candidate in unanswered if candidate['id'] != question['id']]
        snapshot = state.inference_snapshot()
    status = scoring_service.get_role_resolution_status(
        is_complete=bool(snapshot['is_complete']),
        best_fit_role_slug=snapshot['top_role_slug'],
        score_margin=float(snapshot['score_margin']),
    )
    return {
        'candidates': [role['slug'] for role in snapshot['role_candidates']],
        'answered': state.answered_total,
        'resolved': status == 'resolved',
    }


def _run_scenario(args: tuple) -> tuple[str, dict]:
    catalog, name, samples, seed = args
    items = prepare_items(catalog.questions)
    params = dict(PARAMS)
    params.update(SCENARIOS[name])
    rng = random.Random(seed)
    top1 = top3 = resolved = wrong_confident = 0
    answered, retest = [], []
    kinds: Counter = Counter()
    kind_hits: Counter = Counter()
    for _ in range(samples):
        persona = make_persona(rng, params)
        first = run_session(persona, catalog, items, rng, params)
        second = run_session(persona, catalog, items, rng, params)
        shown = first['candidates']
        top1 += bool(shown) and shown[0] == persona['truth']
        hit = persona['truth'] in shown
        top3 += hit
        kinds[persona['kind']] += 1
        kind_hits[persona['kind']] += hit
        answered.append(first['answered'])
        if first['resolved']:
            resolved += 1
            wrong_confident += shown[0] not in persona['truth_top2']
        union = set(shown) | set(second['candidates'])
        retest.append(len(set(shown) & set(second['candidates'])) / len(union) if union else 1.0)
    answered.sort()
    return name, {
        'top1_accuracy': round(top1 / samples, 4),
        'top3_accuracy': round(top3 / samples, 4),
        'resolved_rate': round(resolved / samples, 4),
        'wrong_confident_rate': round(wrong_confident / samples, 4),
        'avg_answered_questions': round(statistics.mean(answered), 2),
        'p90_answered_questions': answered[int(0.9 * (samples - 1))],
        'retest_candidate_overlap': round(statistics.mean(retest), 4),
        'top3_by_kind': {kind: round(kind_hits[kind] / count, 4) for kind, count in sorted(kinds.items())},
    }


def run_realistic_suite(catalog: CatalogContext, *, samples: int, seed: int, scenarios: list[str] | None = None) -> dict[str, object]:
    names = scenarios or list(SCENARIOS)
    jobs = [(catalog, name, samples, seed + offset) for offset, name in enumerate(names)]
    with ProcessPoolExecutor() as executor:
        rows = dict(executor.map(_run_scenario, jobs))
    report: dict[str, object] = {'samples_per_scenario': samples, 'seed': seed, 'scenarios': {name: rows[name] for name in names}}
    values = list(report['scenarios'].values())
    report['summary'] = {
        'top3_accuracy': round(statistics.mean(row['top3_accuracy'] for row in values), 4),
        'top3_accuracy_worst': min(row['top3_accuracy'] for row in values),
        'top1_accuracy': round(statistics.mean(row['top1_accuracy'] for row in values), 4),
        'wrong_confident_rate_worst': max(row['wrong_confident_rate'] for row in values),
        'avg_answered_questions': round(statistics.mean(row['avg_answered_questions'] for row in values), 2),
        'retest_candidate_overlap': round(statistics.mean(row['retest_candidate_overlap'] for row in values), 4),
    }
    return report
