"""The Skill Assessment is built from authored Assessable Topic Sets.

These cover what ADR-0003 decided: the assessable unit is authored for the role
rather than read off the imported graph, a role whose sets are not written yet
still gets a usable assessment, and coverage of the graph is a backlog rather
than a gate.
"""

import shutil
import tempfile
import textwrap
from pathlib import Path

import pytest
from django.core.management import CommandError, call_command
from django.test import TestCase

from assessments.management.commands.validate_topic_set_catalog import build_topic_set_report
from assessments.models import AssessableTopicSet, SkillAssessmentQuestion
from assessments.services import assessable_topic_set_service
from assessments.services.assessable_topic_set_service import (
    build_set_key,
    load_assessable_topic_sets,
    select_assessable_topic_sets,
    sync_assessable_topic_sets,
)
from assessments.services.skill_assessment_service import list_skill_assessment_dimensions, list_skill_assessment_questions
from assessments.services.topic_skill_assessment_service import (
    TOPIC_TARGET_MAX,
    build_topic_targets,
    select_assessable_units,
    sync_topic_skill_assessment_catalog,
)
from roadmaps.models import ExternalRoadmapEdge, ExternalRoadmapNode, Role


BACKEND_SETS = """
role_slug: backend-developer
sets:
  - key: internet-and-web-protocols
    title: Internet and web protocols
    title_th: อินเทอร์เน็ตและโปรโตคอลเว็บ
    nodes: [http, https]
  - key: data-storage
    title: Data storage
    title_th: การจัดเก็บข้อมูล
    nodes: [databases]
"""


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


class TopicSetContentTestCase(TestCase):
    """Authored content lives in a throwaway directory, not in the repository's."""

    def setUp(self):
        self.content_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.content_dir, True)
        original = assessable_topic_set_service.TOPIC_SET_CONTENT_DIR
        assessable_topic_set_service.TOPIC_SET_CONTENT_DIR = self.content_dir
        self.addCleanup(setattr, assessable_topic_set_service, 'TOPIC_SET_CONTENT_DIR', original)

    def write_sets(self, role_slug: str, body: str) -> Path:
        path = self.content_dir / f'{role_slug}.yaml'
        path.write_text(textwrap.dedent(body).lstrip(), encoding='utf-8')
        return path


