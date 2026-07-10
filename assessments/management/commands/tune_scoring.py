"""Grid-search scoring hyperparameters against the in-memory simulator.

Each trial overrides one combination of scoring-service constants and
runs the SAME pre-generated answer stream so the only variable is the params.

Grid file format (YAML):

    grid:
      ROLE_SCORE_SOFTMAX_TEMPERATURE: [1.5, 2.0, 2.242, 2.5, 3.0]
      ROLE_DISCOVERY_CONFIDENCE_THRESHOLD: [0.25, 0.289, 0.33]
      ROLE_EVIDENCE_SCORE_SCALE: [4.0, 5.229, 6.0]

Example:
    python manage.py tune_scoring --grid data/scoring_tuning_grid.yaml --samples 500
"""

import concurrent.futures
import itertools
import json
from pathlib import Path

import yaml
from django.core.management.base import BaseCommand, CommandError

from simulation.engine import (
    METRIC_HIGHER_IS_BETTER,
    METRIC_LOWER_IS_BETTER,
    TUNABLE_PARAM_NAMES,
    _pre_generate_choices,
    run_trial,
)
from simulation.loaders import count_core_questions, load_questions, load_roles


VALID_METRICS = sorted(METRIC_HIGHER_IS_BETTER | METRIC_LOWER_IS_BETTER)


class Command(BaseCommand):
    help = 'Grid-search scoring hyperparameters using the in-memory simulator.'

    def add_arguments(self, parser):
        parser.add_argument('--grid', required=True, help='Path to a YAML grid file (see module docstring).')
        parser.add_argument('--samples', type=int, default=200, help='Monte Carlo samples per trial.')
        parser.add_argument('--random-seed', type=int, default=42, help='Shared seed so every trial sees the same answer stream.')
        parser.add_argument('--workers', type=int, default=None, help='Worker process count. Defaults to os.cpu_count().')
        parser.add_argument(
            '--metric',
            default='resolved_rate',
            choices=VALID_METRICS,
            help='Metric to rank trials by. Higher-is-better metrics sort descending.',
        )
        parser.add_argument('--format', choices=['text', 'json'], default='text', help='Output format.')

    def handle(self, *args, **options):
        grid = self._load_grid(options['grid'])
        questions = load_questions()
        if not questions:
            msg = 'No active ROLE-stage questions found. Run seed_mvp_content first.'
            raise CommandError(msg)
        active_role_slugs, role_names = load_roles()
        core_target = count_core_questions(questions)
        likert_weights = {-2: 0.2, -1: 0.2, 0: 0.2, 1: 0.2, 2: 0.2}

        trials = self._expand_grid(grid)
        if not trials:
            msg = 'Grid expanded to zero trials. Check the grid file.'
            raise CommandError(msg)

        pre_generated_choices = _pre_generate_choices(
            options['samples'], len(questions), 0, likert_weights, options['random_seed'],
        )

        self.stdout.write(self.style.MIGRATE_HEADING(
            f'\n=== Scoring Hyperparameter Tuning ({len(trials)} trials x {options["samples"]} samples, '
            f'metric={options["metric"]}, seed={options["random_seed"]}) ===',
        ))

        worker_count = options['workers'] if options['workers'] and options['workers'] > 0 else None
        with concurrent.futures.ProcessPoolExecutor(max_workers=worker_count) as executor:
            futures = {
                executor.submit(
                    run_trial, trial_id, params, options['samples'], questions,
                    active_role_slugs, role_names, core_target,
                    pre_generated_choices, likert_weights, options['random_seed'], options['metric'],
                ): trial_id
                for trial_id, params in enumerate(trials)
            }
            results = [future.result() for future in concurrent.futures.as_completed(futures)]

        results.sort(
            key=lambda result: result['metric_value'],
            reverse=options['metric'] in METRIC_HIGHER_IS_BETTER,
        )

        if options['format'] == 'json':
            payload = {'metric': options['metric'], 'samples': options['samples'], 'seed': options['random_seed'], 'trials': results}
            self.stdout.write(json.dumps(payload, indent=2, sort_keys=True))
        else:
            self._print_table(results, options['metric'])

    def _load_grid(self, path: str) -> dict[str, list]:
        with Path(path).open(encoding='utf-8') as grid_file:
            data = yaml.safe_load(grid_file)
        if not isinstance(data, dict) or 'grid' not in data:
            msg = f'{path}: expected a top-level "grid" mapping of param name -> value list.'
            raise CommandError(msg)
        grid = data['grid']
        unknown = sorted(set(grid) - set(TUNABLE_PARAM_NAMES))
        if unknown:
            msg = f'{path}: unknown tunable params {unknown}. Valid: {list(TUNABLE_PARAM_NAMES)}'
            raise CommandError(msg)
        return grid

    def _expand_grid(self, grid: dict[str, list]) -> list[dict[str, float]]:
        names = list(grid)
        return [dict(zip(names, combo, strict=True)) for combo in itertools.product(*(grid[n] for n in names))]

    def _print_table(self, results: list[dict[str, object]], metric: str) -> None:
        self.stdout.write(f'{"rank":>4}  {"trial":>5}  {metric:>20}  {"resolved":>10}  {"low_conf":>10}  {"coverage":>10}  {"entropy":>10}  params')
        for rank, result in enumerate(results, start=1):
            self.stdout.write(
                f'{rank:>4}  {result["trial_id"]:>5}  {result["metric_value"]:>20.4f}  '
                f'{result["resolved_rate"] * 100:>9.1f}%  {result["low_confidence_rate"] * 100:>9.1f}%  '
                f'{result["resolved_role_coverage_rate"] * 100:>9.1f}%  {result["resolved_uniformity"]:>10.4f}  '
                f'{result["params"]}',
            )
