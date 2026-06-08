# ruff: noqa: E402, C901, PLR0912, PLR0913, PLR0915, S311, F541, PERF401, PLR2004
import argparse
import concurrent.futures
import os
import random
import sys
import time
from collections import Counter


# Set up Django settings before importing models
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.runtime')
import django


django.setup()

import simulate_multiprocess_inmemory as sim


# SWEBOK Likert values
LIKERT_VALUES = (-2, -1, 0, 1, 2)


def run_trial_task(
    trial_id: int,
    params: dict,
    samples: int,
    prefix_answers: list[int],
    likert_weights: dict[int, float],
    preferred_role_slug: str | None,
    active_role_slugs: list[str],
    serialized_questions: list[dict],
    role_profile_weights: dict,
    role_dimension_idf: dict,
    pre_generated_choices_list: list[list[int]],
) -> dict:
    # Override global variables in the imported simulation module for this worker process
    sim.ROLE_SCORE_SOFTMAX_TEMPERATURE = params['ROLE_SCORE_SOFTMAX_TEMPERATURE']
    sim.ROLE_DISCOVERY_CONFIDENCE_THRESHOLD = params['ROLE_DISCOVERY_CONFIDENCE_THRESHOLD']
    sim.ROLE_DISCOVERY_MIN_MARGIN = params['ROLE_DISCOVERY_MIN_MARGIN']
    sim.SOFTMAX_OMEGA = params['SOFTMAX_OMEGA']
    sim.ROLE_EVIDENCE_SCORE_SCALE = params['ROLE_EVIDENCE_SCORE_SCALE']
    sim.ROLE_EVIDENCE_LOGISTIC_SCALE = params['ROLE_EVIDENCE_LOGISTIC_SCALE']
    sim.ROLE_SPECIALIZATION_EVIDENCE_THRESHOLD = params['ROLE_SPECIALIZATION_EVIDENCE_THRESHOLD']
    sim.DEFAULT_ROLE_PRIOR_WEIGHT = params['DEFAULT_ROLE_PRIOR_WEIGHT']

    # Run the samples sequentially in this worker process
    results = []
    for idx in range(samples):
        res = sim.run_single_inmemory_sample(
            idx,
            prefix_answers,
            likert_weights,
            preferred_role_slug,
            active_role_slugs,
            serialized_questions,
            role_profile_weights,
            role_dimension_idf,
            pre_generated_choices_list[idx]
        )
        results.append(res)

    # Aggregate metrics
    resolution_status_counts = Counter()
    confidence_total = 0.0
    answered_role_question_total = 0
    for sample in results:
        resolution_status_counts[sample['resolution_status']] += 1
        confidence_total += sample['confidence']
        answered_role_question_total += sample['answered_role_questions']

    resolved_rate = resolution_status_counts['resolved'] / samples
    ambiguous_rate = resolution_status_counts['ambiguous'] / samples
    avg_questions = answered_role_question_total / samples
    avg_confidence = confidence_total / samples

    # Fitness score: prioritize resolved rate, and secondarily average confidence
    fitness_score = resolved_rate * 0.7 + avg_confidence * 0.3

    return {
        'trial_id': trial_id,
        'params': params,
        'resolved_rate': resolved_rate,
        'ambiguous_rate': ambiguous_rate,
        'avg_questions': avg_questions,
        'avg_confidence': avg_confidence,
        'fitness_score': fitness_score,
    }


