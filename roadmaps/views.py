from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .external_roadmap import build_external_roadmap_topics, build_external_source_meta
from .models import Role
from .serializers import RoadmapTopicSerializer, RoleRoadmapSerializer, RoleSerializer


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
        return Response(self.get_serializer(payload).data)
