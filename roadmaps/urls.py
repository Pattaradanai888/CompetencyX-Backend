from django.urls import path

from .views import RoleListAPIView, RoleTopicListAPIView


urlpatterns = [
    path('roles/', RoleListAPIView.as_view(), name='role-list'),
    path('roles/<slug:role_slug>/topics/', RoleTopicListAPIView.as_view(), name='role-topic-list'),
]
