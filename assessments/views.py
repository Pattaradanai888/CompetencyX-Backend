from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import generics, status
from rest_framework.response import Response

from roadmaps.models import Role

from .models import AssessmentSession
from .roadmaps import get_survey2_catalog
from .serializers import (
    AnswerSubmitSerializer,
    AssessmentHistorySerializer,
    AssessmentResultSerializer,
    AssessmentSessionSerializer,
    RoleInsightsSerializer,
    SessionCreateSerializer,
    Survey2CatalogSerializer,
    Survey2NextQuestionRequestSerializer,
    Survey2NextQuestionResponseSerializer,
    Survey2SessionStateSerializer,
)
from .services import (
    apply_recommendation_feedback_from_survey2,
    build_session_state,
    create_assessment_session,
    get_role_insights,
    submit_answer,
)
from .survey2_adaptive import apply_survey2_step_feedback, select_next_survey2_question


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
        'answered_skill_questions': 0,
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
        'answered_skill_questions': 2,
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
            language=serializer.validated_data.get('language', AssessmentSession.Language.EN),
            profile=serializer.validated_data.get('profile', {}),
        )
        return Response(
            AssessmentSessionSerializer(session, context={'session_state': build_session_state(session)}).data,
            status=status.HTTP_201_CREATED,
        )


class AssessmentSessionDetailAPIView(generics.RetrieveAPIView):
    queryset = AssessmentSession.objects.with_roles()
    serializer_class = AssessmentSessionSerializer

    @extend_schema(
        operation_id='getAssessmentSession',
        summary='Get the current assessment session state',
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
                response=AssessmentSessionSerializer,
                description='Current assessment session state, including the next question when still in progress.',
                examples=[OpenApiExample('Session response', value=SESSION_RESPONSE_EXAMPLE, response_only=True)],
            ),
            404: OpenApiResponse(description='Assessment session was not found.'),
        },
    )
    def get(self, request, *args, **kwargs):
        session = self.get_object()
        return Response(AssessmentSessionSerializer(session, context={'session_state': build_session_state(session)}).data)


class AssessmentSessionInsightsAPIView(generics.RetrieveAPIView):
    queryset = AssessmentSession.objects.with_roles()
    serializer_class = RoleInsightsSerializer

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
    def get(self, request, *args, **kwargs):
        session = self.get_object()
        insights = get_role_insights(session)
        return Response(RoleInsightsSerializer(session, context={'role_insights': insights}).data)


class AssessmentSessionResultAPIView(generics.RetrieveAPIView):
    queryset = AssessmentSession.objects.with_results()
    serializer_class = AssessmentResultSerializer

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
                description='Final recommendations, mastery scores, and gap topics.',
                examples=[OpenApiExample('Results response', value=RESULT_RESPONSE_EXAMPLE, response_only=True)],
            ),
            404: OpenApiResponse(description='Assessment session was not found.'),
        },
    )
    def get(self, request, *args, **kwargs):
        session = self.get_object()
        if session.status != AssessmentSession.Status.COMPLETED:
            return Response({'detail': 'Assessment results are only available after completion.'}, status=status.HTTP_409_CONFLICT)
        serializer = self.get_serializer(session, context={'role_insights': get_role_insights(session)})
        return Response(serializer.data)


class AssessmentSessionHistoryAPIView(generics.RetrieveAPIView):
    queryset = AssessmentSession.objects.with_history()
    serializer_class = AssessmentHistorySerializer

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
    def post(self, request, pk, *args, **kwargs):
        session = get_object_or_404(
            AssessmentSession.objects.with_roles(),
            pk=pk,
        )
        serializer = self.get_serializer(data=request.data, context={'session': session})
        serializer.is_valid(raise_exception=True)
        submit_answer(
            session=session,
            question=serializer.validated_data['question'],
            option=serializer.validated_data['option'],
            scale_value=serializer.validated_data.get('scale_value'),
            response_time_ms=serializer.validated_data.get('response_time_ms'),
            confidence_indicator=serializer.validated_data.get('confidence_indicator', ''),
        )

        session.refresh_from_db()
        return Response(AssessmentSessionSerializer(session, context={'session_state': build_session_state(session)}).data, status=status.HTTP_200_OK)


class AssessmentSurvey2SessionAPIView(generics.GenericAPIView):
    serializer_class = Survey2SessionStateSerializer
    queryset = AssessmentSession.objects.with_roles()

    def _get_survey2_state(self, session: AssessmentSession) -> dict:
        profile = session.profile if isinstance(session.profile, dict) else {}
        survey2_state = profile.get('survey2')
        if isinstance(survey2_state, dict):
            return survey2_state
        return {'completed': False, 'answers': {}, 'completed_at': None}

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
    def get(self, request, pk, *args, **kwargs):
        session = get_object_or_404(self.get_queryset(), pk=pk)
        serializer = self.get_serializer(self._get_survey2_state(session))
        return Response(serializer.data, status=status.HTTP_200_OK)

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
    def post(self, request, pk, *args, **kwargs):
        session = get_object_or_404(self.get_queryset(), pk=pk)
        previous_state = self._get_survey2_state(session)
        previous_answers = previous_state.get('answers', {}) if isinstance(previous_state, dict) else {}
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serialized_state = serializer.data

        profile = session.profile if isinstance(session.profile, dict) else {}
        profile['survey2'] = serialized_state
        session.profile = profile
        session.save(update_fields=['profile', 'updated_at'])
        if isinstance(serialized_state.get('answers'), dict):
            new_answers = serialized_state['answers']
            for question_id in new_answers:
                if question_id not in previous_answers:
                    apply_survey2_step_feedback(
                        session,
                        before_answers=new_answers,
                        answered_question_id=question_id,
                    )
        apply_recommendation_feedback_from_survey2(session)

        return Response(self.get_serializer(profile['survey2']).data, status=status.HTTP_200_OK)


class AssessmentSurvey2CatalogAPIView(generics.RetrieveAPIView):
    serializer_class = Survey2CatalogSerializer
    queryset = AssessmentSession.objects.with_roles()

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
    def get(self, request, pk, *args, **kwargs):
        session = get_object_or_404(self.get_queryset(), pk=pk)
        target_role = session.preferred_role or session.best_fit_role
        catalog = get_survey2_catalog(target_role.slug if target_role else None)
        return Response(self.get_serializer(catalog).data, status=status.HTTP_200_OK)


class AssessmentSurvey2NextQuestionAPIView(generics.GenericAPIView):
    serializer_class = Survey2NextQuestionRequestSerializer
    queryset = AssessmentSession.objects.with_roles()

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
    def post(self, request, pk, *args, **kwargs):
        session = get_object_or_404(self.get_queryset(), pk=pk)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        answers = serializer.validated_data.get('answers', {})
        next_question = select_next_survey2_question(session, answers)
        payload = Survey2NextQuestionResponseSerializer({'next_question': next_question}).data
        return Response(payload, status=status.HTTP_200_OK)
