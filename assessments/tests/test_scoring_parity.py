"""Parity tests between the pure scoring path and the DB-backed path.

These seed the full MVP catalog and assert that the pure scoring path
produces snapshots identical to the DB-backed role-inference service path.
This is the drift detector: if scoring and role inference ever disagree,
these tests fail.
"""

from django.core.management import call_command
from rest_framework.test import APITestCase

from assessments.services import scoring_service
from assessments.services.assessment_service import create_assessment_session, submit_answer
from assessments.services.role_inference_service import answer_to_signal_dict, get_role_inference_snapshot
from roadmaps.models import Question, Role
from simulation.engine import LIKERT_VALUES, CatalogContext, SimulationConfig, aggregate_results, run_single_sample


class ScoringParityTests(APITestCase):
    """The drift detector: pure scoring must match the DB-backed path."""

    @classmethod
    def setUpTestData(cls):
        call_command('seed_mvp_content')
        cls.active_role_slugs = list(Role.objects.filter(is_active=True).values_list('slug', flat=True))
        cls.role_names = dict(Role.objects.filter(is_active=True).values_list('slug', 'name'))
        cls.core_target = Question.objects.filter(
            stage=Question.Stage.ROLE,
            item_group=Question.ItemGroup.CORE,
            is_active=True,
        ).count()

    def _build_session_answer_dicts(self, session):
        return [
            answer_to_signal_dict(answer)
            for answer in session.answers.select_related('question')
            if answer.question.stage == Question.Stage.ROLE
        ]

    def test_db_snapshot_matches_pure_snapshot(self):
        session = create_assessment_session(profile={})
        likert_questions = list(
            Question.objects.filter(stage=Question.Stage.ROLE, is_active=True).order_by('display_order', 'id'),
        )
        for index, question in enumerate(likert_questions[:12]):
            scale_value = [2, -1, 1, 0, 2, -2, 1, -1, 2, 0, 1, -1][index]
            submit_answer(session=session, question=question, scale_value=scale_value)
            session.refresh_from_db()

        db_snapshot = get_role_inference_snapshot(session)

        answer_dicts = self._build_session_answer_dicts(session)
        evidence = scoring_service.compute_role_evidence_snapshot(answer_dicts)
        pure_snapshot = scoring_service.build_role_inference_snapshot(
            evidence,
            active_role_slugs=self.active_role_slugs,
            role_names=self.role_names,
            answered_core=sum(1 for answer in answer_dicts),
            core_target=self.core_target,
            answered_tie_break=0,
        )

        assert pure_snapshot['top_role_slug'] == db_snapshot['top_role_slug']
        assert abs(float(pure_snapshot['confidence']) - float(db_snapshot['confidence'])) < 1e-9
        assert abs(float(pure_snapshot['margin_share']) - float(db_snapshot['margin_share'])) < 1e-9
        assert abs(float(pure_snapshot['score_margin']) - float(db_snapshot['score_margin'])) < 1e-9
        assert abs(float(pure_snapshot['winner_share']) - float(db_snapshot['winner_share'])) < 1e-9
        assert len(pure_snapshot['ranked_roles']) == len(db_snapshot['ranked_roles'])
        assert pure_snapshot['ranked_roles'][0]['slug'] == db_snapshot['ranked_roles'][0]['slug']

    def test_run_single_sample_returns_consistent_outcome(self):
        questions = [
            {
                'id': question.id,
                'display_order': question.display_order,
                'item_group': question.item_group,
                'discriminates_between': list(question.discriminates_between or []),
                'agree_dimension_signals': dict(question.agree_dimension_signals or {}),
                'disagree_dimension_signals': dict(question.disagree_dimension_signals or {}),
                'trait_positive_dimension': question.trait_positive_dimension,
            }
            for question in Question.objects.filter(stage=Question.Stage.ROLE, is_active=True).order_by('display_order', 'id')
        ]
        fixed_answers = list((LIKERT_VALUES * 10)[: len(questions)])
        catalog = CatalogContext(
            questions=questions,
            active_role_slugs=list(self.active_role_slugs),
            role_names=self.role_names,
            core_target=self.core_target,
        )
        result = run_single_sample(0, catalog, [], fixed_answers)
        assert result['answered_role_questions'] >= self.core_target
        assert result['resolution_status'] in {'resolved', 'low_confidence', 'unknown'}
        assert result['best_fit_role'] is None or result['best_fit_role'] in self.active_role_slugs

    def test_aggregate_results_shape(self):
        questions = []
        results = [
            {
                'sample_index': 0,
                'phase': 'recommendation_ready',
                'status': 'completed',
                'resolution_status': 'resolved',
                'best_fit_role': 'backend-developer',
                'top_ranked_role': 'backend-developer',
                'answered_core_questions': 46,
                'answered_tie_break_questions': 0,
                'answered_role_questions': 46,
                'confidence': 0.5,
                'margin_share': 0.3,
                'score_margin': 4.0,
                'winner_share': 0.6,
            },
        ]
        summary = aggregate_results(
            results,
            catalog=CatalogContext(
                questions=questions,
                active_role_slugs=list(self.active_role_slugs),
                role_names=self.role_names,
                core_target=self.core_target,
            ),
            config=SimulationConfig(
                samples=1,
                seed=42,
                likert_weights={-2: 0.2, -1: 0.2, 0: 0.2, 1: 0.2, 2: 0.2},
            ),
        )
        assert summary['resolved_count'] == 1
        assert summary['resolved_rate'] == 1.0
        assert summary['resolved_roles']['backend-developer'] == 1
        assert 'worst_case_95pct_margin_of_error' in summary
        questions.clear()
