from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, OpenApiResponse, extend_schema
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


SESSION_CREATE_REQUEST_EXAMPLE = {
    'preferred_role_slug': 'backend-engineer',
    'profile': {
        'education_level': 'student',
        'current_stage': 'beginner',
    },
}

SESSION_RESPONSE_EXAMPLE = {
    'id': '2b39d41d-8de9-4b9b-b2ef-2a278b3f3770',
    'status': 'in_progress',
    'phase': 'role_discovery',
    'best_fit_confidence': 0.0,
    'preferred_role': {
        'id': 1,
        'slug': 'backend-engineer',
        'name': 'Backend Engineer',
        'description': 'Builds APIs and backend services.',
    },
    'best_fit_role': None,
    'profile': {
        'education_level': 'student',
        'current_stage': 'beginner',
    },
    'started_at': '2026-04-17T04:00:00Z',
    'updated_at': '2026-04-17T04:00:00Z',
    'completed_at': None,
    'milestones': {
        'answered_role_questions': 0,
        'answered_skill_questions': 0,
    },
    'role_alignment_status': 'unknown',
    'guidance_summary': 'You want to pursue Backend Engineer. Answer the role-discovery questions to see how close your current fit is.',
    'current_question': {
        'id': 101,
        'code': 'role-primary-interest',
        'stage': 'role',
        'question_type': 'single_choice',
        'prompt': 'Which work sounds most interesting?',
        'help_text': '',
        'role': None,
        'topic': None,
        'difficulty': 1,
        'discrimination_score': 3.0,
        'options': [
            {
                'id': 201,
                'key': 'backend',
                'label': 'Designing APIs and backend services',
                'value': '',
                'display_order': 1,
            }
        ],
    },
}

ANSWER_REQUEST_EXAMPLE = {
    'question_id': 101,
    'option_id': 201,
    'response_time_ms': 4200,
    'confidence_indicator': 'high',
}

RESULT_RESPONSE_EXAMPLE = {
    'id': '2b39d41d-8de9-4b9b-b2ef-2a278b3f3770',
    'status': 'completed',
    'phase': 'recommendation_ready',
    'best_fit_confidence': 0.8,
    'preferred_role': {
        'id': 1,
        'slug': 'backend-engineer',
        'name': 'Backend Engineer',
        'description': 'Builds APIs and backend services.',
    },
    'best_fit_role': {
        'id': 1,
        'slug': 'backend-engineer',
        'name': 'Backend Engineer',
        'description': 'Builds APIs and backend services.',
    },
    'profile': {
        'education_level': 'student',
        'current_stage': 'beginner',
    },
    'started_at': '2026-04-17T04:00:00Z',
    'updated_at': '2026-04-17T04:05:00Z',
    'completed_at': '2026-04-17T04:05:00Z',
    'milestones': {
        'answered_role_questions': 2,
        'answered_skill_questions': 2,
    },
    'role_alignment_status': 'aligned',
    'guidance_summary': 'You are tracking well toward Backend Engineer. Focus next on Databases, HTTP Fundamentals.',
    'preferred_role_gap_topics': [
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
        }
    ],
    'mastery_scores': [
        {
            'topic_id': 11,
            'topic_slug': 'http',
            'topic_title': 'HTTP Fundamentals',
            'mastery_score': 1.0,
            'confidence_score': 0.5,
            'updated_at': '2026-04-17T04:05:00Z',
        }
    ],
    'preferred_path_recommendation': {
        'id': 301,
        'role_slug': 'backend-engineer',
        'topic_id': 12,
        'topic_slug': 'databases',
        'topic_title': 'Databases',
        'reason': 'Lowest-order topic with satisfied prerequisites and insufficient mastery.',
        'path_kind': 'preferred',
        'policy_type': 'rule_based',
        'score': 0.5,
        'created_at': '2026-04-17T04:05:00Z',
    },
    'best_fit_path_recommendation': None,
}

HISTORY_RESPONSE_EXAMPLE = {
    'id': '2b39d41d-8de9-4b9b-b2ef-2a278b3f3770',
    'phase': 'recommendation_ready',
    'status': 'completed',
    'answers': [
        {
            'id': 401,
            'question_id': 101,
            'question_code': 'role-primary-interest',
            'question_prompt': 'Which work sounds most interesting?',
            'question_stage': 'role',
            'topic_slug': None,
            'selected_option_id': 201,
            'selected_option_key': 'backend',
            'selected_option_label': 'Designing APIs and backend services',
            'response_time_ms': 4200,
            'confidence_indicator': 'high',
            'responded_at': '2026-04-17T04:01:00Z',
        }
    ],
    'recommendations': [
        {
            'id': 301,
            'role_slug': 'backend-engineer',
            'topic_id': 12,
            'topic_slug': 'databases',
            'topic_title': 'Databases',
            'reason': 'Lowest-order topic with satisfied prerequisites and insufficient mastery.',
            'path_kind': 'preferred',
            'policy_type': 'rule_based',
            'score': 0.5,
            'created_at': '2026-04-17T04:05:00Z',
        }
    ],
}


