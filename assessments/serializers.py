from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from recommendations.serializers import RecommendationSerializer
from roadmaps.models import Question, QuestionOption, Role
from roadmaps.serializers import RoadmapTopicSerializer, RoleSerializer

from .models import Answer, AssessmentSession, TopicMastery
from .services import (
    build_guidance_summary,
    build_session_state,
    get_current_question,
    get_preferred_role_gap_topics,
    get_role_alignment_status,
    get_role_insights,
    get_role_resolution_status,
    serialize_milestones,
)


class SessionCreateSerializer(serializers.Serializer):
    preferred_role_slug = serializers.SlugField(required=False)
    profile = serializers.DictField(required=False)

    def validate_preferred_role_slug(self, value):
        if not Role.objects.filter(slug=value, is_active=True).exists():
            msg = 'Unknown role slug.'
            raise serializers.ValidationError(msg)
        return value


class AnswerSubmitSerializer(serializers.Serializer):
    question_id = serializers.IntegerField()
    option_id = serializers.IntegerField(required=False)
    scale_value = serializers.IntegerField(required=False)
    response_time_ms = serializers.IntegerField(required=False, min_value=0)
    confidence_indicator = serializers.ChoiceField(
        choices=['low', 'medium', 'high'],
        required=False,
        allow_blank=True,
    )

    def validate(self, attrs):
        session: AssessmentSession | None = self.context.get('session')
        try:
            question = Question.objects.prefetch_related('options').get(id=attrs['question_id'], is_active=True)
        except Question.DoesNotExist as exc:
            raise serializers.ValidationError({'question_id': 'Unknown active question.'}) from exc

        if question.question_type == Question.Type.LIKERT_5:
            option, scale_value = self._validate_likert_answer(attrs)
        else:
            option, scale_value = self._validate_option_answer(attrs, question)

        if session is not None:
            expected_question = get_current_question(session)
            if expected_question is None:
                raise serializers.ValidationError({'question_id': 'This assessment session is not accepting more answers.'})
            if question.id != expected_question.id:
                raise serializers.ValidationError(
                    {'question_id': (f'Out-of-order submission. Expected "{expected_question.code}" ({expected_question.id}).')}
                )

        attrs['question'] = question
        attrs['option'] = option
        attrs['scale_value'] = scale_value
        return attrs

    def _validate_likert_answer(self, attrs):
        scale_value = attrs.get('scale_value')
        if 'option_id' in attrs:
            raise serializers.ValidationError({'option_id': 'Likert questions must submit scale_value instead of option_id.'})
        if scale_value not in {-2, -1, 0, 1, 2}:
            raise serializers.ValidationError({'scale_value': 'Use one of -2, -1, 0, 1, or 2.'})
        return None, scale_value

    def _validate_option_answer(self, attrs, question):
        if 'scale_value' in attrs:
            raise serializers.ValidationError({'scale_value': 'Option questions must submit option_id instead of scale_value.'})
        if 'option_id' not in attrs:
            raise serializers.ValidationError({'option_id': 'This question requires an option_id.'})
        try:
            option = QuestionOption.objects.get(id=attrs['option_id'], question=question)
        except QuestionOption.DoesNotExist as exc:
            raise serializers.ValidationError({'option_id': 'Option does not belong to the question.'}) from exc
        return option, None


class TopicMasterySerializer(serializers.ModelSerializer):
    topic_slug = serializers.SlugRelatedField(source='topic', read_only=True, slug_field='slug')
    topic_title = serializers.CharField(source='topic.title', read_only=True)

    class Meta:
        model = TopicMastery
        fields = (
            'topic_id',
            'topic_slug',
            'topic_title',
            'mastery_score',
            'confidence_score',
            'updated_at',
        )


class PillarInsightSerializer(serializers.Serializer):
    key = serializers.CharField()
    label = serializers.CharField()
    raw_score = serializers.FloatField()
    normalized_score = serializers.FloatField()
    evidence_count = serializers.IntegerField()


class RankedRoleInsightSerializer(serializers.Serializer):
    slug = serializers.CharField()
    name = serializers.CharField()
    fit_score = serializers.FloatField()
    fit_share = serializers.FloatField()
    top_supporting_pillars = serializers.ListField(child=serializers.CharField())


