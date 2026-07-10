from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .exceptions import AssessmentNotCompleted
from .models import AssessmentSession
from .serializers import (
    AnswerSubmitSerializer,
    AssessmentHistorySerializer,
    AssessmentResultSerializer,
    AssessmentSessionSerializer,
    RoleInsightsSerializer,
    Survey2CatalogSerializer,
    Survey2NextQuestionRequestSerializer,
    Survey2NextQuestionResponseSerializer,
    Survey2SessionStateSerializer,
)
from .services import survey2_service


SESSION_CREATE_REQUEST_EXAMPLE = {
    'preferred_role_slug': 'backend-engineer',
    'language': 'en',
    'profile': {
        'education_level': 'student',
        'current_stage': 'beginner',
    },
}

SESSION_RESPONSE_EXAMPLE = {
    'id': '2b39d41d-8de9-4b9b-b2ef-2a278b3f3770',
    'status': 'in_progress',
    'phase': 'role_discovery',
    'language': 'en',
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
        'answered_core_role_questions': 0,
        'answered_tie_break_questions': 0,
    },
    'role_alignment_status': 'unknown',
    'role_resolution_status': 'in_progress',
    'guidance_summary': 'You want to pursue Backend Engineer. Complete the role-discovery profile to compare fit.',
    'current_question': {
        'id': 101,
        'code': 'role-likert-build-working-parts',
        'stage': 'role',
        'question_type': 'likert_5',
        'prompt': 'I enjoy turning an idea into a working technical part.',
        'help_text': '',
        'role': None,
        'topic': None,
        'difficulty': 1,
        'options': [],
        'response_scale': [
            {
                'key': 'strongly_agree',
                'label': 'Strongly agree',
                'value': 2,
                'display_order': 1,
            },
            {
                'key': 'agree',
                'label': 'Agree',
                'value': 1,
                'display_order': 2,
            },
            {
                'key': 'neutral',
                'label': 'Neutral',
                'value': 0,
                'display_order': 3,
            },
            {
                'key': 'disagree',
                'label': 'Disagree',
                'value': -1,
                'display_order': 4,
            },
            {
                'key': 'strongly_disagree',
                'label': 'Strongly disagree',
                'value': -2,
                'display_order': 5,
            },
        ],
    },
}

INSIGHTS_RESPONSE_EXAMPLE = {
    'role_resolution_status': 'resolved',
    'best_fit_role': {
        'id': 2,
        'slug': 'backend-engineer',
        'name': 'Backend Engineer',
        'description': 'Builds APIs, data flows, and server-side application logic.',
    },
    'best_fit_confidence': 0.71,
    'answered_role_questions': 3,
    'pillar_profile': [
        {
            'key': 'systems_design',
            'label': 'Systems Design',
            'raw_score': 7.0,
            'normalized_score': 0.5,
            'evidence_count': 3,
        },
        {
            'key': 'reliability_automation',
            'label': 'Reliability and Automation',
            'raw_score': 4.0,
            'normalized_score': 0.286,
            'evidence_count': 2,
        },
    ],
    'ranked_roles': [
        {
            'slug': 'backend-engineer',
            'name': 'Backend Engineer',
            'fit_score': 0.71,
            'fit_share': 0.18,
            'top_supporting_pillars': ['Systems Design', 'Reliability and Automation', 'Data Reasoning'],
        },
        {
            'slug': 'system-architect',
            'name': 'System Architect',
            'fit_score': 0.58,
            'fit_share': 0.16,
            'top_supporting_pillars': ['Systems Design', 'Risk and Security'],
        },
    ],
    'guidance_summary': 'Your current answers align best with Backend Engineer.',
}

ANSWER_REQUEST_EXAMPLE = {
    'question_id': 101,
    'scale_value': 2,
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
        'answered_core_role_questions': 2,
        'answered_tie_break_questions': 0,
    },
    'role_alignment_status': 'aligned',
    'role_resolution_status': 'resolved',
    'guidance_summary': 'You are tracking well toward Backend Engineer. Focus next on Databases, HTTP Fundamentals.',
    'pillar_profile': [
        {
            'key': 'systems_design',
            'label': 'Systems Design',
            'raw_score': 7.0,
            'normalized_score': 0.5,
            'evidence_count': 3,
        }
    ],
    'ranked_roles': [
        {
            'slug': 'backend-engineer',
            'name': 'Backend Engineer',
            'fit_score': 0.71,
            'fit_share': 0.18,
            'top_supporting_pillars': ['Systems Design', 'Reliability and Automation', 'Data Reasoning'],
        }
    ],
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
            'question_code': 'role-likert-build-working-parts',
            'question_prompt': 'I enjoy turning an idea into a working technical part.',
            'question_stage': 'role',
            'topic_slug': None,
            'selected_option_id': None,
            'selected_option_key': None,
            'selected_option_label': None,
            'scale_value': 2,
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

