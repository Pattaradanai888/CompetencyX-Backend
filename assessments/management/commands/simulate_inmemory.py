"""Fast Monte Carlo twin of ``simulate_assessment`` — no DB writes, runs N
sessions in parallel via ``ProcessPoolExecutor``.

Examples:
    python manage.py simulate_inmemory --samples 1000
    python manage.py simulate_inmemory --samples 5000 --workers 8 --format json
    python manage.py simulate_inmemory --probe
"""

import json

from django.core.management.base import BaseCommand, CommandError

from roadmaps.questionnaire import ROLE_PROFILE_WEIGHTS
from simulation.engine import LIKERT_VALUES, aggregate_results, run_samples, run_single_sample
from simulation.loaders import count_core_questions, load_questions, load_roles


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
        core_target = count_core_questions(questions)
        likert_weights = self._parse_likert_weights(options['likert_weights'])
        prefix_answers = self._parse_prefix_answers(options['prefix_answers'])

        unknown_roles = sorted(set(ROLE_PROFILE_WEIGHTS) - set(active_role_slugs))
        if unknown_roles:
            self.stdout.write(self.style.WARNING(f'Role profiles without active DB rows: {", ".join(unknown_roles)}'))

        if options['probe']:
            self._run_probe(questions, active_role_slugs, role_names, core_target, likert_weights, prefix_answers)
            return

        results = run_samples(
            samples=options['samples'],
            questions=questions,
            active_role_slugs=active_role_slugs,
            role_names=role_names,
            core_target=core_target,
            prefix_answers=prefix_answers,
            likert_weights=likert_weights,
            seed=options['random_seed'],
            workers=options['workers'],
        )
        summary = aggregate_results(
            results,
            samples=options['samples'],
            seed=options['random_seed'],
            likert_weights=likert_weights,
            active_role_slugs=active_role_slugs,
            prefix_answers=prefix_answers,
        )

        if options['format'] == 'json':
            self.stdout.write(json.dumps(summary, indent=2, sort_keys=True))
        else:
            self._print_text(summary)

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

    def _run_probe(  # noqa: PLR0913
        self,
        questions: list[dict],
        active_role_slugs: list[str],
        role_names: dict[str, str],
        core_target: int,
        likert_weights: dict[int, float],
        prefix_answers: list[int],
    ) -> None:
        deterministic_answers = [next(iter(likert_weights))] * max(len(questions) - len(prefix_answers), 0)
        result = run_single_sample(
            0,
            questions,
            list(active_role_slugs),
            role_names,
            core_target,
            list(prefix_answers),
            deterministic_answers,
        )
        self.stdout.write(self.style.SUCCESS('Single-sample probe:'))
        self.stdout.write(json.dumps(result, indent=2, sort_keys=True))

    def _print_text(self, summary: dict[str, object]) -> None:
        self.stdout.write(self.style.MIGRATE_HEADING(
            f'\n=== In-Memory Role Resolution Simulation (N={summary["samples"]}, seed={summary["seed"]}) ===',
        ))
        self.stdout.write(f'Likert weights: {summary["likert_weights"]}')
        if summary.get('prefix_answers'):
            self.stdout.write(f'Prefix answers: {summary["prefix_answers"]}')
        self.stdout.write(f'Completed:      {summary["completed_count"]:4d} ({summary["completed_rate"] * 100:.1f}%)')
        self.stdout.write(f'Resolved:       {summary["resolved_count"]:4d} ({summary["resolved_rate"] * 100:.1f}%)')
        self.stdout.write(f'Low confidence: {summary["low_confidence_count"]:4d} ({summary["low_confidence_rate"] * 100:.1f}%)')
        self.stdout.write(f'Ambiguous:      {summary["ambiguous_count"]:4d} ({summary["ambiguous_rate"] * 100:.1f}%)')
        answered = summary['answered_role_questions']
        self.stdout.write(f'Answered role Qs: mean={answered["mean"]:.2f}  min={answered["min"]}  max={answered["max"]}')
        self.stdout.write(f'95% worst-case margin of error: +/-{summary["worst_case_95pct_margin_of_error"]:.4f}')

        self.stdout.write(self.style.MIGRATE_HEADING('\n--- Role coverage ---'))
        self.stdout.write(
            f'Best-fit roles seen: {summary["best_fit_role_coverage_count"]}/{summary["active_role_count"]} '
            f'({summary["best_fit_role_coverage_rate"] * 100:.1f}%)',
        )
        self.stdout.write(f'Missing best-fit roles: {", ".join(summary["missing_best_fit_roles"]) or "None"}')
        self.stdout.write(
            f'Resolved roles seen: {summary["resolved_role_coverage_count"]}/{summary["active_role_count"]} '
            f'({summary["resolved_role_coverage_rate"] * 100:.1f}%)',
        )
        self.stdout.write(f'Missing resolved roles: {", ".join(summary["missing_resolved_roles"]) or "None"}')
        resolved_shape = summary['resolved_role_uniformity']
        self.stdout.write(
            'Resolved role uniformity: '
            f'normalized_entropy={resolved_shape["normalized_entropy"]:.4f}  max_share={resolved_shape["max_share"]:.4f}',
        )

        if 'resolved_confidence' in summary:
            confidence = summary['resolved_confidence']
            margin = summary['resolved_margin_share']
            score_margin = summary['resolved_score_margin']
            winner = summary['resolved_winner_share']
            self.stdout.write(self.style.MIGRATE_HEADING('\n--- Resolved sessions ---'))
            self.stdout.write(f'Confidence:        mean={confidence["mean"]:.4f}  min={confidence["min"]:.4f}  median={confidence["median"]:.4f}')
            self.stdout.write(f'Margin (share):    mean={margin["mean"]:.4f}  min={margin["min"]:.4f}  median={margin["median"]:.4f}')
            self.stdout.write(f'Margin (score):    mean={score_margin["mean"]:.4f}'
                              f'  min={score_margin["min"]:.4f}  median={score_margin["median"]:.4f}')
            self.stdout.write(f'Winner share:      mean={winner["mean"]:.4f}  min={winner["min"]:.4f}  median={winner["median"]:.4f}')
            self.stdout.write('Best-fit role distribution:')
            for role, count in summary['resolved_roles'].items():
                self.stdout.write(f'  {role or "None":35s} {count:4d}')

        if 'low_confidence_confidence' in summary:
            confidence = summary['low_confidence_confidence']
            margin = summary['low_confidence_margin_share']
            score_margin = summary['low_confidence_score_margin']
            self.stdout.write(self.style.WARNING('\n--- Low-confidence completions ---'))
            self.stdout.write(f'Confidence:        mean={confidence["mean"]:.4f}  max={confidence["max"]:.4f}')
            self.stdout.write(f'Margin (share):    mean={margin["mean"]:.4f}  max={margin["max"]:.4f}')
            self.stdout.write(f'Margin (score):    mean={score_margin["mean"]:.4f}  max={score_margin["max"]:.4f}')
            self.stdout.write('Best-fit role distribution:')
            for role, count in list(summary.get('low_confidence_roles', {}).items())[:10]:
                self.stdout.write(f'  {role:35s} {count:4d}')