class AssessableTopicSetSyncTests(TopicSetContentTestCase):
    def setUp(self):
        super().setUp()
        self.backend = Role.objects.create(slug='backend-developer', name='Backend Developer')
        self.http = _node(self.backend, 'b1', 'http', 'HTTP', 1)
        self.https = _node(self.backend, 'b2', 'https', 'HTTPS', 2)
        self.databases = _node(self.backend, 'b3', 'databases', 'Databases', 3)
        self.caching = _node(self.backend, 'b4', 'caching', 'Caching', 4)
        ExternalRoadmapEdge.objects.create(role=self.backend, source_node=self.http, target_node=self.https)
        ExternalRoadmapEdge.objects.create(role=self.backend, source_node=self.https, target_node=self.databases)

    def test_a_set_carries_its_key_role_wording_order_and_nodes(self):
        self.write_sets('backend-developer', BACKEND_SETS)

        sync_assessable_topic_sets()

        topic_set = AssessableTopicSet.objects.get(set_key='backend-developer--internet-and-web-protocols')
        self.assertEqual(topic_set.role, self.backend)
        self.assertEqual(topic_set.title, 'Internet and web protocols')
        self.assertEqual(topic_set.title_th, 'อินเทอร์เน็ตและโปรโตคอลเว็บ')
        self.assertEqual(topic_set.display_order, 1)
        self.assertEqual({node.slug for node in topic_set.nodes.all()}, {'http', 'https'})

    def test_sync_is_idempotent(self):
        self.write_sets('backend-developer', BACKEND_SETS)

        first = sync_assessable_topic_sets()
        second = sync_assessable_topic_sets()

        self.assertEqual(first, second)
        self.assertEqual(AssessableTopicSet.objects.count(), 2)
        self.assertEqual(AssessableTopicSet.objects.filter(is_active=True).count(), 2)

    def test_a_set_that_leaves_the_catalog_is_deactivated_rather_than_deleted(self):
        # Answers are recorded against the set key, so deleting the set would
        # make answers already given uninterpretable.
        self.write_sets('backend-developer', BACKEND_SETS)
        sync_assessable_topic_sets()

        self.write_sets(
            'backend-developer',
            """
            role_slug: backend-developer
            sets:
              - key: data-storage
                title: Data storage
                title_th: การจัดเก็บข้อมูล
                nodes: [databases]
            """,
        )
        sync_assessable_topic_sets()

        retired = AssessableTopicSet.objects.get(set_key='backend-developer--internet-and-web-protocols')
        self.assertFalse(retired.is_active)
        self.assertTrue(AssessableTopicSet.objects.get(set_key='backend-developer--data-storage').is_active)

    def test_authoring_nothing_at_all_does_not_retire_the_catalog(self):
        # A deploy without the content directory would otherwise deactivate
        # every set and drop every role back to its derived topics.
        self.write_sets('backend-developer', BACKEND_SETS)
        sync_assessable_topic_sets()

        for path in self.content_dir.glob('*.yaml'):
            path.unlink()
        sync_assessable_topic_sets()

        self.assertEqual(AssessableTopicSet.objects.filter(is_active=True).count(), 2)

    def test_a_set_for_a_role_that_is_not_in_the_catalog_is_skipped(self):
        self.write_sets(
            'zz-unknown',
            """
            role_slug: zz-unknown
            sets:
              - key: anything
                title: Anything
                nodes: []
            """,
        )

        self.assertEqual(sync_assessable_topic_sets(), {})

    def test_duplicate_keys_are_rejected(self):
        self.write_sets(
            'backend-developer',
            """
            role_slug: backend-developer
            sets:
              - key: data-storage
                title: Data storage
                nodes: [databases]
              - key: data-storage
                title: Data storage again
                nodes: [caching]
            """,
        )

        with pytest.raises(ValueError, match='defined more than once'):
            load_assessable_topic_sets()

    def test_a_set_is_one_unit_whose_prerequisites_exclude_its_own_nodes(self):
        # http -> https lives inside the first set, so it is not a prerequisite
        # of the set; https -> databases crosses sets, so it is.
        self.write_sets('backend-developer', BACKEND_SETS)
        sync_assessable_topic_sets()

        units = {unit['slug']: unit for unit in select_assessable_topic_sets(self.backend)}

        self.assertEqual(units['internet-and-web-protocols']['prerequisite_titles'], [])
        self.assertEqual(units['data-storage']['prerequisite_titles'], ['HTTPS'])

    def test_an_item_is_keyed_by_the_stable_set_key(self):
        self.write_sets('backend-developer', BACKEND_SETS)
        sync_assessable_topic_sets()
        sync_topic_skill_assessment_catalog()

        served = {question['id'] for question in list_skill_assessment_questions('backend-developer')}

        self.assertEqual(
            served,
            {build_set_key('backend-developer', 'internet-and-web-protocols'), build_set_key('backend-developer', 'data-storage')},
        )

    def test_the_catalog_serves_the_authored_sets_for_a_role_that_has_them(self):
        self.write_sets('backend-developer', BACKEND_SETS)
        sync_assessable_topic_sets()
        sync_topic_skill_assessment_catalog()

        questions = list_skill_assessment_questions('backend-developer')
        dimensions = list_skill_assessment_dimensions('backend-developer')

        self.assertEqual([question['topic_title'] for question in questions], ['Internet and web protocols', 'Data storage'])
        self.assertEqual([dimension['label'] for dimension in dimensions], ['Internet and web protocols', 'Data storage'])
        self.assertIn('Internet and web protocols', questions[0]['prompt'])
        self.assertIn('อินเทอร์เน็ตและโปรโตคอลเว็บ', questions[0]['translations']['th']['prompt'])

    def test_a_set_without_reviewed_thai_wording_is_served_without_a_thai_prompt(self):
        self.write_sets(
            'backend-developer',
            """
            role_slug: backend-developer
            sets:
              - key: data-storage
                title: Data storage
                nodes: [databases]
            """,
        )
        sync_assessable_topic_sets()
        sync_topic_skill_assessment_catalog()

        translations = list_skill_assessment_questions('backend-developer')[0]['translations']

        self.assertEqual(set(translations), {'en'})

    def test_the_readiness_target_counts_dependent_sets_not_dependent_titles(self):
        # http -> https and https -> databases both leave the first set, but
        # they land in one other set, so the first set has one dependent.
        self.write_sets('backend-developer', BACKEND_SETS)
        sync_assessable_topic_sets()

        targets = build_topic_targets(self.backend)

        self.assertAlmostEqual(targets['internet-and-web-protocols'], 0.7)
        self.assertLess(targets['internet-and-web-protocols'], TOPIC_TARGET_MAX)
        self.assertAlmostEqual(targets['data-storage'], 0.6)

    def test_a_role_without_authored_sets_keeps_the_items_derived_from_its_roadmap(self):
        sync_topic_skill_assessment_catalog()

        titles = [question['topic_title'] for question in list_skill_assessment_questions('backend-developer')]

        self.assertEqual(titles, ['HTTP', 'HTTPS', 'Databases', 'Caching'])

    def test_authored_sets_win_over_the_derived_topics(self):
        self.write_sets('backend-developer', BACKEND_SETS)
        sync_assessable_topic_sets()

        self.assertEqual(
            [unit['title'] for unit in select_assessable_units(self.backend)],
            ['Internet and web protocols', 'Data storage'],
        )

    def test_a_retired_set_stops_being_asked_about(self):
        self.write_sets('backend-developer', BACKEND_SETS)
        sync_assessable_topic_sets()
        sync_topic_skill_assessment_catalog()

        AssessableTopicSet.objects.filter(set_key='backend-developer--data-storage').update(is_active=False)
        sync_topic_skill_assessment_catalog()

        served = [question['topic_title'] for question in list_skill_assessment_questions('backend-developer')]
        self.assertEqual(served, ['Internet and web protocols'])
        self.assertFalse(SkillAssessmentQuestion.objects.get(question_id='backend-developer--data-storage').is_active)