def main():
    parser = argparse.ArgumentParser(description='Hyperparameter Tuning for Monte Carlo Role Estimator.')
    parser.add_argument('--mode', choices=('grid', 'random', 'genetic'), default='grid', help='Tuning mode.')
    parser.add_argument('--samples', type=int, default=100, help='Number of Monte Carlo samples per trial.')
    parser.add_argument('--trials', type=int, default=30, help='Number of random search trials (only if mode=random).')
    parser.add_argument('--pop-size', type=int, default=20, help='Population size for genetic search.')
    parser.add_argument('--generations', type=int, default=5, help='Number of generations for genetic search.')
    parser.add_argument('--mutation-rate', type=float, default=0.2, help='Mutation rate for genetic search.')
    parser.add_argument('--random-seed', type=int, default=12345, help='Random seed for reproducibility.')
    parser.add_argument('--likert-weights', default='1,1,1,1,1', help='Weights for LIKERT_VALUES.')
    parser.add_argument('--answers', default='', help='Prefix answers.')

    args = parser.parse_args()

    # Parse prefix answers
    prefix_answers = []
    if args.answers.strip():
        for val in args.answers.split(','):
            val_int = int(val.strip())
            if val_int not in LIKERT_VALUES:
                sys.exit(f"Invalid answer: {val_int}. Must be in {LIKERT_VALUES}")
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

    # Fetch data from Django models
    active_role_slugs = list(sim.Role.objects.filter(is_active=True).order_by('slug').values_list('slug', flat=True))

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
        for q in sim.Question.objects.filter(stage=sim.Question.Stage.ROLE, is_active=True)
    ]

    # Pre-generate Common Random Choices (CRN) to control variance between trials
    rng = random.Random(args.random_seed)
    num_random_needed = sim.ROLE_DISCOVERY_CORE_QUESTION_TARGET - len(prefix_answers)
    pre_generated_choices_list = []
    for _ in range(args.samples):
        choices = [
            rng.choices(
                population=list(LIKERT_VALUES),
                weights=[likert_weights[v] for v in LIKERT_VALUES],
                k=1
            )[0]
            for _ in range(num_random_needed)
        ]
        pre_generated_choices_list.append(choices)

    results = []

    if args.mode == 'genetic':
        # Genetic algorithm hyperparameter tuning
        bounds = {
            'ROLE_SCORE_SOFTMAX_TEMPERATURE': (0.5, 2.5),
            'ROLE_DISCOVERY_CONFIDENCE_THRESHOLD': (0.10, 0.50),
            'ROLE_DISCOVERY_MIN_MARGIN': (0.30, 0.95),
            'SOFTMAX_OMEGA': (0.10, 0.60),
            'ROLE_EVIDENCE_SCORE_SCALE': (1.0, 6.0),
            'ROLE_EVIDENCE_LOGISTIC_SCALE': (0.2, 2.0),
            'ROLE_SPECIALIZATION_EVIDENCE_THRESHOLD': (0.1, 0.9),
            'DEFAULT_ROLE_PRIOR_WEIGHT': (0.00001, 0.05),
        }

        pop_rng = random.Random(args.random_seed + 2)
        population = []
        for _ in range(args.pop_size):
            ind = {}
            for param, (low, high) in bounds.items():
                if param == 'DEFAULT_ROLE_PRIOR_WEIGHT':
                    ind[param] = round(pop_rng.uniform(low, high), 5)
                else:
                    ind[param] = round(pop_rng.uniform(low, high), 3)
            population.append(ind)

        sys.stdout.write(f"Starting Genetic Hyperparameter Tuning...\n")
        sys.stdout.write(f"Population size: {args.pop_size} | Generations: {args.generations} | Samples per Trial: {args.samples}\n\n")

        start_time = time.perf_counter()
        best_overall = None

        with concurrent.futures.ProcessPoolExecutor() as executor:
            for gen in range(args.generations):
                sys.stdout.write(f"Evaluating Generation {gen + 1}/{args.generations}...\n")
                futures = [
                    executor.submit(
                        run_trial_task,
                        idx + 1 + gen * args.pop_size,
                        ind,
                        args.samples,
                        prefix_answers,
                        likert_weights,
                        None,
                        active_role_slugs,
                        serialized_questions,
                        sim.ROLE_PROFILE_WEIGHTS,
                        sim.ROLE_DIMENSION_IDF,
                        pre_generated_choices_list
                    )
                    for idx, ind in enumerate(population)
                ]
                gen_results = [f.result() for f in futures]

                # Sort by fitness score descending
                gen_results.sort(key=lambda r: r['fitness_score'], reverse=True)

                best_gen = gen_results[0]
                sys.stdout.write(
                    f"Gen {gen + 1} Best Trial {best_gen['trial_id']}: Resolved Rate: {best_gen['resolved_rate']:.4f}, "
                    f"Avg Conf: {best_gen['avg_confidence']:.4f}, Fitness: {best_gen['fitness_score']:.4f}\n"
                )

                # Keep track of all evaluated trials for the final summary print
                results.extend(gen_results)

                if best_overall is None or best_gen['fitness_score'] > best_overall['fitness_score']:
                    best_overall = best_gen

                if gen < args.generations - 1:
                    # Elitism: top 20% (min 1)
                    num_elites = max(1, int(args.pop_size * 0.2))
                    next_pop = [r['params'] for r in gen_results[:num_elites]]

                    # Selection pool: top 50%
                    parent_pool = [r['params'] for r in gen_results[:max(2, int(args.pop_size * 0.5))]]
                    while len(next_pop) < args.pop_size:
                        p1 = pop_rng.choice(parent_pool)
                        p2 = pop_rng.choice(parent_pool)

                        # Uniform Crossover
                        child = {}
                        for param in bounds:
                            child[param] = p1[param] if pop_rng.random() < 0.5 else p2[param]

                        # Mutation
                        for param, (low, high) in bounds.items():
                            if pop_rng.random() < args.mutation_rate:
                                span = high - low
                                perturb = pop_rng.uniform(-0.1 * span, 0.1 * span)
                                val = child[param] + perturb
                                val = max(low, min(high, val))
                                if param == 'DEFAULT_ROLE_PRIOR_WEIGHT':
                                    child[param] = round(val, 5)
                                else:
                                    child[param] = round(val, 3)
                        next_pop.append(child)
                    population = next_pop

        end_time = time.perf_counter()
        elapsed = end_time - start_time

    else:
        # Generate trials for grid or random modes
        trials_params = []
        if args.mode == 'grid':
            # Grid definition
            temps = [1.0, 1.15, 1.3]
            thresholds = [0.24, 0.28, 0.32]
            margins = [0.65, 0.75, 0.85]
            omegas = [0.30, 0.35, 0.40]

            for t in temps:
                for th in thresholds:
                    for m in margins:
                        for o in omegas:
                            trials_params.append({
                                'ROLE_SCORE_SOFTMAX_TEMPERATURE': t,
                                'ROLE_DISCOVERY_CONFIDENCE_THRESHOLD': th,
                                'ROLE_DISCOVERY_MIN_MARGIN': m,
                                'SOFTMAX_OMEGA': o,
                                'ROLE_EVIDENCE_SCORE_SCALE': 3.0,
                                'ROLE_EVIDENCE_LOGISTIC_SCALE': 0.7,
                                'ROLE_SPECIALIZATION_EVIDENCE_THRESHOLD': 0.5,
                                'DEFAULT_ROLE_PRIOR_WEIGHT': 0.001,
                            })
        else:
            # Random search definition - covers 8 hyperparameters
            trial_rng = random.Random(args.random_seed + 1)
            for _ in range(args.trials):
                trials_params.append({
                    'ROLE_SCORE_SOFTMAX_TEMPERATURE': round(trial_rng.uniform(0.9, 1.6), 3),
                    'ROLE_DISCOVERY_CONFIDENCE_THRESHOLD': round(trial_rng.uniform(0.20, 0.40), 3),
                    'ROLE_DISCOVERY_MIN_MARGIN': round(trial_rng.uniform(0.50, 0.90), 3),
                    'SOFTMAX_OMEGA': round(trial_rng.uniform(0.20, 0.50), 3),
                    'ROLE_EVIDENCE_SCORE_SCALE': round(trial_rng.uniform(1.5, 4.5), 3),
                    'ROLE_EVIDENCE_LOGISTIC_SCALE': round(trial_rng.uniform(0.4, 1.2), 3),
                    'ROLE_SPECIALIZATION_EVIDENCE_THRESHOLD': round(trial_rng.uniform(0.3, 0.8), 3),
                    'DEFAULT_ROLE_PRIOR_WEIGHT': round(trial_rng.uniform(0.0001, 0.01), 5),
                })

        sys.stdout.write(f"Starting Hyperparameter Tuning Sweep...\n")
        sys.stdout.write(f"Mode: {args.mode} | Samples per Trial: {args.samples} | Total Trials: {len(trials_params)}\n\n")

        start_time = time.perf_counter()

        # Execute trials in parallel
        with concurrent.futures.ProcessPoolExecutor() as executor:
            futures = [
                executor.submit(
                    run_trial_task,
                    idx + 1,
                    params,
                    args.samples,
                    prefix_answers,
                    likert_weights,
                    None,
                    active_role_slugs,
                    serialized_questions,
                    sim.ROLE_PROFILE_WEIGHTS,
                    sim.ROLE_DIMENSION_IDF,
                    pre_generated_choices_list
                )
                for idx, params in enumerate(trials_params)
            ]
            results = [f.result() for f in futures]

        end_time = time.perf_counter()
        elapsed = end_time - start_time

    # Sort results by fitness score descending
    results.sort(key=lambda r: r['fitness_score'], reverse=True)

    # Print Table Header
    sys.stdout.write(
        f"{'Trial':5} | {'Temp':6} | {'ConfTh':6} | {'Margin':6} | {'Omega':6} | "
        f"{'Resolved':8} | {'AvgConf':7} | {'Fitness':7}\n"
    )
    sys.stdout.write("-" * 80 + "\n")

    # Print top 15 results
    for r in results[:15]:
        p = r['params']
        sys.stdout.write(
            f"{r['trial_id']:5d} | "
            f"{p['ROLE_SCORE_SOFTMAX_TEMPERATURE']:6.3f} | "
            f"{p['ROLE_DISCOVERY_CONFIDENCE_THRESHOLD']:6.3f} | "
            f"{p['ROLE_DISCOVERY_MIN_MARGIN']:6.3f} | "
            f"{p['SOFTMAX_OMEGA']:6.3f} | "
            f"{r['resolved_rate']:8.4f} | "
            f"{r['avg_confidence']:7.4f} | "
            f"{r['fitness_score']:7.4f}\n"
        )

    sys.stdout.write("\n" + "=" * 80 + "\n")
    sys.stdout.write(f"Tuning Sweep Completed in {elapsed:.2f} seconds.\n")
    if results:
        best = results[0]
        bp = best['params']
        sys.stdout.write(f"\n* BEST CONFIGURATION FOUND (Trial {best['trial_id']}) *\n")
        sys.stdout.write(f"  ROLE_SCORE_SOFTMAX_TEMPERATURE      = {bp['ROLE_SCORE_SOFTMAX_TEMPERATURE']:.3f}\n")
        sys.stdout.write(f"  ROLE_DISCOVERY_CONFIDENCE_THRESHOLD = {bp['ROLE_DISCOVERY_CONFIDENCE_THRESHOLD']:.3f}\n")
        sys.stdout.write(f"  ROLE_DISCOVERY_MIN_MARGIN           = {bp['ROLE_DISCOVERY_MIN_MARGIN']:.3f}\n")
        sys.stdout.write(f"  SOFTMAX_OMEGA                       = {bp['SOFTMAX_OMEGA']:.3f}\n")
        sys.stdout.write(f"  ROLE_EVIDENCE_SCORE_SCALE           = {bp['ROLE_EVIDENCE_SCORE_SCALE']:.3f}\n")
        sys.stdout.write(f"  ROLE_EVIDENCE_LOGISTIC_SCALE        = {bp['ROLE_EVIDENCE_LOGISTIC_SCALE']:.3f}\n")
        sys.stdout.write(f"  ROLE_SPECIALIZATION_EVIDENCE_THRES  = {bp['ROLE_SPECIALIZATION_EVIDENCE_THRESHOLD']:.3f}\n")
        sys.stdout.write(f"  DEFAULT_ROLE_PRIOR_WEIGHT           = {bp['DEFAULT_ROLE_PRIOR_WEIGHT']:.5f}\n")
        sys.stdout.write(f"  --------------------------------------------------\n")
        sys.stdout.write(f"  Resolved Rate: {best['resolved_rate']:.4f}\n")
        sys.stdout.write(f"  Avg Confidence: {best['avg_confidence']:.4f}\n")
        sys.stdout.write(f"  Fitness Score: {best['fitness_score']:.4f}\n")


if __name__ == '__main__':
    main()
