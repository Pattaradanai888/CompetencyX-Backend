import json
import logging
import math
import random
import statistics
from collections import Counter

from django.core.management.base import BaseCommand
from django.db import transaction

from assessments.flow import create_assessment_session, get_current_question, submit_answer
from assessments.models import AssessmentSession
from assessments.role_inference import _get_role_inference_snapshot, _is_core_role_profile_complete, get_role_resolution_status
from roadmaps.models import Question
from roadmaps.questionnaire import ROLE_PROFILE_WEIGHTS


LIKERT_VALUES = [-2, -1, 0, 1, 2]


class Command(BaseCommand):
    help = 'Simulate assessment sessions with uniform-random likert answers to measure role-resolution outcomes and gate failures.'

    def add_arguments(self, parser):
        parser.add_argument('--samples', type=int, default=100, help='Number of simulated sessions.')
        parser.add_argument('--random-seed', type=int, default=42, help='Random seed for reproducibility.')
        parser.add_argument('--format', choices=['text', 'json'], default='text', help='Output format.')

    @transaction.atomic
    def handle(self, *args, **options):
        samples = options['samples']
        random.seed(options['random_seed'])
        logging.disable(logging.INFO)
        try:
            results = []
            for _ in range(samples):
                session = create_assessment_session(profile={})
                role_question_count = 0
                while True:
                    question = get_current_question(session)
                    if question is None:
                        break
                    if question.question_type == Question.Type.LIKERT_5:
                        submit_answer(session=session, question=question, scale_value=random.choice(LIKERT_VALUES))  # noqa: S311
                    else:
                        question_options = list(question.options.all())
                        chosen = random.choice(question_options) if question_options else None  # noqa: S311
                        submit_answer(session=session, question=question, option=chosen)
                    session.refresh_from_db()
                    role_question_count += 1

                snapshot = _get_role_inference_snapshot(session)
                resolution_status = get_role_resolution_status(session)
                results.append({
                    'phase': session.phase,
                    'status': session.status,
                    'role_resolution_status': resolution_status,
                    'best_fit_role': session.best_fit_role.slug if session.best_fit_role else None,
                    'confidence': round(session.best_fit_confidence, 4),
                    'margin_share': round(float(snapshot['margin_share']), 4),
                    'score_margin': round(float(snapshot['score_margin']), 4),
                    'winner_share': round(float(snapshot['winner_share']), 4),
                    'entropy': round(float(snapshot['entropy']), 4),
                    'role_qs': role_question_count,
                    'core_complete': _is_core_role_profile_complete(session),
                })

            summary = self._summarize(results, samples, options['random_seed'])
        finally:
            logging.disable(logging.NOTSET)

        if options['format'] == 'json':
            self.stdout.write(json.dumps(summary, indent=2, sort_keys=True))
        else:
            self._print_text(summary)

    def _summarize(self, results, samples, seed):
        completed_phases = {
            AssessmentSession.Phase.RECOMMENDATION_READY,
            AssessmentSession.Phase.COMPLETED,
        }
        completed = [r for r in results if r['phase'] in completed_phases]
        resolved = [r for r in results if r['role_resolution_status'] == 'resolved']
        low_confidence = [r for r in results if r['role_resolution_status'] == 'low_confidence']
        ambiguous = [r for r in results if r['phase'] == AssessmentSession.Phase.ROLE_AMBIGUITY]
        all_role_slugs = set(ROLE_PROFILE_WEIGHTS)
        resolved_role_counts = Counter(r['best_fit_role'] for r in resolved if r['best_fit_role'])
        best_fit_role_counts = Counter(r['best_fit_role'] for r in results if r['best_fit_role'])
        resolved_roles_seen = set(resolved_role_counts)
        best_fit_roles_seen = set(best_fit_role_counts)

        summary = {
            'samples': samples,
            'seed': seed,
            'random_answer_values': LIKERT_VALUES,
            'active_role_count': len(all_role_slugs),
            'completed_count': len(completed),
            'completed_rate': round(len(completed) / samples, 4),
            'resolved_count': len(resolved),
            'resolved_rate': round(len(resolved) / samples, 4),
            'low_confidence_count': len(low_confidence),
            'low_confidence_rate': round(len(low_confidence) / samples, 4),
            'ambiguous_count': len(ambiguous),
            'ambiguous_rate': round(len(ambiguous) / samples, 4),
            'best_fit_role_coverage_count': len(best_fit_roles_seen),
            'best_fit_role_coverage_rate': round(len(best_fit_roles_seen) / len(all_role_slugs), 4),
            'missing_best_fit_roles': sorted(all_role_slugs - best_fit_roles_seen),
            'best_fit_role_uniformity': self._distribution_shape(best_fit_role_counts, len(all_role_slugs)),
            'resolved_role_coverage_count': len(resolved_roles_seen),
            'resolved_role_coverage_rate': round(len(resolved_roles_seen) / len(all_role_slugs), 4),
            'missing_resolved_roles': sorted(all_role_slugs - resolved_roles_seen),
            'resolved_role_uniformity': self._distribution_shape(resolved_role_counts, len(all_role_slugs)),
        }

        if resolved:
            confs = [r['confidence'] for r in resolved]
            margins = [r['margin_share'] for r in resolved]
            score_margins = [r['score_margin'] for r in resolved]
            shares = [r['winner_share'] for r in resolved]
            summary['resolved_confidence'] = self._stats(confs)
            summary['resolved_margin_share'] = self._stats(margins)
            summary['resolved_score_margin'] = self._stats(score_margins)
            summary['resolved_winner_share'] = self._stats(shares)
            summary['resolved_roles'] = dict(Counter(r['best_fit_role'] for r in resolved).most_common())

        if low_confidence:
            low_confs = [r['confidence'] for r in low_confidence]
            low_margins = [r['margin_share'] for r in low_confidence]
            low_score_margins = [r['score_margin'] for r in low_confidence]
            summary['low_confidence_confidence'] = self._stats(low_confs)
            summary['low_confidence_margin_share'] = self._stats(low_margins)
            summary['low_confidence_score_margin'] = self._stats(low_score_margins)
            summary['low_confidence_roles'] = dict(Counter(r['best_fit_role'] for r in low_confidence if r['best_fit_role']).most_common())

        if ambiguous:
            amb_confs = [r['confidence'] for r in ambiguous]
            amb_margins = [r['margin_share'] for r in ambiguous]
            amb_score_margins = [r['score_margin'] for r in ambiguous]
            summary['ambiguous_confidence'] = self._stats(amb_confs)
            summary['ambiguous_margin_share'] = self._stats(amb_margins)
            summary['ambiguous_score_margin'] = self._stats(amb_score_margins)
            summary['ambiguous_roles'] = dict(Counter(r['best_fit_role'] for r in ambiguous if r['best_fit_role']).most_common())

        return summary

    def _stats(self, values):
        return {
            'mean': round(statistics.mean(values), 4),
            'min': round(min(values), 4),
            'max': round(max(values), 4),
            'median': round(statistics.median(values), 4),
        }

    def _distribution_shape(self, role_counts, role_count):
        total = sum(role_counts.values())
        if total == 0 or role_count == 0:
            return {
                'normalized_entropy': 0.0,
                'max_share': 0.0,
                'min_seen_share': 0.0,
            }

        probabilities = [count / total for count in role_counts.values()]
        entropy = -sum(probability * math.log(probability) for probability in probabilities)
        normalized_entropy = entropy / math.log(role_count) if role_count > 1 else 1.0
        return {
            'normalized_entropy': round(normalized_entropy, 4),
            'max_share': round(max(probabilities), 4),
            'min_seen_share': round(min(probabilities), 4),
        }

    def _print_text(self, s):
        self.stdout.write(self.style.MIGRATE_HEADING(f'\n=== Assessment Resolution Simulation (N={s["samples"]}, seed={s["seed"]}) ==='))
        self.stdout.write(f'Random answer values: {s["random_answer_values"]}')
        self.stdout.write(f'Completed:      {s["completed_count"]:4d} ({s["completed_rate"] * 100:.1f}%)')
        self.stdout.write(f'Resolved:       {s["resolved_count"]:4d} ({s["resolved_rate"] * 100:.1f}%)')
        self.stdout.write(f'Low confidence: {s["low_confidence_count"]:4d} ({s["low_confidence_rate"] * 100:.1f}%)')
        self.stdout.write(f'Ambiguous:      {s["ambiguous_count"]:4d} ({s["ambiguous_rate"] * 100:.1f}%)')
        self.stdout.write(self.style.MIGRATE_HEADING('\n--- Role coverage ---'))
        self.stdout.write(
            f'Best-fit roles seen: {s["best_fit_role_coverage_count"]}/{s["active_role_count"]} '
            f'({s["best_fit_role_coverage_rate"] * 100:.1f}%)'
        )
        self.stdout.write(f'Missing best-fit roles: {", ".join(s["missing_best_fit_roles"]) or "None"}')
        self.stdout.write(
            f'Resolved roles seen: {s["resolved_role_coverage_count"]}/{s["active_role_count"]} '
            f'({s["resolved_role_coverage_rate"] * 100:.1f}%)'
        )
        self.stdout.write(f'Missing resolved roles: {", ".join(s["missing_resolved_roles"]) or "None"}')
        resolved_shape = s['resolved_role_uniformity']
        self.stdout.write(
            'Resolved role uniformity: '
            f'normalized_entropy={resolved_shape["normalized_entropy"]:.4f}  max_share={resolved_shape["max_share"]:.4f}'
        )

        if 'resolved_confidence' in s:
            c = s['resolved_confidence']
            m = s['resolved_margin_share']
            sm = s['resolved_score_margin']
            w = s['resolved_winner_share']
            self.stdout.write(self.style.MIGRATE_HEADING('\n--- Resolved sessions ---'))
            self.stdout.write(f'Confidence: mean={c["mean"]:.4f}  min={c["min"]:.4f}  median={c["median"]:.4f}')
            self.stdout.write(f'Margin (share diff): mean={m["mean"]:.4f}  min={m["min"]:.4f}  median={m["median"]:.4f}')
            self.stdout.write(f'Margin (score diff): mean={sm["mean"]:.4f}  min={sm["min"]:.4f}  median={sm["median"]:.4f}')
            self.stdout.write(f'Winner share: mean={w["mean"]:.4f}  min={w["min"]:.4f}  median={w["median"]:.4f}')
            self.stdout.write('Best-fit role distribution:')
            for role, count in s['resolved_roles'].items():
                self.stdout.write(f'  {role or "None":35s} {count:4d}')

        if 'low_confidence_confidence' in s:
            c = s['low_confidence_confidence']
            m = s['low_confidence_margin_share']
            sm = s['low_confidence_score_margin']
            self.stdout.write(self.style.WARNING('\n--- Low-confidence completions ---'))
            self.stdout.write(f'Confidence: mean={c["mean"]:.4f}  max={c["max"]:.4f}')
            self.stdout.write(f'Margin (share diff): mean={m["mean"]:.4f}  max={m["max"]:.4f}')
            self.stdout.write(f'Margin (score diff): mean={sm["mean"]:.4f}  max={sm["max"]:.4f}')
            self.stdout.write('Best-fit role distribution:')
            for role, count in list(s['low_confidence_roles'].items())[:10]:
                self.stdout.write(f'  {role:35s} {count:4d}')

        if 'ambiguous_confidence' in s:
            c = s['ambiguous_confidence']
            m = s['ambiguous_margin_share']
            sm = s['ambiguous_score_margin']
            self.stdout.write(self.style.WARNING('\n--- Ambiguous sessions ---'))
            self.stdout.write(f'Confidence: mean={c["mean"]:.4f}  max={c["max"]:.4f}')
            self.stdout.write(f'Margin (share diff): mean={m["mean"]:.4f}  max={m["max"]:.4f}')
            self.stdout.write(f'Margin (score diff): mean={sm["mean"]:.4f}  max={sm["max"]:.4f}')
            self.stdout.write('Top role among ambiguous:')
            for role, count in list(s['ambiguous_roles'].items())[:10]:
                self.stdout.write(f'  {role:35s} {count:4d}')
