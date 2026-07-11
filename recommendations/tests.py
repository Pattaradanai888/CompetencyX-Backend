"""Tests for the Q-learning recommendation service.

Two concerns:
- Pure unit tests verify the reward math and policy selection in isolation (no DB).
- DB-backed tests verify eligibility filtering, state-key bucketing, epsilon-greedy
  topic selection with exact Q-value updates, recommendation refresh orchestration,
  and survey-2 outcome feedback application.
"""

from types import SimpleNamespace
from unittest import mock

import pytest
from django.test import TestCase, override_settings

from assessments.models import AssessmentSession, Survey2Answer
from assessments.services.recommendation_service import (
    _build_recommendation_state_key,
    _calculate_recommendation_reward,
    _calculate_survey2_outcome_reward,
    _get_eligible_recommendation_topics,
    _get_recommendation_policy,
    apply_recommendation_feedback_from_survey2,
    build_recommendation_for_role,
    refresh_recommendations,
)
from recommendations.models import Recommendation, RecommendationQValue
from roadmaps.models import RoadmapTopic, Role, TopicPrerequisite


def _stub_topic(*, display_order, difficulty=RoadmapTopic.Difficulty.BEGINNER):
    return SimpleNamespace(display_order=display_order, difficulty=difficulty, Difficulty=RoadmapTopic.Difficulty)


def test_survey2_outcome_reward_all_fives_clamps_to_one():
    assert _calculate_survey2_outcome_reward({'q1': 5, 'q2': 5, 'q3': 5}) == 1.0


def test_survey2_outcome_reward_all_ones_is_completion_reward_only():
    assert _calculate_survey2_outcome_reward({'q1': 1, 'q2': 1, 'q3': 1}) == pytest.approx(0.55)


def test_survey2_outcome_reward_mixed_answers_pay_spread_penalty():
    # avg=3 -> normalized 0.5, spread=(5-1)/4=1.0 -> penalty 0.1: 0.55 + 0.225 - 0.1
    assert _calculate_survey2_outcome_reward({'q1': 1, 'q2': 5}) == pytest.approx(0.675)


def test_survey2_outcome_reward_single_answer_has_no_spread_penalty():
    assert _calculate_survey2_outcome_reward({'q1': 3}) == pytest.approx(0.775)


def test_survey2_outcome_reward_clamps_upper_bound():
    # avg=9 -> normalized average clamps to 1.0 before the reward is computed.
    assert _calculate_survey2_outcome_reward({'q1': 9}) == 1.0


def test_survey2_outcome_reward_clamps_lower_bound():
    # Huge spread penalty (spread=10 -> penalty 1.0) drags the reward to the floor.
    assert _calculate_survey2_outcome_reward({'q1': 1, 'q2': 41}) == pytest.approx(0.0, abs=1e-9)


def test_recommendation_reward_beginner_first_topic_clamps_to_one():
    # 0.7 + 0.2 * 1.0 + 0.15 = 1.05 -> clamped to 1.0
    assert _calculate_recommendation_reward(_stub_topic(display_order=0)) == 1.0


def test_recommendation_reward_non_beginner_gets_smaller_difficulty_bonus():
    # 0.7 + 0.2 * (1 / 2) + 0.05 = 0.85
    topic = _stub_topic(display_order=1, difficulty=RoadmapTopic.Difficulty.INTERMEDIATE)
    assert _calculate_recommendation_reward(topic) == pytest.approx(0.85)


def test_recommendation_reward_negative_display_order_is_treated_as_zero():
    # max(-3, 0) = 0 -> order bonus 1.0: 0.7 + 0.2 + 0.05 = 0.95
    topic = _stub_topic(display_order=-3, difficulty=RoadmapTopic.Difficulty.INTERMEDIATE)
    assert _calculate_recommendation_reward(topic) == pytest.approx(0.95)


def test_recommendation_policy_q_learning_when_configured():
    with override_settings(ASSESSMENT_RECOMMENDATION_POLICY='q_learning'):
        assert _get_recommendation_policy() == Recommendation.PolicyType.Q_LEARNING