SURVEY2_RESPONSE_EXAMPLE = {
    'completed': True,
    'answers': {
        'q-req': 4,
        'q-design': 5,
        'q-dev': 4,
        'q-test': 3,
        'q-release': 3,
        'q-psp': 4,
    },
    'completed_at': '2026-05-08T20:00:00Z',
}

SURVEY2_NEXT_QUESTION_REQUEST_EXAMPLE = {
    'answers': {
        'q-req': 4,
        'q-design': 5,
    },
}

SURVEY2_NEXT_QUESTION_RESPONSE_EXAMPLE = {
    'next_question': {
        'id': 'q-dev',
        'prompt': 'I can implement features using clear design and coding practices.',
        'dimension_key': 'development',
    },
}


@extend_schema_view(
    create=extend_schema(
        operation_id='createAssessmentSession',
        summary='Create an assessment session',
        tags=['Assessment Sessions'],
        request=AssessmentSessionSerializer,
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
    ),
)
class AssessmentSessionViewSet(mixins.CreateModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = AssessmentSessionSerializer

    def get_queryset(self):
        if self.action == 'results':
            return AssessmentSession.objects.with_results()
        if self.action == 'history':
            return AssessmentSession.objects.with_history()
        return AssessmentSession.objects.with_roles()

    def get_serializer_class(self):
        return {
            'insights': RoleInsightsSerializer,
            'results': AssessmentResultSerializer,
            'history': AssessmentHistorySerializer,
            'answers': AnswerSubmitSerializer,
            'survey2': Survey2SessionStateSerializer,
            'update_survey2': Survey2SessionStateSerializer,
            'survey2_catalog': Survey2CatalogSerializer,
            'survey2_next_question': Survey2NextQuestionRequestSerializer,
        }.get(getattr(self, 'action', None), AssessmentSessionSerializer)

    @extend_schema(
        operation_id='getAssessmentInsights',
        summary='Get role discovery insights',
        tags=['Assessment Sessions'],
        parameters=[
            OpenApiParameter(
                name='id',
                type=str,
                location=OpenApiParameter.PATH,
                description='Assessment session UUID.',
            ),
        ],
        responses={
            200: OpenApiResponse(
                response=RoleInsightsSerializer,
                description='Pillar profile and ranked role insights for the session.',
                examples=[OpenApiExample('Insights response', value=INSIGHTS_RESPONSE_EXAMPLE, response_only=True)],
            ),
            404: OpenApiResponse(description='Assessment session was not found.'),
        },
    )
    @action(detail=True, methods=['get'])
    def insights(self, request, *args, **kwargs):
        return Response(self.get_serializer(self.get_object()).data)

    @extend_schema(
        operation_id='getAssessmentResults',
        summary='Get final assessment results',
        tags=['Assessment Sessions'],
        parameters=[
            OpenApiParameter(
                name='id',
                type=str,
                location=OpenApiParameter.PATH,
                description='Assessment session UUID.',
            ),
        ],
        responses={
            200: OpenApiResponse(
                response=AssessmentResultSerializer,
                description='Final recommendations and gap topics.',
                examples=[OpenApiExample('Results response', value=RESULT_RESPONSE_EXAMPLE, response_only=True)],
            ),
            404: OpenApiResponse(description='Assessment session was not found.'),
            409: OpenApiResponse(description='Assessment results are only available after completion.'),
        },
    )
    @action(detail=True, methods=['get'])
    def results(self, request, *args, **kwargs):
        session = self.get_object()
        if session.status != AssessmentSession.Status.COMPLETED:
            raise AssessmentNotCompleted
        return Response(self.get_serializer(session).data)

    @extend_schema(
        operation_id='getAssessmentHistory',
        summary='Get completed assessment history',
        tags=['Assessment Sessions'],
        parameters=[
            OpenApiParameter(
                name='id',
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
    @action(detail=True, methods=['get'])
    def history(self, request, *args, **kwargs):
        session = self.get_object()
        if session.status != AssessmentSession.Status.COMPLETED:
            msg = 'Assessment history is only available after completion.'
            raise AssessmentNotCompleted(msg)
        return Response(self.get_serializer(session).data)

    @extend_schema(
        operation_id='submitAssessmentAnswer',
        summary='Submit an answer for the current question',
        tags=['Assessment Sessions'],
        parameters=[
            OpenApiParameter(
                name='id',
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
    @action(detail=True, methods=['post'], url_path='answers', url_name='answers')
    def answers(self, request, *args, **kwargs):
        session = self.get_object()
        serializer = self.get_serializer(
            data=request.data,
            context={**self.get_serializer_context(), 'session': session},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        session.refresh_from_db()
        output = AssessmentSessionSerializer(session, context=self.get_serializer_context())
        return Response(output.data)

    @extend_schema(
        operation_id='getAssessmentSurvey2Session',
        summary='Get Survey 2 saved answers for an assessment session',
        tags=['Assessment Sessions'],
        parameters=[
            OpenApiParameter(
                name='id',
                type=str,
                location=OpenApiParameter.PATH,
                description='Assessment session UUID.',
            ),
        ],
        responses={
            200: OpenApiResponse(
                response=Survey2SessionStateSerializer,
                description='Saved Survey 2 state for this assessment session.',
                examples=[OpenApiExample('Survey 2 state', value=SURVEY2_RESPONSE_EXAMPLE, response_only=True)],
            ),
            404: OpenApiResponse(description='Assessment session was not found.'),
        },
    )
    @action(detail=True, methods=['get'], url_path='survey2', url_name='survey2')
    def survey2(self, request, *args, **kwargs):
        return Response(self.get_serializer(survey2_service.get_survey2_state(self.get_object())).data)

    @extend_schema(
        operation_id='saveAssessmentSurvey2Session',
        summary='Save Survey 2 answers for an assessment session',
        tags=['Assessment Sessions'],
        parameters=[
            OpenApiParameter(
                name='id',
                type=str,
                location=OpenApiParameter.PATH,
                description='Assessment session UUID.',
            ),
        ],
        request=Survey2SessionStateSerializer,
        responses={
            200: OpenApiResponse(
                response=Survey2SessionStateSerializer,
                description='Survey 2 state was saved.',
                examples=[OpenApiExample('Saved Survey 2 state', value=SURVEY2_RESPONSE_EXAMPLE, response_only=True)],
            ),
            400: OpenApiResponse(description='Validation error in Survey 2 payload.'),
            404: OpenApiResponse(description='Assessment session was not found.'),
        },
    )
    @survey2.mapping.post
    def update_survey2(self, request, *args, **kwargs):
        session = self.get_object()
        serializer = self.get_serializer(
            data=request.data,
            context={**self.get_serializer_context(), 'session': session},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @extend_schema(
        operation_id='getAssessmentSurvey2Catalog',
        summary='Get Survey 2 PSP and SDLC questionnaire catalog for an assessment session',
        tags=['Assessment Sessions'],
        parameters=[
            OpenApiParameter(
                name='id',
                type=str,
                location=OpenApiParameter.PATH,
                description='Assessment session UUID.',
            ),
        ],
        responses={
            200: OpenApiResponse(
                response=Survey2CatalogSerializer,
                description='Survey 2 question, dimension, scale, and role guidance catalog.',
            ),
            404: OpenApiResponse(description='Assessment session was not found.'),
        },
    )
    @action(detail=True, methods=['get'], url_path='survey2/catalog', url_name='survey2-catalog')
    def survey2_catalog(self, request, *args, **kwargs):
        session = self.get_object()
        target_role = session.preferred_role or session.best_fit_role
        catalog = survey2_service.get_survey2_catalog(target_role.slug if target_role else None)
        return Response(self.get_serializer(catalog).data)

    @extend_schema(
        operation_id='getAssessmentSurvey2NextQuestion',
        summary='Get the next adaptive Survey 2 question',
        tags=['Assessment Sessions'],
        parameters=[
            OpenApiParameter(
                name='id',
                type=str,
                location=OpenApiParameter.PATH,
                description='Assessment session UUID.',
            ),
        ],
        request=Survey2NextQuestionRequestSerializer,
        responses={
            200: OpenApiResponse(
                response=Survey2NextQuestionResponseSerializer,
                description='Next unanswered Survey 2 question selected from the current answer state, or null when complete.',
                examples=[
                    OpenApiExample('Next question request', value=SURVEY2_NEXT_QUESTION_REQUEST_EXAMPLE, request_only=True),
                    OpenApiExample('Next question response', value=SURVEY2_NEXT_QUESTION_RESPONSE_EXAMPLE, response_only=True, status_codes=['200']),
                ],
            ),
            400: OpenApiResponse(description='Validation error in Survey 2 answers.'),
            404: OpenApiResponse(description='Assessment session was not found.'),
        },
    )
    @action(detail=True, methods=['post'], url_path='survey2/next-question', url_name='survey2-next-question')
    def survey2_next_question(self, request, *args, **kwargs):
        session = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        answers = serializer.validated_data.get('answers', {})
        next_question = survey2_service.select_next_survey2_question(session, answers)
        payload = Survey2NextQuestionResponseSerializer({'next_question': next_question}).data
        return Response(payload)
