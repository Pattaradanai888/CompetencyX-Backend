"""Views for the catalog of roles and their roadmaps."""

import hashlib

from django.db.models import Count, Max
from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .external_roadmap import build_external_roadmap_topics, build_external_source_meta
from .models import ExternalRoadmapEdge, ExternalRoadmapNode, RoadmapTopic, Role, TopicPrerequisite
from .serializers import RoadmapTopicSerializer, RoleRoadmapSerializer, RoleSerializer


# The full roadmap is master data that changes only on import, so it is served
# cacheable with validators rather than paginated (ADR-0003).
ROADMAP_CACHE_CONTROL = 'public, max-age=3600'


def build_role_roadmap_etag(role) -> str:
    """A validator over everything the roadmap response carries.

    Built from row counts and the latest ``updated_at`` of each contributing
    table, so a re-import that rewrites the graph moves the validator and a
    stale response is not served.
    """
    node_stats = ExternalRoadmapNode.objects.filter(role=role).aggregate(latest=Max('updated_at'), total=Count('id'))
    # Edges and curated prerequisite rows carry no timestamps; the highest id
    # stands in, and moves whenever an import rewrites the rows.
    edge_stats = ExternalRoadmapEdge.objects.filter(role=role).aggregate(latest=Max('id'), total=Count('id'))
    topic_stats = RoadmapTopic.objects.filter(role=role, is_active=True).aggregate(latest=Max('updated_at'), total=Count('id'))
    prerequisite_stats = TopicPrerequisite.objects.filter(topic__role=role).aggregate(latest=Max('id'), total=Count('id'))
    digest = hashlib.md5(  # noqa: S324 - an ETag is a change detector, not a secret
        repr(
            (
                role.slug,
                role.updated_at,
                node_stats,
                edge_stats,
                topic_stats,
                prerequisite_stats,
                build_external_source_meta(role),
            ),
        ).encode(),
    )
    return f'W/"{digest.hexdigest()}"'


@extend_schema_view(
    list=extend_schema(
        operation_id='listCatalogRoles',
        summary='List active roles',
        tags=['Catalog'],
        responses={200: RoleSerializer(many=True)},
    ),
)
class RoleViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    queryset = Role.objects.filter(is_active=True)
    serializer_class = RoleSerializer
    lookup_field = 'slug'

    @extend_schema(
        operation_id='listRoleTopics',
        summary='List topics for a role',
        tags=['Catalog'],
        responses={
            200: RoadmapTopicSerializer(many=True),
            404: OpenApiResponse(description='Role slug was not found or is inactive.'),
        },
    )
    @action(
        detail=True,
        methods=['get'],
        serializer_class=RoadmapTopicSerializer,
        url_path='topics',
        url_name='topic-list',
    )
    def topics(self, request, *args, **kwargs):
        role = self.get_object()
        topics = role.topics.filter(is_active=True).prefetch_related('prerequisites').order_by('display_order', 'id')
        return Response(self.get_serializer(topics, many=True).data)

    @extend_schema(
        operation_id='retrieveRoleRoadmap',
        summary="Retrieve a role's full roadmap",
        description=(
            'Returns the role, its curated topics ordered by display order, the prerequisite edges '
            'between them, and the full external roadmap (roadmap.sh) imported into our own database. '
            '`external_topics` is empty for a role with no vendored snapshot.'
        ),
        tags=['Catalog'],
        responses={
            200: RoleRoadmapSerializer,
            404: OpenApiResponse(description='Role slug was not found or is inactive.'),
        },
        examples=[
            OpenApiExample(
                'Backend developer roadmap',
                value={
                    'role': {
                        'id': 1,
                        'slug': 'backend-developer',
                        'name': 'Backend Developer',
                        'description': 'Builds and operates server-side systems.',
                        'top_ka_codes': ['KA-SWE-01'],
                        'core_tasks': ['Design APIs'],
                        'swebok_source_version': 'v4',
                    },
                    'topics': [
                        {
                            'id': 10,
                            'slug': 'http',
                            'title': 'HTTP Fundamentals',
                            'topic_group': 'Web',
                            'description': 'Requests, responses, status codes.',
                            'difficulty': 'beginner',
                            'display_order': 1,
                            'parent_id': None,
                            'prerequisites': [],
                        },
                    ],
                    'prerequisite_edges': [
                        {
                            'topic': 'apis',
                            'prerequisite': 'http',
                            'required_mastery_threshold': 0.7,
                            'dependency_weight': 1.0,
                        },
                    ],
                },
                response_only=True,
            ),
        ],
    )
    @action(
        detail=True,
        methods=['get'],
        serializer_class=RoleRoadmapSerializer,
        url_path='roadmap',
        url_name='roadmap',
    )
    def roadmap(self, request, *args, **kwargs):
        role = self.get_object()
        etag = build_role_roadmap_etag(role)
        response = self._not_modified_if_matching(request, etag)
        if response is None:
            topics = list(
                role.topics.filter(is_active=True)
                .prefetch_related('prerequisites__prerequisite')
                .order_by('display_order', 'id'),
            )
            edges = [
                edge
                for topic in topics
                for edge in sorted(topic.prerequisites.all(), key=lambda item: item.prerequisite.slug)
            ]
            payload = {
                'role': role,
                'topics': topics,
                'prerequisite_edges': edges,
                'external_topics': build_external_roadmap_topics(role),
                'external_source': build_external_source_meta(role),
            }
            response = Response(self.get_serializer(payload).data)
        response['ETag'] = etag
        response['Cache-Control'] = ROADMAP_CACHE_CONTROL
        return response

    def _not_modified_if_matching(self, request, etag):
        """A 304 when the validator the client holds still matches."""
        header = request.META.get('HTTP_IF_NONE_MATCH')
        if not header:
            return None
        candidates = {candidate.strip() for candidate in header.split(',')}
        if etag in candidates or '*' in candidates:
            return Response(status=304)
        return None