class RoleInsightsSerializer(serializers.ModelSerializer):
    role_resolution_status = serializers.SerializerMethodField()
    answered_role_questions = serializers.SerializerMethodField()
    pillar_profile = serializers.SerializerMethodField()
    ranked_roles = serializers.SerializerMethodField()
    guidance_summary = serializers.SerializerMethodField()
    best_fit_role = serializers.SerializerMethodField()
    best_fit_confidence = serializers.SerializerMethodField()

    class Meta:
        model = AssessmentSession
        fields = (
            'role_resolution_status',
            'best_fit_role',
            'best_fit_confidence',
            'answered_role_questions',
            'pillar_profile',
            'ranked_roles',
            'guidance_summary',
        )

    def _insights(self, obj):
        cached = self.context.get('role_insights')
        if cached is not None:
            return cached
        return get_role_insights(obj)

    @extend_schema_field(serializers.CharField())
    def get_role_resolution_status(self, obj):
        return self._insights(obj)['role_resolution_status']

    @extend_schema_field(RoleSerializer(allow_null=True))
    def get_best_fit_role(self, obj):
        best_fit_role = self._insights(obj)['best_fit_role']
        return RoleSerializer(best_fit_role).data if best_fit_role else None

    @extend_schema_field(serializers.FloatField())
    def get_best_fit_confidence(self, obj):
        return self._insights(obj)['best_fit_confidence']

    @extend_schema_field(serializers.IntegerField())
    def get_answered_role_questions(self, obj):
        return self._insights(obj)['answered_role_questions']

    @extend_schema_field(PillarInsightSerializer(many=True))
    def get_pillar_profile(self, obj):
        return self._insights(obj)['pillar_profile']

    @extend_schema_field(RankedRoleInsightSerializer(many=True))
    def get_ranked_roles(self, obj):
        return self._insights(obj)['ranked_roles']

    @extend_schema_field(serializers.CharField())
    def get_guidance_summary(self, obj):
        return self._insights(obj)['guidance_summary']


class AssessmentSessionSerializer(serializers.ModelSerializer):
    preferred_role = RoleSerializer(read_only=True)
    best_fit_role = serializers.SerializerMethodField()
    best_fit_confidence = serializers.SerializerMethodField()
    milestones = serializers.SerializerMethodField()
    role_alignment_status = serializers.SerializerMethodField()
    role_resolution_status = serializers.SerializerMethodField()
    guidance_summary = serializers.SerializerMethodField()
    current_question = serializers.SerializerMethodField()

    class Meta:
        model = AssessmentSession
        fields = (
            'id',
            'status',
            'phase',
            'best_fit_confidence',
            'preferred_role',
            'best_fit_role',
            'profile',
            'started_at',
            'updated_at',
            'completed_at',
            'milestones',
            'role_alignment_status',
            'role_resolution_status',
            'guidance_summary',
            'current_question',
        )

    def _session_state(self, obj):
        session_state = self.context.get('session_state')
        if session_state is not None:
            return session_state
        return build_session_state(obj)

    @extend_schema_field(RoleSerializer(allow_null=True))
    def get_best_fit_role(self, obj):
        best_fit_role = self._session_state(obj)['best_fit_role']
        return RoleSerializer(best_fit_role).data if best_fit_role else None

    @extend_schema_field(serializers.FloatField())
    def get_best_fit_confidence(self, obj):
        return self._session_state(obj)['best_fit_confidence']

    @extend_schema_field(serializers.JSONField())
    def get_milestones(self, obj):
        return self._session_state(obj)['milestones']

    @extend_schema_field(serializers.CharField())
    def get_role_alignment_status(self, obj):
        return self._session_state(obj)['role_alignment_status']

    @extend_schema_field(serializers.CharField())
    def get_role_resolution_status(self, obj):
        return self._session_state(obj)['role_resolution_status']

    @extend_schema_field(serializers.CharField())
    def get_guidance_summary(self, obj):
        return self._session_state(obj)['guidance_summary']

    @extend_schema_field(serializers.JSONField(allow_null=True))
    def get_current_question(self, obj):
        return self._session_state(obj)['current_question']


class AnswerHistorySerializer(serializers.ModelSerializer):
    question_code = serializers.CharField(source='question.code', read_only=True)
    question_prompt = serializers.CharField(source='question.prompt', read_only=True)
    question_stage = serializers.CharField(source='question.stage', read_only=True)
    topic_slug = serializers.SlugRelatedField(source='question.topic', read_only=True, slug_field='slug')
    selected_option_key = serializers.CharField(source='selected_option.key', read_only=True)
    selected_option_label = serializers.CharField(source='selected_option.label', read_only=True)

    class Meta:
        model = Answer
        fields = (
            'id',
            'question_id',
            'question_code',
            'question_prompt',
            'question_stage',
            'topic_slug',
            'selected_option_id',
            'selected_option_key',
            'selected_option_label',
            'scale_value',
            'response_time_ms',
            'confidence_indicator',
            'responded_at',
        )


