from django.urls import include, path

from . import views


urlpatterns = [
    path('health/', views.health_check, name='health-check'),
    path('accounts/', include('accounts.urls')),
    path('catalog/', include('roadmaps.urls')),
    path('assessment-sessions/', include('assessments.urls')),
]
