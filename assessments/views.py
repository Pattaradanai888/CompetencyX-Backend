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
from .schema import (
    ANSWER_REQUEST_EXAMPLE,
    HISTORY_RESPONSE_EXAMPLE,
    INSIGHTS_RESPONSE_EXAMPLE,
    RESULT_RESPONSE_EXAMPLE,
    SESSION_CREATE_REQUEST_EXAMPLE,
    SESSION_RESPONSE_EXAMPLE,
    SKILL_ASSESSMENT_NEXT_QUESTION_REQUEST_EXAMPLE,
    SKILL_ASSESSMENT_NEXT_QUESTION_RESPONSE_EXAMPLE,
    SKILL_ASSESSMENT_RESPONSE_EXAMPLE,
)
from .serializers import (
    AnswerSubmitSerializer,
    AssessmentHistorySerializer,
    AssessmentResultSerializer,
    AssessmentSessionSerializer,
    RoleInsightsSerializer,
    SkillAssessmentCatalogSerializer,
    SkillAssessmentNextQuestionRequestSerializer,
    SkillAssessmentNextQuestionResponseSerializer,
    SkillAssessmentSessionStateSerializer,
)
from .services import skill_assessment_service


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
            'skill_assessment': SkillAssessmentSessionStateSerializer,
            'update_skill_assessment': SkillAssessmentSessionStateSerializer,
            'skill_assessment_catalog': SkillAssessmentCatalogSerializer,
            'skill_assessment_next_question': SkillAssessmentNextQuestionRequestSerializer,
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
        operation_id='getAssessmentSkillAssessmentSession',
        summary='Get skill assessment saved answers for an assessment session',
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
                response=SkillAssessmentSessionStateSerializer,
                description='Saved skill assessment state for this assessment session.',
                examples=[OpenApiExample('Skill assessment state', value=SKILL_ASSESSMENT_RESPONSE_EXAMPLE, response_only=True)],
            ),
            404: OpenApiResponse(description='Assessment session was not found.'),
        },
    )
    @action(detail=True, methods=['get'], url_path='skill-assessment', url_name='skill-assessment')
    def skill_assessment(self, request, *args, **kwargs):
        return Response(self.get_serializer(skill_assessment_service.get_skill_assessment_state(self.get_object())).data)

    @extend_schema(
        operation_id='saveAssessmentSkillAssessmentSession',
        summary='Save skill assessment answers for an assessment session',
        tags=['Assessment Sessions'],
        parameters=[
            OpenApiParameter(
                name='id',
                type=str,
                location=OpenApiParameter.PATH,
                description='Assessment session UUID.',
            ),
        ],
        request=SkillAssessmentSessionStateSerializer,
        responses={
            200: OpenApiResponse(
                response=SkillAssessmentSessionStateSerializer,
                description='Skill assessment state was saved.',
                examples=[OpenApiExample('Saved skill assessment state', value=SKILL_ASSESSMENT_RESPONSE_EXAMPLE, response_only=True)],
            ),
            400: OpenApiResponse(description='Validation error in skill assessment payload.'),
            404: OpenApiResponse(description='Assessment session was not found.'),
        },
    )
    @skill_assessment.mapping.post
    def update_skill_assessment(self, request, *args, **kwargs):
        session = self.get_object()
        serializer = self.get_serializer(
            data=request.data,
            context={**self.get_serializer_context(), 'session': session},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @extend_schema(
        operation_id='getAssessmentSkillAssessmentCatalog',
        summary='Get skill assessment PSP and SDLC questionnaire catalog for an assessment session',
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
                response=SkillAssessmentCatalogSerializer,
                description='Skill assessment question, dimension, scale, and role guidance catalog.',
            ),
            404: OpenApiResponse(description='Assessment session was not found.'),
        },
    )
    @action(detail=True, methods=['get'], url_path='skill-assessment/catalog', url_name='skill-assessment-catalog')
    def skill_assessment_catalog(self, request, *args, **kwargs):
        session = self.get_object()
        target_role = session.preferred_role or session.best_fit_role
        catalog = skill_assessment_service.get_skill_assessment_catalog(target_role.slug if target_role else None)
        return Response(self.get_serializer(catalog).data)

    @extend_schema(
        operation_id='getAssessmentSkillAssessmentNextQuestion',
        summary='Get the next adaptive skill assessment question',
        tags=['Assessment Sessions'],
        parameters=[
            OpenApiParameter(
                name='id',
                type=str,
                location=OpenApiParameter.PATH,
                description='Assessment session UUID.',
            ),
        ],
        request=SkillAssessmentNextQuestionRequestSerializer,
        responses={
            200: OpenApiResponse(
                response=SkillAssessmentNextQuestionResponseSerializer,
                description='Next unanswered skill assessment question selected from the current answer state, or null when complete.',
                examples=[
                    OpenApiExample('Next question request', value=SKILL_ASSESSMENT_NEXT_QUESTION_REQUEST_EXAMPLE, request_only=True),
                    OpenApiExample(
                        'Next question response',
                        value=SKILL_ASSESSMENT_NEXT_QUESTION_RESPONSE_EXAMPLE,
                        response_only=True,
                        status_codes=['200'],
                    ),
                ],
            ),
            400: OpenApiResponse(description='Validation error in skill assessment answers.'),
            404: OpenApiResponse(description='Assessment session was not found.'),
        },
    )
    @action(detail=True, methods=['post'], url_path='skill-assessment/next-question', url_name='skill-assessment-next-question')
    def skill_assessment_next_question(self, request, *args, **kwargs):
        session = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        answers = serializer.validated_data.get('answers', {})
        next_question = skill_assessment_service.select_next_skill_assessment_question(session, answers)
        payload = SkillAssessmentNextQuestionResponseSerializer({'next_question': next_question}).data
        return Response(payload)