class AssessmentResultSerializer(serializers.ModelSerializer):
    preferred_role = RoleSerializer(read_only=True)
    best_fit_role = serializers.SerializerMethodField()
    best_fit_confidence = serializers.SerializerMethodField()
    mastery_scores = TopicMasterySerializer(many=True, read_only=True)
    preferred_path_recommendation = serializers.SerializerMethodField()
    best_fit_path_recommendation = serializers.SerializerMethodField()
    milestones = serializers.SerializerMethodField()
    role_alignment_status = serializers.SerializerMethodField()
    role_resolution_status = serializers.SerializerMethodField()
    guidance_summary = serializers.SerializerMethodField()
    preferred_role_gap_topics = serializers.SerializerMethodField()
    pillar_profile = serializers.SerializerMethodField()
    ranked_roles = serializers.SerializerMethodField()

    class Meta:
        model = AssessmentSession
        fields = (
            'id',
            'status',
            'phase',
            'best_fit_confidence',
            'preferred_role',
            'best_fit_role',
            'profile',
            'started_at',
            'updated_at',
            'completed_at',
            'milestones',
            'role_alignment_status',
            'role_resolution_status',
            'guidance_summary',
            'pillar_profile',
            'ranked_roles',
            'preferred_role_gap_topics',
            'mastery_scores',
            'preferred_path_recommendation',
            'best_fit_path_recommendation',
        )

    def _insights(self, obj):
        cached = self.context.get('role_insights')
        if cached is not None:
            return cached
        return get_role_insights(obj)

    @extend_schema_field(serializers.JSONField())
    def get_milestones(self, obj):
        return serialize_milestones(obj)

    @extend_schema_field(serializers.CharField())
    def get_role_alignment_status(self, obj):
        return get_role_alignment_status(obj)

    @extend_schema_field(serializers.CharField())
    def get_role_resolution_status(self, obj):
        return get_role_resolution_status(obj)

    @extend_schema_field(RoleSerializer(allow_null=True))
    def get_best_fit_role(self, obj):
        if get_role_resolution_status(obj) != 'resolved':
            return None
        return RoleSerializer(obj.best_fit_role).data if obj.best_fit_role else None

    @extend_schema_field(serializers.FloatField())
    def get_best_fit_confidence(self, obj):
        return obj.best_fit_confidence if get_role_resolution_status(obj) == 'resolved' else 0.0

    @extend_schema_field(serializers.CharField())
    def get_guidance_summary(self, obj):
        return build_guidance_summary(obj)

    @extend_schema_field(PillarInsightSerializer(many=True))
    def get_pillar_profile(self, obj):
        return self._insights(obj)['pillar_profile']

    @extend_schema_field(RankedRoleInsightSerializer(many=True))
    def get_ranked_roles(self, obj):
        return self._insights(obj)['ranked_roles']

    @extend_schema_field(RoadmapTopicSerializer(many=True))
    def get_preferred_role_gap_topics(self, obj):
        return RoadmapTopicSerializer(get_preferred_role_gap_topics(obj), many=True).data

    @extend_schema_field(RecommendationSerializer(allow_null=True))
    def get_preferred_path_recommendation(self, obj):
        recommendation = obj.recommendations.filter(path_kind='preferred').select_related('role', 'topic').first()
        return RecommendationSerializer(recommendation).data if recommendation else None

    @extend_schema_field(RecommendationSerializer(allow_null=True))
    def get_best_fit_path_recommendation(self, obj):
        recommendation = obj.recommendations.filter(path_kind='best_fit').select_related('role', 'topic').first()
        return RecommendationSerializer(recommendation).data if recommendation else None


class AssessmentHistorySerializer(serializers.ModelSerializer):
    answers = AnswerHistorySerializer(many=True, read_only=True)
    recommendations = RecommendationSerializer(many=True, read_only=True)

    class Meta:
        model = AssessmentSession
        fields = (
            'id',
            'phase',
            'status',
            'answers',
            'recommendations',
        )


class Survey2SessionStateSerializer(serializers.Serializer):
    completed = serializers.BooleanField(default=False)
    answers = serializers.DictField(
        child=serializers.IntegerField(min_value=1, max_value=5),
        default=dict,
    )
    completed_at = serializers.DateTimeField(required=False, allow_null=True)

    def validate_answers(self, value):
        for key in value:
            if not str(key).strip():
                msg = 'Answer keys must be non-empty strings.'
                raise serializers.ValidationError(msg)
        return value