class AssessmentSessionCreateAPIView(generics.GenericAPIView):
    serializer_class = SessionCreateSerializer

    @extend_schema(
        operation_id='createAssessmentSession',
        summary='Create an assessment session',
        tags=['Assessment Sessions'],
        request=SessionCreateSerializer,
        responses={
            201: OpenApiResponse(
                response=AssessmentSessionSerializer,
                description='Assessment session created successfully.',
                examples=[
                    OpenApiExample('Create session request', value=SESSION_CREATE_REQUEST_EXAMPLE, request_only=True),
                    OpenApiExample('Create session response', value=SESSION_RESPONSE_EXAMPLE, response_only=True, status_codes=['201']),
                ],
            ),
            400: OpenApiResponse(description='Validation error, such as an unknown preferred role slug.'),
        },
    )
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        preferred_role = None
        if serializer.validated_data.get('preferred_role_slug'):
            preferred_role = get_object_or_404(
                Role,
                slug=serializer.validated_data['preferred_role_slug'],
                is_active=True,
            )
        session = create_assessment_session(
            preferred_role=preferred_role,
            profile=serializer.validated_data.get('profile', {}),
        )
        return Response(
            AssessmentSessionSerializer(session).data,
            status=status.HTTP_201_CREATED,
        )


class AssessmentSessionDetailAPIView(generics.RetrieveAPIView):
    queryset = AssessmentSession.objects.select_related(
        'preferred_role',
        'best_fit_role',
    )
    serializer_class = AssessmentSessionSerializer

    @extend_schema(
        operation_id='getAssessmentSession',
        summary='Get the current assessment session state',
        tags=['Assessment Sessions'],
        parameters=[
            OpenApiParameter(
                name='pk',
                type=str,
                location=OpenApiParameter.PATH,
                description='Assessment session UUID.',
            ),
        ],
        responses={
            200: OpenApiResponse(
                response=AssessmentSessionSerializer,
                description='Current assessment session state, including the next question when still in progress.',
                examples=[OpenApiExample('Session response', value=SESSION_RESPONSE_EXAMPLE, response_only=True)],
            ),
            404: OpenApiResponse(description='Assessment session was not found.'),
        },
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class AssessmentSessionResultAPIView(generics.RetrieveAPIView):
    queryset = AssessmentSession.objects.select_related('preferred_role', 'best_fit_role').prefetch_related(
        'mastery_scores__topic',
        'recommendations__role',
        'recommendations__topic',
    )
    serializer_class = AssessmentResultSerializer

    @extend_schema(
        operation_id='getAssessmentResults',
        summary='Get final assessment results',
        tags=['Assessment Sessions'],
        parameters=[
            OpenApiParameter(
                name='pk',
                type=str,
                location=OpenApiParameter.PATH,
                description='Assessment session UUID.',
            ),
        ],
        responses={
            200: OpenApiResponse(
                response=AssessmentResultSerializer,
                description='Final recommendations, mastery scores, and gap topics.',
                examples=[OpenApiExample('Results response', value=RESULT_RESPONSE_EXAMPLE, response_only=True)],
            ),
            404: OpenApiResponse(description='Assessment session was not found.'),
        },
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class AssessmentSessionHistoryAPIView(generics.RetrieveAPIView):
    queryset = AssessmentSession.objects.prefetch_related(
        'answers__question__topic',
        'answers__selected_option',
        'recommendations__role',
        'recommendations__topic',
    )
    serializer_class = AssessmentHistorySerializer

    @extend_schema(
        operation_id='getAssessmentHistory',
        summary='Get completed assessment history',
        tags=['Assessment Sessions'],
        parameters=[
            OpenApiParameter(
                name='pk',
                type=str,
                location=OpenApiParameter.PATH,
                description='Assessment session UUID.',
            ),
        ],
        responses={
            200: OpenApiResponse(
                response=AssessmentHistorySerializer,
                description='Completed assessment answers and recommendations.',
                examples=[OpenApiExample('History response', value=HISTORY_RESPONSE_EXAMPLE, response_only=True)],
            ),
            404: OpenApiResponse(description='Assessment session was not found.'),
            409: OpenApiResponse(
                description='Assessment history is only available after completion.',
                examples=[
                    OpenApiExample(
                        'History not ready',
                        value={'detail': 'Assessment history is only available after completion.'},
                        response_only=True,
                        status_codes=['409'],
                    )
                ],
            ),
        },
    )
    def get(self, request, *args, **kwargs):
        session = self.get_object()
        if session.status != AssessmentSession.Status.COMPLETED:
            return Response({'detail': 'Assessment history is only available after completion.'}, status=status.HTTP_409_CONFLICT)
        serializer = self.get_serializer(session)
        return Response(serializer.data)


class AssessmentAnswerSubmitAPIView(generics.GenericAPIView):
    serializer_class = AnswerSubmitSerializer

    @extend_schema(
        operation_id='submitAssessmentAnswer',
        summary='Submit an answer for the current question',
        tags=['Assessment Sessions'],
        parameters=[
            OpenApiParameter(
                name='pk',
                type=str,
                location=OpenApiParameter.PATH,
                description='Assessment session UUID.',
            ),
        ],
        request=AnswerSubmitSerializer,
        responses={
            200: OpenApiResponse(
                response=AssessmentSessionSerializer,
                description='Updated assessment session state after a valid answer submission.',
                examples=[
                    OpenApiExample('Submit answer request', value=ANSWER_REQUEST_EXAMPLE, request_only=True),
                    OpenApiExample('Submit answer response', value=SESSION_RESPONSE_EXAMPLE, response_only=True, status_codes=['200']),
                ],
            ),
            400: OpenApiResponse(
                description='Validation or assessment flow error, including out-of-order answers.',
                examples=[
                    OpenApiExample(
                        'Out-of-order submission',
                        value={'question_id': ['Out-of-order submission. Expected "role-primary-interest" (101).']},
                        response_only=True,
                        status_codes=['400'],
                    )
                ],
            ),
            404: OpenApiResponse(description='Assessment session was not found.'),
        },
    )
    def post(self, request, pk, *args, **kwargs):
        session = get_object_or_404(
            AssessmentSession.objects.select_related('preferred_role', 'best_fit_role'),
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
