import json
import logging
import math
import random
from collections import Counter

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from assessments.role_inference import _get_role_inference_snapshot, get_role_resolution_status
from assessments.services import create_assessment_session, get_current_question, submit_answer
from roadmaps.models import Question, Role


LIKERT_VALUES = (-2, -1, 0, 1, 2)


class Command(BaseCommand):
    help = 'Estimate final role probabilities with Monte Carlo sampling over adaptive role-discovery Likert answers.'

    def add_arguments(self, parser):
        parser.add_argument('--samples', type=int, default=10)
        parser.add_argument('--answers', default='')
        parser.add_argument('--likert-weights', default='1,1,1,1,1')
        parser.add_argument('--random-seed', type=int, default=12345)
        parser.add_argument('--preferred-role-slug')
        parser.add_argument('--top-roles', type=int, default=10)
        parser.add_argument('--format', choices=('text', 'json'), default='text')
        parser.add_argument('--seed-content', action='store_true')
        parser.add_argument('--verbose-events', action='store_true')
        parser.add_argument('--policy-mode', choices=('core_sequence', 'info_gain'), default=None,
                            help='Override ASSESSMENT_BANDIT_POLICY_MODE for the simulation.')

    def handle(self, *args, **options):
        if options['samples'] <= 0:
            msg = '--samples must be greater than 0.'
            raise CommandError(msg)
        if options['top_roles'] <= 0:
            msg = '--top-roles must be greater than 0.'
            raise CommandError(msg)

        if options['seed_content']:
            call_command('seed_mvp_content', stdout=self.stdout)

        if not Question.objects.filter(stage=Question.Stage.ROLE, is_active=True).exists():
            msg = 'No active role questions found. Run `python manage.py seed_mvp_content` first.'
            raise CommandError(msg)

        preferred_role = None
        if options['preferred_role_slug']:
            preferred_role = Role.objects.filter(slug=options['preferred_role_slug'], is_active=True).first()
            if preferred_role is None:
                msg = f'Unknown active role slug: {options["preferred_role_slug"]}'
                raise CommandError(msg)

        prefix_answers = self._parse_answers(options['answers'])
        likert_weights = self._parse_likert_weights(options['likert_weights'])
        rng = random.Random(options['random_seed'])  # noqa: S311

        policy_mode = options.get('policy_mode')
        if policy_mode:
            from django.test import override_settings
            with override_settings(ASSESSMENT_BANDIT_POLICY_MODE=policy_mode):
                summary = self._estimate_probabilities(
                    samples=options['samples'],
                    prefix_answers=prefix_answers,
                    likert_weights=likert_weights,
                    preferred_role=preferred_role,
                    top_roles=options['top_roles'],
                    rng=rng,
                    suppress_assessment_logs=not options['verbose_events'],
                )
        else:
            summary = self._estimate_probabilities(
                samples=options['samples'],
                prefix_answers=prefix_answers,
                likert_weights=likert_weights,
                preferred_role=preferred_role,
                top_roles=options['top_roles'],
                rng=rng,
                suppress_assessment_logs=not options['verbose_events'],
            )

        if options['format'] == 'json':
            self.stdout.write(json.dumps(summary, indent=2, sort_keys=True))
            return

        self._write_text_summary(summary)

    def _parse_answers(self, raw_answers: str) -> list[int]:
        if not raw_answers.strip():
            return []
        answers = []
        for raw_value in raw_answers.split(','):
            value = int(raw_value.strip())
            if value not in LIKERT_VALUES:
                msg = f'Invalid answer "{value}". Use only -2,-1,0,1,2.'
                raise CommandError(msg)
            answers.append(value)
        return answers

    def _parse_likert_weights(self, raw_weights: str) -> dict[int, float]:
        parts = [part.strip() for part in raw_weights.split(',') if part.strip()]
        if len(parts) != len(LIKERT_VALUES):
            msg = '--likert-weights must have exactly 5 comma-separated values for -2,-1,0,1,2.'
            raise CommandError(msg)

        weights: dict[int, float] = {}
        for likert_value, raw_weight in zip(LIKERT_VALUES, parts, strict=True):
            weight = float(raw_weight)
            if weight < 0:
                msg = '--likert-weights cannot contain negative values.'
                raise CommandError(msg)
            weights[likert_value] = weight

        if sum(weights.values()) <= 0:
            msg = '--likert-weights must contain at least one positive value.'
            raise CommandError(msg)
        return weights

    def _estimate_probabilities(self, *, samples, prefix_answers, likert_weights, preferred_role, top_roles, rng, suppress_assessment_logs):  # noqa: PLR0913
        active_role_slugs = list(Role.objects.filter(is_active=True).order_by('slug').values_list('slug', flat=True))
        resolved_role_counts: Counter[str] = Counter()
        top_ranked_role_counts: Counter[str] = Counter()
        resolution_status_counts: Counter[str] = Counter()
        phase_counts: Counter[str] = Counter()
        answered_role_question_total = 0
        confidence_total = 0.0

        assessments_logger = logging.getLogger('assessments.services')
        original_disabled = assessments_logger.disabled
        if suppress_assessment_logs:
            assessments_logger.disabled = True
        try:
            for _index in range(samples):
                sample = self._run_sample(
                    prefix_answers=prefix_answers,
                    likert_weights=likert_weights,
                    preferred_role=preferred_role,
                    rng=rng,
                )
                resolution_status_counts[sample['resolution_status']] += 1
                phase_counts[sample['phase']] += 1
                answered_role_question_total += sample['answered_role_questions']
                confidence_total += sample['confidence']
                if sample['resolved_role_slug'] is not None:
                    resolved_role_counts[sample['resolved_role_slug']] += 1
                if sample['top_ranked_role_slug'] is not None:
                    top_ranked_role_counts[sample['top_ranked_role_slug']] += 1
        finally:
            assessments_logger.disabled = original_disabled

        return {
            'samples': samples,
            'prefix_answers': prefix_answers,
            'likert_values': list(LIKERT_VALUES),
            'likert_weights': {str(key): likert_weights[key] for key in LIKERT_VALUES},
            'preferred_role_slug': preferred_role.slug if preferred_role else None,
            'active_role_count': len(active_role_slugs),
            'average_answered_role_questions': answered_role_question_total / samples,
            'average_confidence': confidence_total / samples,
            'resolution_status_rates': self._format_counter(resolution_status_counts, samples),
            'phase_rates': self._format_counter(phase_counts, samples),
            'resolved_role_rates': self._format_counter(resolved_role_counts, samples, limit=top_roles, all_slugs=active_role_slugs),
            'top_ranked_role_rates': self._format_counter(top_ranked_role_counts, samples, limit=top_roles, all_slugs=active_role_slugs),
            'questionnaire_metrics': {
                'resolved_rate': resolution_status_counts['resolved'] / samples,
                'ambiguous_rate': resolution_status_counts['ambiguous'] / samples,
                'unknown_rate': resolution_status_counts['unknown'] / samples,
                'in_progress_rate': resolution_status_counts['in_progress'] / samples,
                'top_ranked_distribution': self._distribution_metrics(top_ranked_role_counts, samples, active_role_slugs),
                'resolved_role_distribution': self._distribution_metrics(resolved_role_counts, samples, active_role_slugs),
                'worst_case_95pct_margin_of_error': 1.96 * ((0.25 / samples) ** 0.5),
            },
        }

    def _run_sample(self, *, prefix_answers, likert_weights, preferred_role, rng):
        with transaction.atomic():
            session = create_assessment_session(preferred_role=preferred_role, profile={})
            answered_role_questions = 0

            while True:
                question = get_current_question(session)
                if question is None or question.stage != Question.Stage.ROLE:
                    break

                if answered_role_questions < len(prefix_answers):
                    scale_value = prefix_answers[answered_role_questions]
                else:
                    scale_value = rng.choices(
                        population=list(LIKERT_VALUES),
                        weights=[likert_weights[value] for value in LIKERT_VALUES],
                        k=1,
                    )[0]

                submit_answer(session=session, question=question, scale_value=scale_value)
                answered_role_questions += 1
                session.refresh_from_db()

            snapshot = _get_role_inference_snapshot(session)
            resolution_status = get_role_resolution_status(session)
            sample = {
                'answered_role_questions': answered_role_questions,
                'resolution_status': resolution_status,
                'phase': session.phase,
                'confidence': float(snapshot['confidence']),
                'resolved_role_slug': session.best_fit_role.slug if resolution_status == 'resolved' and session.best_fit_role else None,
                'top_ranked_role_slug': snapshot['top_role_slug'],
            }
            transaction.set_rollback(True)
            return sample

    def _format_counter(self, counts: Counter[str], sample_count: int, *, limit: int | None = None, all_slugs: list[str] | None = None):
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

    def _distribution_metrics(self, counts: Counter[str], sample_count: int, role_slugs: list[str]) -> dict[str, object]:
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

    def _write_text_summary(self, summary: dict):
        self.stdout.write(f"Samples: {summary['samples']}")
        self.stdout.write(f"Prefix answers: {summary['prefix_answers'] or 'none'}")
        self.stdout.write(f"Preferred role: {summary['preferred_role_slug'] or 'none'}")
        self.stdout.write(f"Likert weights: {summary['likert_weights']}")
        self.stdout.write(f"Avg answered role questions: {summary['average_answered_role_questions']:.2f}")
        self.stdout.write(f"Avg confidence: {summary['average_confidence']:.4f}")
        self.stdout.write('')
        self.stdout.write('Resolution status rates:')
        for item in summary['resolution_status_rates']:
            self.stdout.write(f"  {item['slug']}: {item['probability']:.4f} ({item['count']})")
        self.stdout.write('')
        self.stdout.write('Resolved role rates:')
        for item in summary['resolved_role_rates']:
            self.stdout.write(f"  {item['slug']}: {item['probability']:.4f} ({item['count']})")
        self.stdout.write('')
        self.stdout.write('Top ranked role rates:')
        for item in summary['top_ranked_role_rates']:
            self.stdout.write(f"  {item['slug']}: {item['probability']:.4f} ({item['count']})")
        self.stdout.write('')
        self.stdout.write('Questionnaire metrics:')
        metrics = summary['questionnaire_metrics']
        self.stdout.write(f"  resolved_rate: {metrics['resolved_rate']:.4f}")
        self.stdout.write(f"  ambiguous_rate: {metrics['ambiguous_rate']:.4f}")
        self.stdout.write(f"  worst_case_95pct_margin_of_error: +/-{metrics['worst_case_95pct_margin_of_error']:.4f}")
        top_ranked_metrics = metrics['top_ranked_distribution']
        self.stdout.write(f"  top_ranked.hit_role_count: {top_ranked_metrics['hit_role_count']}")
        self.stdout.write(f"  top_ranked.effective_role_count: {top_ranked_metrics['effective_role_count']:.2f}")
        self.stdout.write(f"  top_ranked.normalized_entropy: {top_ranked_metrics['normalized_entropy']:.4f}")
        self.stdout.write(f"  top_ranked.top_3_probability_mass: {top_ranked_metrics['top_3_probability_mass']:.4f}")
