from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Role
from .serializers import RoadmapTopicSerializer, RoleSerializer


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
