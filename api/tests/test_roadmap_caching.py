"""The full roadmap is master data: served with cache validators, not paginated.

Paging a 301-item numbered list does not make it usable, so the response is
made cacheable instead -- validators and a conditional request that answers
304 while the imported graph has not changed (ADR-0003).
"""

from django.urls import reverse
from rest_framework import status

from roadmaps.models import ExternalRoadmapNode

from .base import AssessmentFlowTestCase


class RoleRoadmapCachingTests(AssessmentFlowTestCase):
    def setUp(self):
        super().setUp()
        ExternalRoadmapNode.objects.create(
            role=self.backend_role,
            external_id='b1',
            slug='http',
            title='HTTP',
            node_type=ExternalRoadmapNode.NodeType.TOPIC,
            display_order=1,
            source='roadmap.sh',
        )

    def roadmap_url(self):
        return reverse('role-roadmap', kwargs={'slug': self.backend_role.slug})

    def test_the_full_roadmap_is_served_with_cache_validators(self):
        response = self.client.get(self.roadmap_url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response['ETag'])
        self.assertIn('public', response['Cache-Control'])
        self.assertTrue(response.json()['external_topics'])

    def test_a_conditional_request_answers_not_modified_while_the_graph_is_unchanged(self):
        first = self.client.get(self.roadmap_url())
        etag = first['ETag']

        second = self.client.get(self.roadmap_url(), HTTP_IF_NONE_MATCH=etag)

        self.assertEqual(second.status_code, status.HTTP_304_NOT_MODIFIED)
        self.assertEqual(second['ETag'], etag)
        self.assertEqual(second.content, b'')

    def test_re_importing_the_roadmap_changes_the_validator(self):
        etag = self.client.get(self.roadmap_url())['ETag']

        # A re-import rewrites the graph rows; the validator must move with them.
        node = ExternalRoadmapNode.objects.get(role=self.backend_role)
        node.title = 'HTTP and web fundamentals'
        node.save()

        third = self.client.get(self.roadmap_url(), HTTP_IF_NONE_MATCH=etag)

        self.assertEqual(third.status_code, status.HTTP_200_OK)
        self.assertNotEqual(third['ETag'], etag)
        self.assertEqual(third.json()['external_topics'][0]['title'], 'HTTP and web fundamentals')

    def test_each_role_has_its_own_validator(self):
        ExternalRoadmapNode.objects.create(
            role=self.qa_role,
            external_id='q1',
            slug='test-design-external',
            title='Test Design',
            node_type=ExternalRoadmapNode.NodeType.TOPIC,
            display_order=1,
            source='roadmap.sh',
        )

        backend_etag = self.client.get(self.roadmap_url())['ETag']
        qa_etag = self.client.get(reverse('role-roadmap', kwargs={'slug': self.qa_role.slug}))['ETag']

        self.assertNotEqual(backend_etag, qa_etag)
