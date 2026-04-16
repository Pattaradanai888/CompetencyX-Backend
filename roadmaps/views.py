from django.shortcuts import get_object_or_404
from rest_framework import generics

from .models import RoadmapTopic, Role
from .serializers import RoadmapTopicSerializer, RoleSerializer


class RoleListAPIView(generics.ListAPIView):
    queryset = Role.objects.filter(is_active=True)
    serializer_class = RoleSerializer


class RoleTopicListAPIView(generics.ListAPIView):
    serializer_class = RoadmapTopicSerializer

    def get_queryset(self):
        role = get_object_or_404(Role, slug=self.kwargs['role_slug'], is_active=True)
        return RoadmapTopic.objects.filter(role=role, is_active=True).prefetch_related('prerequisites').order_by('display_order', 'id')
