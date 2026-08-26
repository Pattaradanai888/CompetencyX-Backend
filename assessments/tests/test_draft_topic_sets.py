"""The drafting command for Assessable Topic Sets.

Authoring 15-20 sets per role across 26 roles by hand is not achievable, so a
command drafts the structure against the imported graph -- sets, wording
proposals, node mappings, and the nodes left unassigned -- and a human
reviews before anything goes live (ADR-0003).
"""

import shutil
import tempfile
from pathlib import Path

import pytest
import yaml
from django.core.management import CommandError, call_command
from django.test import TestCase

from assessments.models import AssessableTopicSet
from assessments.services import assessable_topic_set_service
from roadmaps.models import ExternalRoadmapEdge, ExternalRoadmapNode, Role


class DraftTopicSetsTests(TestCase):
    def setUp(self):
        self.backend = Role.objects.create(slug='backend-developer', name='Backend Developer')

        self.content_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.content_dir, True)
        original = assessable_topic_set_service.TOPIC_SET_CONTENT_DIR
        assessable_topic_set_service.TOPIC_SET_CONTENT_DIR = self.content_dir
        self.addCleanup(setattr, assessable_topic_set_service, 'TOPIC_SET_CONTENT_DIR', original)
        self.drafts_dir = self.content_dir / 'drafts'

        self.nodes = {}
        previous = None
        for index in range(1, 31):
            slug = f'topic-{index:02d}'
            node = ExternalRoadmapNode.objects.create(
                role=self.backend,
                external_id=f'b{index}',
                slug=slug,
                title=f'Topic {index:02d}',
                node_type=ExternalRoadmapNode.NodeType.TOPIC,
                display_order=index,
                source='roadmap.sh',
            )
            self.nodes[slug] = node
            # A chain of prerequisites plus standalone nodes, like a real graph.
            if previous is not None and index % 2 == 0:
                ExternalRoadmapEdge.objects.create(role=self.backend, source_node=previous, target_node=node)
            if index % 3 != 0:
                previous = node
        ExternalRoadmapNode.objects.create(
            role=self.backend,
            external_id='b-nav',
            slug='pick-a-language',
            title='Pick a Language',
            node_type=ExternalRoadmapNode.NodeType.TOPIC,
            display_order=99,
            source='roadmap.sh',
        )

    def draft_path(self) -> Path:
        return self.drafts_dir / 'backend-developer.yaml'

    def run_draft(self, *args):
        call_command('draft_topic_sets', 'backend-developer', *args)

    def test_drafting_a_role_produces_a_reviewable_file_with_sets_and_mappings(self):
        self.run_draft()

        draft = yaml.safe_load(self.draft_path().read_text(encoding='utf-8'))
        self.assertEqual(draft['role_slug'], 'backend-developer')
        self.assertEqual(draft['status'], 'draft')
        sets = draft['sets']
        self.assertGreaterEqual(len(sets), 1)
        self.assertTrue(all(set_['key'] and set_['title'] for set_ in sets))
        self.assertTrue(all('title_th' in set_ for set_ in sets))
        self.assertTrue(all(set_['review'] == {'status': 'draft'} for set_ in sets))
        assigned = {slug for set_ in sets for slug in set_['nodes']}
        self.assertGreaterEqual(len(assigned), 25)
        self.assertIn('topic-01', assigned)
        self.assertNotIn('pick-a-language', assigned)

    def test_the_draft_records_which_nodes_were_left_unassigned(self):
        self.run_draft()

        draft = yaml.safe_load(self.draft_path().read_text(encoding='utf-8'))
        unassigned_slugs = {entry['slug'] for entry in draft['unassigned']}
        self.assertEqual(unassigned_slugs, {'pick-a-language'})
        self.assertEqual(draft['counts']['unassigned'], 1)

    def test_drafting_never_activates_sets_or_touches_the_database(self):
        self.run_draft()

        self.assertEqual(AssessableTopicSet.objects.count(), 0)

    def test_redrafting_does_not_overwrite_an_existing_draft_without_force(self):
        self.run_draft()
        original = self.draft_path().read_text(encoding='utf-8')
        self.draft_path().write_text(original + '\n# reviewed notes\n', encoding='utf-8')

        with pytest.raises(CommandError):
            self.run_draft()
        self.assertIn('# reviewed notes', self.draft_path().read_text(encoding='utf-8'))

        self.run_draft('--force')
        self.assertNotIn('# reviewed notes', self.draft_path().read_text(encoding='utf-8'))

    def test_drafting_does_not_overwrite_reviewed_content(self):
        reviewed_path = self.content_dir / 'backend-developer.yaml'
        reviewed_path.write_text('role_slug: backend-developer\nsets: []\n', encoding='utf-8')

        self.run_draft()

        self.assertEqual(reviewed_path.read_text(encoding='utf-8'), 'role_slug: backend-developer\nsets: []\n')
        self.assertTrue(self.draft_path().exists())

    def test_drafting_a_role_without_a_roadmap_is_an_error(self):
        Role.objects.create(slug='no-roadmap', name='No Roadmap')

        with pytest.raises(CommandError):
            call_command('draft_topic_sets', 'no-roadmap')

    def test_drafting_an_unknown_role_is_an_error(self):
        with pytest.raises(CommandError):
            call_command('draft_topic_sets', 'no-such-role')