def test_recommendation_policy_falls_back_to_rule_based_for_unknown_values():
    with override_settings(ASSESSMENT_RECOMMENDATION_POLICY='bandit'):
        assert _get_recommendation_policy() == Recommendation.PolicyType.RULE_BASED
    with override_settings(ASSESSMENT_RECOMMENDATION_POLICY='rule_based'):
        assert _get_recommendation_policy() == Recommendation.PolicyType.RULE_BASED


Q_LEARNING_SETTINGS = {
    'ASSESSMENT_RECOMMENDATION_POLICY': 'q_learning',
    'ASSESSMENT_RECOMMENDATION_Q_EPSILON': 0.0,
    'ASSESSMENT_RECOMMENDATION_Q_ALPHA': 0.5,
    'ASSESSMENT_RECOMMENDATION_Q_GAMMA': 0.5,
}


class RecommendationServiceDbTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.role = Role.objects.create(slug='backend-developer', name='Backend Developer')
        cls.topic_http = RoadmapTopic.objects.create(role=cls.role, slug='http', title='HTTP Fundamentals', display_order=1)
        cls.topic_databases = RoadmapTopic.objects.create(role=cls.role, slug='databases', title='Databases', display_order=2)
        cls.topic_apis = RoadmapTopic.objects.create(role=cls.role, slug='apis', title='API Design', display_order=3)
        TopicPrerequisite.objects.create(topic=cls.topic_apis, prerequisite=cls.topic_http, required_mastery_threshold=0.7)

        cls.other_role = Role.objects.create(slug='qa-engineer', name='QA Engineer')
        cls.other_topic = RoadmapTopic.objects.create(role=cls.other_role, slug='test-design', title='Test Design', display_order=1)

        cls.gated_role = Role.objects.create(slug='frontend-developer', name='Frontend Developer')
        gated_topic = RoadmapTopic.objects.create(role=cls.gated_role, slug='react', title='React', display_order=1)
        TopicPrerequisite.objects.create(topic=gated_topic, prerequisite=cls.topic_http, required_mastery_threshold=0.7)

        cls.session = AssessmentSession.objects.create(
            phase=AssessmentSession.Phase.RECOMMENDATION_READY,
            preferred_role=cls.role,
            best_fit_role=cls.role,
            best_fit_confidence=0.5,
        )

    def _state_key(self, *, role=None, path_kind=Recommendation.PathKind.PREFERRED, mastery_overrides=None):
        return _build_recommendation_state_key(
            self.session,
            role=role or self.role,
            path_kind=path_kind,
            mastery_overrides=mastery_overrides,
        )

    def test_eligible_topics_exclude_prerequisite_gated_topic(self):
        eligible = _get_eligible_recommendation_topics(self.session, role=self.role)
        self.assertEqual([topic.id for topic in eligible], [self.topic_http.id, self.topic_databases.id])

    def test_state_key_confidence_bucket_boundaries(self):
        expectations = {0.0: 'confidence-0', 0.5: 'confidence-2', 1.0: 'confidence-4'}
        for confidence, expected_bucket in expectations.items():
            self.session.best_fit_confidence = confidence
            state_key = self._state_key()
            self.assertEqual(
                state_key,
                f'backend-developer:preferred:unknown:in_progress:{expected_bucket}:mastery-0:weak-3',
            )

    @override_settings(**Q_LEARNING_SETTINGS)
    def test_greedy_selection_on_empty_q_table_ties_break_by_display_order(self):
        recommendation = build_recommendation_for_role(self.session, role=self.role, path_kind=Recommendation.PathKind.PREFERRED)

        self.assertEqual(recommendation.topic, self.topic_http)
        self.assertEqual(recommendation.policy_type, Recommendation.PolicyType.Q_LEARNING)
        self.assertEqual(recommendation.state_key, self._state_key())
        self.assertEqual(recommendation.score, 1.0)

        q_row = RecommendationQValue.objects.get(state_key=recommendation.state_key, path_kind='preferred', role=self.role, topic=self.topic_http)
        # reward = 0.7 + 0.2 * (1 / 2) + 0.15 = 0.95; projected next Q = 0; q = 0 + 0.5 * 0.95
        self.assertAlmostEqual(q_row.q_value, 0.475)
        self.assertAlmostEqual(q_row.reward_total, 0.95)
        self.assertAlmostEqual(q_row.last_reward, 0.95)
        self.assertEqual(q_row.update_count, 1)

    @override_settings(**Q_LEARNING_SETTINGS)
    def test_greedy_selection_prefers_seeded_higher_q_topic(self):
        RecommendationQValue.objects.create(
            state_key=self._state_key(),
            path_kind=Recommendation.PathKind.PREFERRED,
            role=self.role,
            topic=self.topic_databases,
            q_value=0.9,
        )

        recommendation = build_recommendation_for_role(self.session, role=self.role, path_kind=Recommendation.PathKind.PREFERRED)

        self.assertEqual(recommendation.topic, self.topic_databases)
        q_row = RecommendationQValue.objects.get(state_key=recommendation.state_key, topic=self.topic_databases)
        self.assertGreater(q_row.q_value, 0.9)
        self.assertEqual(q_row.update_count, 1)

    @override_settings(**Q_LEARNING_SETTINGS)
    def test_projected_next_q_value_feeds_gamma_term_into_update(self):
        projected_state_key = self._state_key(mastery_overrides={self.topic_http.id: 0.7})
        self.assertNotEqual(projected_state_key, self._state_key())
        RecommendationQValue.objects.create(
            state_key=projected_state_key,
            path_kind=Recommendation.PathKind.PREFERRED,
            role=self.role,
            topic=self.topic_databases,
            q_value=0.8,
        )

        build_recommendation_for_role(self.session, role=self.role, path_kind=Recommendation.PathKind.PREFERRED)

        q_row = RecommendationQValue.objects.get(state_key=self._state_key(), topic=self.topic_http)
        # q = 0 + 0.5 * (0.95 + 0.5 * 0.8 - 0) = 0.675
        self.assertAlmostEqual(q_row.q_value, 0.675)

    @override_settings(**{**Q_LEARNING_SETTINGS, 'ASSESSMENT_RECOMMENDATION_Q_EPSILON': 1.0})
    def test_exploration_branch_uses_random_choice(self):
        with mock.patch('assessments.services.recommendation_service.random.choice', return_value=self.topic_databases) as mocked_choice:
            recommendation = build_recommendation_for_role(self.session, role=self.role, path_kind=Recommendation.PathKind.PREFERRED)

        mocked_choice.assert_called_once()
        self.assertEqual(recommendation.topic, self.topic_databases)
        self.assertTrue(RecommendationQValue.objects.filter(state_key=recommendation.state_key, topic=self.topic_databases).exists())

    @override_settings(ASSESSMENT_RECOMMENDATION_POLICY='rule_based')
    def test_refresh_skips_and_clears_when_phase_is_not_recommendation_ready(self):
        self.session.phase = AssessmentSession.Phase.ROLE_DISCOVERY
        Recommendation.objects.create(session=self.session, role=self.role, topic=self.topic_http, reason='stale')

        self.assertEqual(refresh_recommendations(self.session), [])
        self.assertFalse(Recommendation.objects.filter(session=self.session).exists())

    @override_settings(ASSESSMENT_RECOMMENDATION_POLICY='rule_based')
    def test_refresh_builds_preferred_and_best_fit_recommendations(self):
        self.session.best_fit_role = self.other_role

        recommendations = refresh_recommendations(self.session)

        self.assertEqual(len(recommendations), 2)
        preferred, best_fit = recommendations
        self.assertEqual((preferred.path_kind, preferred.role, preferred.topic), ('preferred', self.role, self.topic_http))
        self.assertEqual((best_fit.path_kind, best_fit.role, best_fit.topic), ('best_fit', self.other_role, self.other_topic))
        self.assertEqual(preferred.policy_type, Recommendation.PolicyType.RULE_BASED)
        self.assertEqual(preferred.score, 1.0)
        self.assertEqual(preferred.state_key, '')

    @override_settings(ASSESSMENT_RECOMMENDATION_POLICY='rule_based')
    def test_refresh_builds_single_recommendation_when_roles_match(self):
        recommendations = refresh_recommendations(self.session)

        self.assertEqual(len(recommendations), 1)
        self.assertEqual(recommendations[0].path_kind, Recommendation.PathKind.PREFERRED)
        self.assertEqual(recommendations[0].topic, self.topic_http)

    @override_settings(ASSESSMENT_RECOMMENDATION_POLICY='rule_based')
    def test_refresh_creates_topicless_rule_based_recommendation_when_nothing_is_eligible(self):
        self.session.preferred_role = self.gated_role
        self.session.best_fit_role = self.gated_role

        recommendations = refresh_recommendations(self.session)

        self.assertEqual(len(recommendations), 1)
        recommendation = recommendations[0]
        self.assertIsNone(recommendation.topic)
        self.assertEqual(recommendation.policy_type, Recommendation.PolicyType.RULE_BASED)
        self.assertEqual(recommendation.score, 0.0)
        self.assertEqual(recommendation.state_key, '')

    def _create_q_learning_recommendation(self, **overrides):
        fields = {
            'session': self.session,
            'role': self.role,
            'topic': self.topic_http,
            'reason': 'seeded',
            'path_kind': Recommendation.PathKind.PREFERRED,
            'policy_type': Recommendation.PolicyType.Q_LEARNING,
            'state_key': 'seeded-state',
        }
        fields.update(overrides)
        return Recommendation.objects.create(**fields)

    def _set_survey2(self, *, completed, answers):
        self.session.survey2_completed = completed
        self.session.survey2_answers.all().delete()
        Survey2Answer.objects.bulk_create(
            Survey2Answer(session=self.session, question_id=question_id, value=value)
            for question_id, value in answers.items()
        )

    def _complete_survey2(self, answers):
        self._set_survey2(completed=True, answers=answers)

    def test_feedback_returns_zero_without_completed_survey2_state(self):
        self._create_q_learning_recommendation()

        self.assertEqual(apply_recommendation_feedback_from_survey2(self.session), 0)

        self._set_survey2(completed=False, answers={'q1': 5})
        self.assertEqual(apply_recommendation_feedback_from_survey2(self.session), 0)

        self._complete_survey2({})
        self.assertEqual(apply_recommendation_feedback_from_survey2(self.session), 0)

    @override_settings(ASSESSMENT_RECOMMENDATION_Q_ALPHA=0.5)
    def test_feedback_applies_exact_q_update_and_is_idempotent(self):
        recommendation = self._create_q_learning_recommendation()
        self._complete_survey2({'q1': 5, 'q2': 5})

        self.assertEqual(apply_recommendation_feedback_from_survey2(self.session), 1)

        q_row = RecommendationQValue.objects.get(state_key='seeded-state', path_kind='preferred', role=self.role, topic=self.topic_http)
        # outcome reward = 1.0 (all fives); q = 0 + 0.5 * (1.0 - 0)
        self.assertAlmostEqual(q_row.q_value, 0.5)
        self.assertAlmostEqual(q_row.reward_total, 1.0)
        self.assertAlmostEqual(q_row.last_reward, 1.0)
        self.assertEqual(q_row.update_count, 1)

        recommendation.refresh_from_db()
        self.assertTrue(recommendation.feedback_reward_applied)
        self.assertIsNotNone(recommendation.feedback_reward_applied_at)

        self.assertEqual(apply_recommendation_feedback_from_survey2(self.session), 0)
        q_row.refresh_from_db()
        self.assertEqual(q_row.update_count, 1)

    def test_feedback_skips_rule_based_topicless_and_stateless_recommendations(self):
        self._create_q_learning_recommendation(policy_type=Recommendation.PolicyType.RULE_BASED, state_key='')
        self._create_q_learning_recommendation(topic=None)
        self._create_q_learning_recommendation(topic=self.topic_databases, state_key='')
        self._complete_survey2({'q1': 5})

        self.assertEqual(apply_recommendation_feedback_from_survey2(self.session), 0)
        self.assertFalse(RecommendationQValue.objects.exists())
        self.assertFalse(Recommendation.objects.filter(feedback_reward_applied=True).exists())
