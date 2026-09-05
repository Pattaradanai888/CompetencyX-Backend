"""Skill Assessment items are anchored to the chosen role's Assessable Topic Sets.

These cover the claims ADR-0002, ADR-0003 and ADR-0005 make: the instrument
differs by role, the recommendation follows from the answers, and a role whose
sets are not authored has no assessment at all -- nothing is read off its
imported roadmap, and nothing stands in.
"""

from django.core.management import call_command
from django.test import TestCase

from assessments.models import AssessableTopicSet, AssessmentSession, SkillAssessmentQuestion, SkillAssessmentRoleGuidance
from assessments.services.assessable_topic_set_service import build_set_key
from assessments.services.skill_assessment_service import (
    get_skill_assessment_catalog,
    get_skill_assessment_state,
    list_skill_assessment_questions,
    list_skill_assessment_role_guidance,
)
from assessments.services.topic_skill_assessment_service import (
    build_readiness_summary,
    build_topic_targets,
    get_topic_mastery,
    scale_value_to_mastery,
    select_assessable_units,
    sync_topic_skill_assessment_catalog,
)
from roadmaps.models import ExternalRoadmapEdge, ExternalRoadmapNode, Role


def _node(role, external_id, slug, title, order):
    return ExternalRoadmapNode.objects.create(
        role=role,
        external_id=external_id,
        slug=slug,
        title=title,
        node_type=ExternalRoadmapNode.NodeType.TOPIC,
        display_order=order,
        source='roadmap.sh',
    )


def _set(role, key, title, nodes, order):
    topic_set = AssessableTopicSet.objects.create(
        set_key=build_set_key(role.slug, key),
        key=key,
        role=role,
        title=title,
        node_slugs=[node.slug for node in nodes],
        display_order=order,
    )
    topic_set.nodes.set(nodes)
    return topic_set


class TopicSkillAssessmentTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.backend = Role.objects.create(slug='backend-developer', name='Backend Developer')
        cls.ux = Role.objects.create(slug='ux-designer', name='UX Designer')
        cls.unauthored = Role.objects.create(slug='blockchain-developer', name='Blockchain Developer')

        cls.http = _node(cls.backend, 'b1', 'http', 'HTTP Fundamentals', 1)
        cls.databases_topic = _node(cls.backend, 'b2', 'databases', 'Databases', 2)
        cls.caching = _node(cls.backend, 'b3', 'caching', 'Caching', 3)
        ExternalRoadmapEdge.objects.create(role=cls.backend, source_node=cls.http, target_node=cls.databases_topic)
        _set(cls.backend, 'http', 'HTTP Fundamentals', [cls.http], 1)
        _set(cls.backend, 'databases', 'Databases', [cls.databases_topic], 2)
        _set(cls.backend, 'caching', 'Caching', [cls.caching], 3)

        research = _node(cls.ux, 'u1', 'research', 'User Research', 1)
        prototyping = _node(cls.ux, 'u2', 'prototyping', 'Prototyping', 2)
        _set(cls.ux, 'research', 'User Research', [research], 1)
        _set(cls.ux, 'prototyping', 'Prototyping', [prototyping], 2)

        # A roadmap with no authored sets: there is content to read off it,
        # and none of it may become an item.
        _node(cls.unauthored, 'c1', 'solidity', 'Solidity', 1)

        sync_topic_skill_assessment_catalog()

    def _answers(self, role, **by_key):
        return {build_set_key(role.slug, key): value for key, value in by_key.items()}

    def test_each_role_is_asked_about_its_own_sets(self):
        backend_questions = list_skill_assessment_questions('backend-developer')
        ux_questions = list_skill_assessment_questions('ux-designer')

        backend_titles = {q['topic_title'] for q in backend_questions}
        ux_titles = {q['topic_title'] for q in ux_questions}

        self.assertEqual(backend_titles, {'HTTP Fundamentals', 'Databases', 'Caching'})
        self.assertEqual(ux_titles, {'User Research', 'Prototyping'})
        self.assertFalse(backend_titles & ux_titles)
        for question in backend_questions:
            self.assertIn(question['topic_title'], question['prompt'])

    def test_a_role_without_authored_sets_is_not_assessed_from_its_roadmap(self):
        # The items once derived from the imported graph are gone: that
        # derivation is what asked Cyber Security six questions against 301
        # nodes and never asked Backend Developer about Git (ADR-0003). The
        # role-independent items that then stood in are gone too (ADR-0005):
        # a role whose sets are not authored has nothing to be asked.
        self.assertEqual(select_assessable_units(self.unauthored), [])
        self.assertFalse(SkillAssessmentQuestion.objects.filter(role=self.unauthored).exists())

        self.assertEqual(list_skill_assessment_questions('blockchain-developer'), [])
        self.assertEqual(get_skill_assessment_catalog('blockchain-developer')['dimensions'], [])
        self.assertEqual(list_skill_assessment_questions(None), [])

    def test_ratings_become_per_topic_mastery(self):
        answers = self._answers(self.backend, http=5, databases=3, caching=1)

        mastery = get_topic_mastery(self.backend, answers)

        self.assertEqual(mastery['backend-developer--http'], 1.0)
        self.assertEqual(mastery['backend-developer--caching'], 0.0)
        self.assertAlmostEqual(mastery['backend-developer--databases'], 0.5)
        self.assertEqual(scale_value_to_mastery(99), 1.0)
        self.assertEqual(scale_value_to_mastery(None), 0.0)

    # How the answers order the suggestions -- prerequisite layer before
    # Self-placed Mastery, assessed gaps before unassessed sets, held topics
    # dropping out -- is asserted at the HTTP seam in
    # api/tests/test_topic_states_and_ordering.py, where a respondent observes
    # it (ADR-0003).

    def test_the_readiness_target_comes_from_the_role_s_own_roadmap(self):
        # HTTP Fundamentals unlocks Databases, so it has to be held more firmly
        # than a topic nothing depends on. The target is therefore a property of
        # this roadmap, not one number applied to every role (ADR-0002, ticket 006).
        targets = build_topic_targets(self.backend)

        self.assertGreater(targets['backend-developer--http'], targets['backend-developer--caching'])
        self.assertEqual(targets['backend-developer--caching'], targets['backend-developer--databases'])
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

        self.assertEqual(state['topic_mastery']['backend-developer--http'], 1.0)
        self.assertNotIn('backend-developer--http', {item['topic_slug'] for item in state['recommended_topics']})
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
