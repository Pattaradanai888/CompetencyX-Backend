"""End-to-end DB twin of ``simulate_inmemory``: drives real sessions through
``submit_answer`` with uniform-random Likert answers, then reuses the engine's
aggregation and the shared text reporter.
"""

import json
import logging
import random

from django.core.management.base import BaseCommand
from django.db import transaction

from assessments.services.assessment_service import create_assessment_session, get_current_question, submit_answer
from assessments.services.role_inference_service import get_role_inference_snapshot, get_role_resolution_status
from roadmaps.models import Question
from roadmaps.questionnaire import ROLE_PROFILE_WEIGHTS
from simulation.engine import CatalogContext, SimulationConfig, aggregate_results
from simulation.reporting import write_summary_text


LIKERT_VALUES = [-2, -1, 0, 1, 2]
UNIFORM_LIKERT_WEIGHTS = {-2: 0.2, -1: 0.2, 0: 0.2, 1: 0.2, 2: 0.2}
COMPLETED_PHASES = {'recommendation_ready', 'completed'}


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
            results = [self._run_db_sample(sample_index) for sample_index in range(samples)]
        finally:
            logging.disable(logging.NOTSET)

        catalog = CatalogContext(
            questions=[],
            active_role_slugs=sorted(ROLE_PROFILE_WEIGHTS),
            role_names={},
            core_target=0,
        )
        config = SimulationConfig(
            samples=samples,
            seed=options['random_seed'],
            likert_weights=UNIFORM_LIKERT_WEIGHTS,
        )
        summary = aggregate_results(results, catalog=catalog, config=config)

        if options['format'] == 'json':
            self.stdout.write(json.dumps(summary, indent=2, sort_keys=True))
        else:
            write_summary_text(self.stdout, self.style, summary, title='Assessment Resolution Simulation')

    def _run_db_sample(self, sample_index: int) -> dict[str, object]:
        session = create_assessment_session(profile={})
        answered_core = 0
        answered_tie_break = 0
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
            if question.item_group == Question.ItemGroup.TIE_BREAK:
                answered_tie_break += 1
            else:
                answered_core += 1

        snapshot = get_role_inference_snapshot(session)
        best_fit_role_slug = session.best_fit_role.slug if session.best_fit_role else None
        return {
            'sample_index': sample_index,
            'phase': session.phase,
            # aggregate_results counts completion by status; mirror the phase gate the DB flow uses.
            'status': 'completed' if session.phase in COMPLETED_PHASES else 'incomplete',
            'resolution_status': get_role_resolution_status(session),
            'best_fit_role': best_fit_role_slug,
            'top_ranked_role': best_fit_role_slug,
            'answered_core_questions': answered_core,
            'answered_tie_break_questions': answered_tie_break,
            'answered_role_questions': answered_core + answered_tie_break,
            'confidence': round(session.best_fit_confidence, 4),
            'margin_share': round(float(snapshot['margin_share']), 4),
            'score_margin': round(float(snapshot['score_margin']), 4),
            'winner_share': round(float(snapshot['winner_share']), 4),
        }
