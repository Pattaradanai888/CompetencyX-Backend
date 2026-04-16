from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.response import Response

from roadmaps.models import Role

from .models import AssessmentSession
from .serializers import (
    AnswerSubmitSerializer,
    AssessmentHistorySerializer,
    AssessmentResultSerializer,
    AssessmentSessionSerializer,
    SessionCreateSerializer,
)
from .services import AssessmentFlowError, create_assessment_session, submit_answer


class AssessmentSessionCreateAPIView(generics.GenericAPIView):
    serializer_class = SessionCreateSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        selected_role = None
        if serializer.validated_data.get('selected_role_slug'):
            selected_role = get_object_or_404(
                Role,
                slug=serializer.validated_data['selected_role_slug'],
                is_active=True,
            )
        session = create_assessment_session(
            selected_role=selected_role,
            profile=serializer.validated_data.get('profile', {}),
        )
        return Response(
            AssessmentSessionSerializer(session).data,
            status=status.HTTP_201_CREATED,
        )


class AssessmentSessionDetailAPIView(generics.RetrieveAPIView):
    queryset = AssessmentSession.objects.select_related(
        'selected_role',
        'inferred_role',
    ).prefetch_related(
        'mastery_scores__topic',
        'recommendations__role',
        'recommendations__topic',
    )
    serializer_class = AssessmentSessionSerializer


class AssessmentSessionResultAPIView(generics.RetrieveAPIView):
    queryset = AssessmentSession.objects.select_related(
        'selected_role',
        'inferred_role',
    ).prefetch_related(
        'answers__question__topic',
        'answers__selected_option',
        'mastery_scores__topic',
        'recommendations__role',
        'recommendations__topic',
    )
    serializer_class = AssessmentResultSerializer


class AssessmentSessionHistoryAPIView(generics.RetrieveAPIView):
    queryset = AssessmentSession.objects.prefetch_related(
        'answers__question__topic',
        'answers__selected_option',
        'recommendations__role',
        'recommendations__topic',
    )
    serializer_class = AssessmentHistorySerializer


class AssessmentAnswerSubmitAPIView(generics.GenericAPIView):
    serializer_class = AnswerSubmitSerializer

    def post(self, request, pk, *args, **kwargs):
        session = get_object_or_404(
            AssessmentSession.objects.select_related('selected_role', 'inferred_role'),
            pk=pk,
        )
        serializer = self.get_serializer(data=request.data, context={'session': session})
        serializer.is_valid(raise_exception=True)
        try:
            submit_answer(
                session=session,
                question=serializer.validated_data['question'],
                option=serializer.validated_data['option'],
                response_time_ms=serializer.validated_data.get('response_time_ms'),
                confidence_indicator=serializer.validated_data.get('confidence_indicator', ''),
            )
        except AssessmentFlowError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        session.refresh_from_db()
        return Response(AssessmentSessionSerializer(session).data, status=status.HTTP_200_OK)
