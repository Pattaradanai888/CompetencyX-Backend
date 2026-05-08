from django.urls import path

from .views import (
    AssessmentAnswerSubmitAPIView,
    AssessmentSurvey2SessionAPIView,
    AssessmentSessionCreateAPIView,
    AssessmentSessionDetailAPIView,
    AssessmentSessionHistoryAPIView,
    AssessmentSessionInsightsAPIView,
    AssessmentSessionResultAPIView,
)


urlpatterns = [
    path('', AssessmentSessionCreateAPIView.as_view(), name='assessment-session-create'),
    path('<uuid:pk>/', AssessmentSessionDetailAPIView.as_view(), name='assessment-session-detail'),
    path('<uuid:pk>/insights/', AssessmentSessionInsightsAPIView.as_view(), name='assessment-session-insights'),
    path('<uuid:pk>/results/', AssessmentSessionResultAPIView.as_view(), name='assessment-session-results'),
    path('<uuid:pk>/history/', AssessmentSessionHistoryAPIView.as_view(), name='assessment-session-history'),
    path('<uuid:pk>/answers/', AssessmentAnswerSubmitAPIView.as_view(), name='assessment-answer-submit'),
    path('<uuid:pk>/survey2/', AssessmentSurvey2SessionAPIView.as_view(), name='assessment-survey2-session'),
]