class TopicSetValidationTests(TopicSetContentTestCase):
    def setUp(self):
        super().setUp()
        self.backend = Role.objects.create(slug='backend-developer', name='Backend Developer')
        Role.objects.create(slug='ux-designer', name='UX Designer')
        _node(self.backend, 'b1', 'http', 'HTTP', 1)
        _node(self.backend, 'b2', 'databases', 'Databases', 2)
        _node(self.backend, 'b3', 'caching', 'Caching', 3)

    def test_roles_with_no_sets_are_reported(self):
        self.write_sets(
            'backend-developer',
            """
            role_slug: backend-developer
            sets:
              - key: data-storage
                title: Data storage
                title_th: การจัดเก็บข้อมูล
                nodes: [databases]
            """,
        )

        self.assertEqual(build_topic_set_report()['roles_without_sets'], ['ux-designer'])

    def test_sets_pointing_at_nodes_that_do_not_exist_are_reported(self):
        self.write_sets(
            'backend-developer',
            """
            role_slug: backend-developer
            sets:
              - key: data-storage
                title: Data storage
                title_th: การจัดเก็บข้อมูล
                nodes: [databases, nowhere]
            """,
        )

        self.assertEqual(build_topic_set_report()['unknown_node_slugs'], [('backend-developer--data-storage', ['nowhere'])])

    def test_sets_missing_reviewed_thai_wording_are_reported(self):
        self.write_sets(
            'backend-developer',
            """
            role_slug: backend-developer
            sets:
              - key: data-storage
                title: Data storage
                nodes: [databases]
            """,
        )

        self.assertEqual(build_topic_set_report()['sets_missing_thai'], ['backend-developer--data-storage'])

    def test_nodes_belonging_to_no_set_are_a_backlog_and_do_not_fail_the_run(self):
        self.write_sets(
            'backend-developer',
            """
            role_slug: backend-developer
            sets:
              - key: data-storage
                title: Data storage
                title_th: การจัดเก็บข้อมูล
                nodes: [databases]
              - key: interfaces
                title: Interfaces
                title_th: อินเทอร์เฟซ
                nodes: [http]
            """,
        )

        report = build_topic_set_report()

        self.assertEqual(report['uncovered_node_counts'], [('backend-developer', 1)])
        self.assertEqual(report['uncovered_node_total'], 1)
        self.assertEqual(report['unknown_node_slugs'], [])

    def test_uncovered_nodes_alone_do_not_fail_even_under_strict(self):
        self.write_sets(
            'backend-developer',
            """
            role_slug: backend-developer
            sets:
              - key: data-storage
                title: Data storage
                title_th: การจัดเก็บข้อมูล
                nodes: [databases]
            """,
        )
        Role.objects.filter(slug='ux-designer').update(is_active=False)

        call_command('validate_topic_set_catalog', '--strict')

    def test_the_command_reports_without_failing_and_fails_only_under_strict(self):
        self.write_sets(
            'backend-developer',
            """
            role_slug: backend-developer
            sets:
              - key: data-storage
                title: Data storage
                nodes: [databases, nowhere]
            """,
        )

        call_command('validate_topic_set_catalog')

        with pytest.raises(CommandError):
            call_command('validate_topic_set_catalog', '--strict')
