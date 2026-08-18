"""Skill Assessment items are anchored to the chosen role's roadmap topics.

These cover the claims ADR-0002 makes: the instrument differs by role, the
recommendation follows from the answers, and a role without an imported
roadmap still gets a usable assessment.
"""

from django.core.management import call_command
from django.test import TestCase

from assessments.models import AssessmentSession, SkillAssessmentQuestion, SkillAssessmentRoleGuidance
from assessments.services.skill_assessment_service import (
    get_skill_assessment_catalog,
    get_skill_assessment_state,
    list_skill_assessment_questions,
    list_skill_assessment_role_guidance,
)
from assessments.services.topic_skill_assessment_service import (
    MAX_TOPIC_QUESTIONS_PER_ROLE,
    TOPIC_MASTERY_THRESHOLD,
    build_readiness_summary,
    build_topic_recommendations,
    build_topic_targets,
    get_topic_mastery,
    scale_value_to_mastery,
    select_assessable_topics,
    sync_topic_skill_assessment_catalog,
)
from roadmaps.models import ExternalRoadmapEdge, ExternalRoadmapNode, Role


def _node(role, external_id, slug, title, order, node_type=ExternalRoadmapNode.NodeType.TOPIC):  # noqa: PLR0913 - node identity plus its place in the graph
    return ExternalRoadmapNode.objects.create(
        role=role,
        external_id=external_id,
        slug=slug,
        title=title,
        node_type=node_type,
        display_order=order,
        source='roadmap.sh',
    )


class TopicSkillAssessmentTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.backend = Role.objects.create(slug='backend-developer', name='Backend Developer')
        cls.ux = Role.objects.create(slug='ux-designer', name='UX Designer')
        cls.uncovered = Role.objects.create(slug='blockchain-developer', name='Blockchain Developer')

        cls.http = _node(cls.backend, 'b1', 'http', 'HTTP Fundamentals', 1)
        cls.databases_topic = _node(cls.backend, 'b2', 'databases', 'Databases', 2)
        cls.caching = _node(cls.backend, 'b3', 'caching', 'Caching', 3)
        _node(cls.backend, 'b4', 'redis', 'Redis', 4, ExternalRoadmapNode.NodeType.SUBTOPIC)
        ExternalRoadmapEdge.objects.create(role=cls.backend, source_node=cls.http, target_node=cls.databases_topic)

        _node(cls.ux, 'u1', 'research', 'User Research', 1)
        _node(cls.ux, 'u2', 'prototyping', 'Prototyping', 2)

        sync_topic_skill_assessment_catalog()

    def _answers(self, role, **by_slug):
        questions = SkillAssessmentQuestion.objects.filter(role=role, is_active=True)
        return {q.question_id: by_slug[q.topic_slug] for q in questions if q.topic_slug in by_slug}

    def test_each_role_is_asked_about_its_own_topics(self):
        backend_questions = list_skill_assessment_questions('backend-developer')
        ux_questions = list_skill_assessment_questions('ux-designer')

        backend_titles = {q['topic_title'] for q in backend_questions}
        ux_titles = {q['topic_title'] for q in ux_questions}

        self.assertEqual(backend_titles, {'HTTP Fundamentals', 'Databases', 'Caching'})
        self.assertEqual(ux_titles, {'User Research', 'Prototyping'})
        self.assertFalse(backend_titles & ux_titles)
        for question in backend_questions:
            self.assertIn(question['topic_title'], question['prompt'])

    def test_subtopics_are_not_asked_about(self):
        # Subtopics are frequently interchangeable alternatives; asking about each
        # would balloon the questionnaire without telling us anything extra.
        titles = {q['topic_title'] for q in list_skill_assessment_questions('backend-developer')}
        self.assertNotIn('Redis', titles)

    def test_a_role_without_an_imported_roadmap_falls_back_to_the_shared_items(self):
        self.assertEqual(select_assessable_topics(self.uncovered), [])

        questions = list_skill_assessment_questions('blockchain-developer')

        self.assertTrue(questions)
        self.assertTrue(all(question['topic_slug'] == '' for question in questions))

    def test_the_question_count_is_capped(self):
        for index in range(MAX_TOPIC_QUESTIONS_PER_ROLE + 5):
            _node(self.ux, f'extra-{index}', f'extra-{index}', f'Extra {index}', 10 + index)

        sync_topic_skill_assessment_catalog()

        self.assertEqual(len(list_skill_assessment_questions('ux-designer')), MAX_TOPIC_QUESTIONS_PER_ROLE)

    def test_ratings_become_per_topic_mastery(self):
        answers = self._answers(self.backend, http=5, databases=3, caching=1)

        mastery = get_topic_mastery(self.backend, answers)

        self.assertEqual(mastery['http'], 1.0)
        self.assertEqual(mastery['caching'], 0.0)
        self.assertAlmostEqual(mastery['databases'], 0.5)
        self.assertEqual(scale_value_to_mastery(99), 1.0)
        self.assertEqual(scale_value_to_mastery(None), 0.0)

    def test_different_answers_on_the_same_role_recommend_different_topics(self):
        weak_on_caching = build_topic_recommendations(
            self.backend,
            self._answers(self.backend, http=5, databases=5, caching=1),
        )
        weak_on_http = build_topic_recommendations(
            self.backend,
            self._answers(self.backend, http=1, databases=5, caching=5),
        )

        self.assertEqual(weak_on_caching[0]['topic_slug'], 'caching')
        self.assertEqual(weak_on_http[0]['topic_slug'], 'http')
        self.assertNotEqual(weak_on_caching[0]['topic_slug'], weak_on_http[0]['topic_slug'])

    def test_mastered_topics_are_not_recommended(self):
        answers = self._answers(self.backend, http=5, databases=5, caching=1)

        recommended = build_topic_recommendations(self.backend, answers)

        slugs = {item['topic_slug'] for item in recommended}
        self.assertEqual(slugs, {'caching'})
        for item in recommended:
            self.assertLess(item['mastery'], TOPIC_MASTERY_THRESHOLD)

    def test_recommendations_carry_a_reason_naming_prerequisites(self):
        answers = self._answers(self.backend, http=5, databases=1, caching=5)

        recommended = build_topic_recommendations(self.backend, answers)

        self.assertEqual(recommended[0]['topic_slug'], 'databases')
        self.assertIn('HTTP Fundamentals', recommended[0]['reason'])

    def test_unanswered_topics_are_treated_as_not_yet_held(self):
        recommended = build_topic_recommendations(self.backend, {})

        self.assertEqual(
            [item['topic_slug'] for item in recommended],
            ['http', 'databases', 'caching'],
        )

    def test_the_readiness_target_comes_from_the_role_s_own_roadmap(self):
        # HTTP Fundamentals unlocks Databases, so it has to be held more firmly
        # than a topic nothing depends on. The target is therefore a property of
        # this roadmap, not one number applied to every role (ADR-0002, ticket 006).
        targets = build_topic_targets(self.backend)

        self.assertGreater(targets['http'], targets['caching'])
        self.assertEqual(targets['caching'], targets['databases'])
        self.assertLessEqual(max(targets.values()), 1.0)

    def test_the_readiness_target_differs_between_roles(self):
        backend_targets = build_topic_targets(self.backend)
        ux_targets = build_topic_targets(self.ux)

        self.assertNotEqual(sorted(backend_targets.values()), sorted(ux_targets.values()))

    def test_readiness_summary_reports_as_is_against_that_target(self):
        summary = build_readiness_summary(self.backend, self._answers(self.backend, http=5, databases=1, caching=1))

        self.assertEqual(summary['targets'], build_topic_targets(self.backend))
        self.assertAlmostEqual(summary['overall_mastery'], 1 / 3)
        self.assertGreater(summary['overall_target'], summary['overall_mastery'])

    def test_catalog_serves_the_role_its_own_items_and_dimensions(self):
        catalog = get_skill_assessment_catalog('ux-designer')

        self.assertEqual({q['topic_title'] for q in catalog['questions']}, {'User Research', 'Prototyping'})
        self.assertEqual({d['label'] for d in catalog['dimensions']}, {'User Research', 'Prototyping'})

    def test_session_state_reports_mastery_and_next_topics(self):
        session = AssessmentSession.objects.create(preferred_role=self.backend)
        answers = self._answers(self.backend, http=5, databases=1, caching=1)
        session.skill_assessment_answers.model.objects.bulk_create(
            [
                session.skill_assessment_answers.model(session=session, question_id=question_id, value=value)
                for question_id, value in answers.items()
            ],
        )

        state = get_skill_assessment_state(session)

        self.assertEqual(state['topic_mastery']['http'], 1.0)
        self.assertNotIn('http', {item['topic_slug'] for item in state['recommended_topics']})
        self.assertTrue(state['recommended_topics'])


class SkillAssessmentGuidanceCoverageTests(TestCase):
    """Every active role must carry its own guidance.

    Guidance used to exist for 6 of 26 roles and the other 20 fell through to
    generic text without anything saying so, which is how the gap stayed
    invisible. This test fails when a role is added without guidance.
    """

    @classmethod
    def setUpTestData(cls):
        call_command('sync_content')

    def test_every_active_role_has_its_own_guidance(self):
        covered = set(
            SkillAssessmentRoleGuidance.objects.filter(is_active=True, role__isnull=False).values_list('role__slug', flat=True),
        )
        active = set(Role.objects.filter(is_active=True).values_list('slug', flat=True))

        self.assertEqual(sorted(active - covered), [])

    def test_guidance_served_for_a_role_is_that_role_s_own(self):
        generic = list_skill_assessment_role_guidance(None)

        for slug in Role.objects.filter(is_active=True).values_list('slug', flat=True):
            role_guidance = list_skill_assessment_role_guidance(slug)
            self.assertTrue(role_guidance, slug)
            self.assertNotEqual(role_guidance, generic, slug)
