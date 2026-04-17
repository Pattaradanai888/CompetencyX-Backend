from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import generics

from .models import RoadmapTopic, Role
from .serializers import RoadmapTopicSerializer, RoleSerializer


class RoleListAPIView(generics.ListAPIView):
    queryset = Role.objects.filter(is_active=True)
    serializer_class = RoleSerializer

    @extend_schema(
        operation_id='listCatalogRoles',
        summary='List active roles',
        tags=['Catalog'],
        responses={
            200: OpenApiResponse(
                response=RoleSerializer(many=True),
                description='Active roles available for onboarding and preference selection.',
                examples=[
                    OpenApiExample(
                        'Role list',
                        value=[
                            {
                                'id': 1,
                                'slug': 'backend-engineer',
                                'name': 'Backend Engineer',
                                'description': 'Builds APIs and backend services.',
                            },
                            {
                                'id': 2,
                                'slug': 'frontend-engineer',
                                'name': 'Frontend Engineer',
                                'description': 'Builds web user interfaces.',
                            },
                        ],
                        response_only=True,
                    ),
                ],
            ),
        },
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class RoleTopicListAPIView(generics.ListAPIView):
    serializer_class = RoadmapTopicSerializer

    @extend_schema(
        operation_id='listRoleTopics',
        summary='List topics for a role',
        tags=['Catalog'],
        parameters=[
            OpenApiParameter(
                name='role_slug',
                type=str,
                location=OpenApiParameter.PATH,
                description='Slug of the active role to inspect.',
            ),
        ],
        responses={
            200: OpenApiResponse(
                response=RoadmapTopicSerializer(many=True),
                description='Ordered roadmap topics for the selected role.',
                examples=[
                    OpenApiExample(
                        'Role topics',
                        value=[
                            {
                                'id': 11,
                                'slug': 'http',
                                'title': 'HTTP Fundamentals',
                                'description': 'Core HTTP concepts for API work.',
                                'difficulty': 'beginner',
                                'display_order': 1,
                                'parent_id': None,
                                'prerequisites': [],
                            },
                            {
                                'id': 12,
                                'slug': 'databases',
                                'title': 'Databases',
                                'description': 'Relational data modeling and SQL.',
                                'difficulty': 'beginner',
                                'display_order': 2,
                                'parent_id': None,
                                'prerequisites': [
                                    {
                                        'topic_id': 11,
                                        'required_mastery_threshold': 0.7,
                                        'dependency_weight': 1.0,
                                    }
                                ],
                            },
                        ],
                        response_only=True,
                    ),
                ],
            ),
            404: OpenApiResponse(description='Role slug was not found or is inactive.'),
        },
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        role = get_object_or_404(Role, slug=self.kwargs['role_slug'], is_active=True)
        return RoadmapTopic.objects.filter(role=role, is_active=True).prefetch_related('prerequisites').order_by('display_order', 'id')
