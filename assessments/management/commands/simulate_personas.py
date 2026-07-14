"""Persona-fidelity harness: can the question bank recover the role a noisy
persona was generated from? Gates every content/weights change.

Examples:
    python manage.py simulate_personas
    python manage.py simulate_personas --samples-per-role 100 --format json
    python manage.py simulate_personas --write-baseline data/simulation/persona_baseline.json
    python manage.py simulate_personas --check-baseline data/simulation/persona_baseline.json
"""

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from simulation.engine import CatalogContext
from simulation.loaders import count_core_questions, load_questions, load_roles
from simulation.personas import build_baseline, compare_to_baseline, compute_content_digest, run_persona_suite


CONFUSION_REPORT_LIMIT = 12
WORST_ROLE_REPORT_LIMIT = 8
LOW_ACCURACY_WARNING_THRESHOLD = 0.8


class Command(BaseCommand):
    help = 'Simulate noisy personas for every role and report how reliably role discovery recovers them.'

    def add_arguments(self, parser):
        parser.add_argument('--samples-per-role', type=int, default=50, help='Noisy samples per role.')
        parser.add_argument('--random-seed', type=int, default=42, help='Seed for reproducible noise.')
        parser.add_argument('--format', choices=['text', 'json'], default='text', help='Output format.')
        parser.add_argument('--write-baseline', metavar='PATH', help='Write the run summary as the new baseline JSON.')
        parser.add_argument('--check-baseline', metavar='PATH', help='Compare this run against a baseline JSON; exit 1 on regression.')
        parser.add_argument('--tolerance', type=float, default=0.02, help='Allowed metric drop vs baseline (default 0.02).')

    def handle(self, *args, **options):
        questions = load_questions()
        if not questions:
            msg = 'No active ROLE-stage questions found. Run sync_content first.'
            raise CommandError(msg)
        active_role_slugs, role_names = load_roles()
        catalog = CatalogContext(
            questions=questions,
            active_role_slugs=active_role_slugs,
            role_names=role_names,
            core_target=count_core_questions(questions),
        )

        baseline = None
        if options['check_baseline']:
            baseline_path = Path(options['check_baseline'])
            if not baseline_path.exists():
                msg = f'Baseline file not found: {baseline_path}'
                raise CommandError(msg)
            baseline = json.loads(baseline_path.read_text(encoding='utf-8'))

        seed = baseline['seed'] if baseline else options['random_seed']
        samples_per_role = baseline['samples_per_role'] if baseline else options['samples_per_role']

        summary = run_persona_suite(catalog, samples_per_role=samples_per_role, seed=seed)
        content_digest = compute_content_digest(catalog)

        if options['format'] == 'json':
            self.stdout.write(json.dumps({**summary, 'content_digest': content_digest}, indent=2, sort_keys=True))
        else:
            self._write_text_report(summary)

        if options['write_baseline']:
            baseline_path = Path(options['write_baseline'])
            baseline_path.parent.mkdir(parents=True, exist_ok=True)
            baseline_path.write_text(
                json.dumps(build_baseline(summary, content_digest=content_digest), indent=2, sort_keys=True) + '\n',
                encoding='utf-8',
            )
            self.stdout.write(self.style.SUCCESS(f'Baseline written to {baseline_path}'))

        if baseline is not None:
            failures = compare_to_baseline(summary, baseline, content_digest=content_digest, tolerance=options['tolerance'])
            if failures:
                for failure in failures:
                    self.stdout.write(self.style.ERROR(f'BASELINE CHECK FAILED: {failure}'))
                msg = 'Persona baseline check failed.'
                raise CommandError(msg)
            self.stdout.write(self.style.SUCCESS('Baseline check passed.'))

    def _write_text_report(self, summary: dict) -> None:
        write = self.stdout.write
        write(self.style.MIGRATE_HEADING(
            f'\n=== Persona Fidelity (N={summary["samples_per_role"]}/role, seed={summary["seed"]}) ===',
        ))
        write(f'Top-1 accuracy:       {summary["top1_accuracy"]:.4f}')
        write(f'Resolved rate:        {summary["resolved_rate"]:.4f}')
        write(f'Precision | resolved: {summary["precision_resolved"]:.4f}')
        write(f'Avg questions asked:  {summary["avg_answered_questions"]:.2f}')
        write(f'Tie-break usage:      {summary["tie_break_usage_rate"]:.4f}')

        write(self.style.MIGRATE_HEADING('\n--- Weakest roles (top-1 accuracy) ---'))
        worst = sorted(summary['per_role_accuracy'].items(), key=lambda item: item[1])[:WORST_ROLE_REPORT_LIMIT]
        for slug, accuracy in worst:
            style = self.style.WARNING if accuracy < LOW_ACCURACY_WARNING_THRESHOLD else (lambda text: text)
            write(style(f'  {slug:36s} {accuracy:.2f}'))

        write(self.style.MIGRATE_HEADING('\n--- Top confusion pairs ---'))
        for pair in summary['confusion_pairs'][:CONFUSION_REPORT_LIMIT]:
            write(f'  {pair["true_role"]:32s} -> {pair["predicted_role"]:32s} {pair["count"]}')

        if summary['dead_question_ids']:
            write(self.style.WARNING(
                f'\nDead questions (never discriminated true role from its confuser): {summary["dead_question_ids"]}',
            ))
        else:
            write('\nNo dead questions detected.')
