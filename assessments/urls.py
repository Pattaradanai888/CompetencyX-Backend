from django.urls import path

from .views import (
    AssessmentAnswerSubmitAPIView,
    AssessmentSessionCreateAPIView,
    AssessmentSessionDetailAPIView,
    AssessmentSessionHistoryAPIView,
    AssessmentSessionResultAPIView,
)


urlpatterns = [
    path('', AssessmentSessionCreateAPIView.as_view(), name='assessment-session-create'),
    path('<uuid:pk>/', AssessmentSessionDetailAPIView.as_view(), name='assessment-session-detail'),
    path('<uuid:pk>/results/', AssessmentSessionResultAPIView.as_view(), name='assessment-session-results'),
    path('<uuid:pk>/history/', AssessmentSessionHistoryAPIView.as_view(), name='assessment-session-history'),
    path('<uuid:pk>/answers/', AssessmentAnswerSubmitAPIView.as_view(), name='assessment-answer-submit'),
]
