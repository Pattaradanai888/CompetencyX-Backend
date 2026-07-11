"""Fast Monte Carlo twin of ``simulate_assessment`` - no DB writes, runs N
sessions in parallel via ``ProcessPoolExecutor``.

Examples:
    python manage.py simulate_inmemory --samples 1000
    python manage.py simulate_inmemory --samples 5000 --workers 8 --format json
    python manage.py simulate_inmemory --probe
"""

import json

from django.core.management.base import BaseCommand, CommandError

from roadmaps.questionnaire import ROLE_PROFILE_WEIGHTS
from simulation.engine import LIKERT_VALUES, CatalogContext, SimulationConfig, aggregate_results, run_samples, run_single_sample
from simulation.loaders import count_core_questions, load_questions, load_roles
from simulation.reporting import write_summary_text


class Command(BaseCommand):
    help = 'Fast in-memory Monte Carlo simulation of role-discovery scoring (no DB writes).'

    def add_arguments(self, parser):
        parser.add_argument('--samples', type=int, default=1000, help='Number of simulated sessions.')
        parser.add_argument('--random-seed', type=int, default=42, help='Random seed for reproducible answer streams.')
        parser.add_argument('--workers', type=int, default=None, help='Worker process count. Defaults to os.cpu_count().')
        parser.add_argument(
            '--likert-weights',
            default='0.2,0.2,0.2,0.2,0.2',
            help=(
                'Comma weights for Likert values -2,-1,0,1,2 in order. '
                'Default is uniform to match simulate_assessment; '
                'use 0.1,0.2,0.4,0.2,0.1 for a realistic centered distribution.'
            ),
        )
        parser.add_argument(
            '--prefix-answers',
            default='',
            help='Comma-separated fixed answers (e.g. "2,2,-1") applied to the first questions of every sample.',
        )
        parser.add_argument('--format', choices=['text', 'json'], default='text', help='Output format.')
        parser.add_argument(
            '--probe',
            action='store_true',
            help='Run a single deterministic sample and print its metrics (quick smoke check).',
        )

    def handle(self, *args, **options):
        questions = load_questions()
        if not questions:
            msg = 'No active ROLE-stage questions found. Run seed_mvp_content first.'
            raise CommandError(msg)
        active_role_slugs, role_names = load_roles()
        catalog = CatalogContext(
            questions=questions,
            active_role_slugs=active_role_slugs,
            role_names=role_names,
            core_target=count_core_questions(questions),
        )
        config = SimulationConfig(
            samples=options['samples'],
            seed=options['random_seed'],
            likert_weights=self._parse_likert_weights(options['likert_weights']),
            prefix_answers=self._parse_prefix_answers(options['prefix_answers']),
            workers=options['workers'],
        )

        unknown_roles = sorted(set(ROLE_PROFILE_WEIGHTS) - set(active_role_slugs))
        if unknown_roles:
            self.stdout.write(self.style.WARNING(f'Role profiles without active DB rows: {", ".join(unknown_roles)}'))

        if options['probe']:
            self._run_probe(catalog, config)
            return

        results = run_samples(catalog, config)
        summary = aggregate_results(results, catalog=catalog, config=config)

        if options['format'] == 'json':
            self.stdout.write(json.dumps(summary, indent=2, sort_keys=True))
        else:
            write_summary_text(self.stdout, self.style, summary, title='In-Memory Role Resolution Simulation')

    def _parse_likert_weights(self, raw: str) -> dict[int, float]:
        parts = [part.strip() for part in raw.split(',') if part.strip()]
        if len(parts) != len(LIKERT_VALUES):
            msg = f'--likert-weights needs exactly {len(LIKERT_VALUES)} comma-separated values.'
            raise ValueError(msg)
        return {value: float(part) for value, part in zip(LIKERT_VALUES, parts, strict=True)}

    def _parse_prefix_answers(self, raw: str) -> list[int]:
        if not raw.strip():
            return []
        return [int(part.strip()) for part in raw.split(',') if part.strip()]

    def _run_probe(self, catalog: CatalogContext, config: SimulationConfig) -> None:
        deterministic_answers = [next(iter(config.likert_weights))] * max(len(catalog.questions) - len(config.prefix_answers), 0)
        result = run_single_sample(0, catalog, list(config.prefix_answers), deterministic_answers)
        self.stdout.write(self.style.SUCCESS('Single-sample probe:'))
        self.stdout.write(json.dumps(result, indent=2, sort_keys=True))
