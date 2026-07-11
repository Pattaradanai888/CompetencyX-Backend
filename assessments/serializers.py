from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from recommendations.serializers import RecommendationSerializer
from roadmaps.models import Question, QuestionOption, Role
from roadmaps.serializers import RoadmapTopicSerializer, RoleSerializer

from .models import Answer, AssessmentSession
from .services.assessment_service import (
    build_session_state,
    create_assessment_session,
    get_current_question,
    submit_answer,
)
from .services.guidance_service import (
    build_guidance_summary,
    get_preferred_role_gap_topics,
    get_role_alignment_status,
    get_role_insights,
    get_visible_role_result,
    serialize_milestones,
)
from .services.survey2_service import SURVEY2_FEEDBACK_PROFILE_KEY, get_survey2_question_ids, save_survey2_state


# No docstrings on these mixins: drf-spectacular inherits class docstrings into
# the OpenAPI component descriptions of every serializer that mixes them in.
class ContextMemoMixin:
    # Memoize expensive per-object builders, honoring a pre-computed value injected via serializer context.
    def _memoized(self, obj, *, context_key, builder):
        cached = self.context.get(context_key)
        if cached is not None:
            return cached
        cache = self.__dict__.setdefault('_memo_cache', {})
        key = (context_key, obj.pk)
        if key not in cache:
            cache[key] = builder(obj)
        return cache[key]


class PublicProfileField(serializers.JSONField):
    def to_representation(self, value):
        data = super().to_representation(value)
        if isinstance(data, dict):
            data = dict(data)
            data.pop(SURVEY2_FEEDBACK_PROFILE_KEY, None)
        return data


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

        attrs['option'] = option
        attrs['question'] = question
        attrs['scale_value'] = scale_value
        attrs.pop('question_id')
        attrs.pop('option_id', None)
        return attrs

    def create(self, validated_data):
        return submit_answer(session=self.context['session'], **validated_data)

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


class RoleInsightsFieldsMixin(ContextMemoMixin):
    def _insights(self, obj):
        return self._memoized(obj, context_key='role_insights', builder=get_role_insights)

    @extend_schema_field(PillarInsightSerializer(many=True))
    def get_pillar_profile(self, obj):
        return self._insights(obj)['pillar_profile']

    @extend_schema_field(RankedRoleInsightSerializer(many=True))
    def get_ranked_roles(self, obj):
        return self._insights(obj)['ranked_roles']


class RoleInsightsSerializer(RoleInsightsFieldsMixin, serializers.ModelSerializer):
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

    @extend_schema_field(serializers.CharField())
    def get_guidance_summary(self, obj):
        return self._insights(obj)['guidance_summary']


class AssessmentSessionSerializer(ContextMemoMixin, serializers.ModelSerializer):
    profile = PublicProfileField(required=False)
    preferred_role_slug = serializers.SlugRelatedField(
        source='preferred_role',
        slug_field='slug',
        queryset=Role.objects.filter(is_active=True),
        write_only=True,
        required=False,
        error_messages={'does_not_exist': 'Unknown role slug.'},
    )
    current_role_slug = serializers.SlugRelatedField(
        source='current_role',
        slug_field='slug',
        queryset=Role.objects.filter(is_active=True),
        write_only=True,
        required=False,
        error_messages={'does_not_exist': 'Unknown role slug.'},
    )
    preferred_role = RoleSerializer(read_only=True)
    current_role = RoleSerializer(read_only=True)
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
            'preferred_role_slug',
            'current_role_slug',
            'status',
            'phase',
            'language',
            'best_fit_confidence',
            'preferred_role',
            'current_role',
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
        read_only_fields = (
            'status',
            'phase',
            'best_fit_confidence',
            'preferred_role',
            'current_role',
            'best_fit_role',
            'started_at',
            'updated_at',
            'completed_at',
            'milestones',
            'role_alignment_status',
            'role_resolution_status',
            'guidance_summary',
            'current_question',
        )

    def create(self, validated_data):
        return create_assessment_session(**validated_data)

    def _session_state(self, obj):
        return self._memoized(obj, context_key='session_state', builder=build_session_state)

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


class AssessmentResultSerializer(RoleInsightsFieldsMixin, serializers.ModelSerializer):
    profile = PublicProfileField(read_only=True)
    preferred_role = RoleSerializer(read_only=True)
    current_role = RoleSerializer(read_only=True)
    best_fit_role = serializers.SerializerMethodField()
    best_fit_confidence = serializers.SerializerMethodField()
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
            'current_role',
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
            'preferred_path_recommendation',
            'best_fit_path_recommendation',
        )

    def _visible_role_result(self, obj):
        return self._memoized(obj, context_key='visible_role_result', builder=get_visible_role_result)

    def _recommendations(self, obj):
        if not hasattr(self, '_recommendation_cache'):
            self._recommendation_cache = {}
        if obj.pk not in self._recommendation_cache:
            self._recommendation_cache[obj.pk] = list(obj.recommendations.all())
        return self._recommendation_cache[obj.pk]

    @extend_schema_field(serializers.JSONField())
    def get_milestones(self, obj):
        return serialize_milestones(obj)

    @extend_schema_field(serializers.CharField())
    def get_role_alignment_status(self, obj):
        return get_role_alignment_status(obj)

    @extend_schema_field(serializers.CharField())
    def get_role_resolution_status(self, obj):
        return self._visible_role_result(obj)['role_resolution_status']

    @extend_schema_field(RoleSerializer(allow_null=True))
    def get_best_fit_role(self, obj):
        best_fit_role = self._visible_role_result(obj)['best_fit_role']
        return RoleSerializer(best_fit_role).data if best_fit_role else None

    @extend_schema_field(serializers.FloatField())
    def get_best_fit_confidence(self, obj):
        return self._visible_role_result(obj)['best_fit_confidence']

    @extend_schema_field(serializers.CharField())
    def get_guidance_summary(self, obj):
        return build_guidance_summary(obj)

    @extend_schema_field(RoadmapTopicSerializer(many=True))
    def get_preferred_role_gap_topics(self, obj):
        return RoadmapTopicSerializer(get_preferred_role_gap_topics(obj), many=True).data

    @extend_schema_field(RecommendationSerializer(allow_null=True))
    def get_preferred_path_recommendation(self, obj):
        recommendation = next((item for item in self._recommendations(obj) if item.path_kind == 'preferred'), None)
        return RecommendationSerializer(recommendation).data if recommendation else None

    @extend_schema_field(RecommendationSerializer(allow_null=True))
    def get_best_fit_path_recommendation(self, obj):
        recommendation = next((item for item in self._recommendations(obj) if item.path_kind == 'best_fit'), None)
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
        known_question_ids = get_survey2_question_ids()
        for key in value:
            if not str(key).strip():
                msg = 'Answer keys must be non-empty strings.'
                raise serializers.ValidationError(msg)
            if key not in known_question_ids:
                msg = f'Unknown Survey 2 question id "{key}".'
                raise serializers.ValidationError(msg)
        return value

    def validate(self, attrs):
        if attrs.get('completed', False):
            missing_question_ids = sorted(get_survey2_question_ids() - set(attrs.get('answers', {})))
            if missing_question_ids:
                raise serializers.ValidationError({'answers': f'Completed Survey 2 is missing answers for: {", ".join(missing_question_ids)}.'})
        return attrs

    def create(self, validated_data):
        return save_survey2_state(session=self.context['session'], state=validated_data)


class Survey2ScaleOptionSerializer(serializers.Serializer):
    label = serializers.CharField()
    label_th = serializers.CharField(required=False)
    value = serializers.IntegerField(min_value=1, max_value=5)


class Survey2DimensionSerializer(serializers.Serializer):
    key = serializers.CharField()
    label = serializers.CharField()
    track = serializers.ChoiceField(choices=['psp', 'sdlc'])
    low_score_action = serializers.CharField()


class Survey2QuestionSerializer(serializers.Serializer):
    id = serializers.CharField()
    prompt = serializers.CharField()
    translations = serializers.DictField(required=False)
    dimension_key = serializers.CharField()


class Survey2CatalogSerializer(serializers.Serializer):
    version = serializers.CharField()
    scale = Survey2ScaleOptionSerializer(many=True)
    dimensions = Survey2DimensionSerializer(many=True)
    questions = Survey2QuestionSerializer(many=True)
    role_guidance = serializers.ListField(child=serializers.CharField())


class Survey2NextQuestionRequestSerializer(serializers.Serializer):
    answers = serializers.DictField(
        child=serializers.IntegerField(min_value=1, max_value=5),
        default=dict,
    )

    def validate_answers(self, value):
        known_question_ids = get_survey2_question_ids()
        for key in value:
            if key not in known_question_ids:
                msg = f'Unknown Survey 2 question id "{key}".'
                raise serializers.ValidationError(msg)
        return value


class Survey2NextQuestionResponseSerializer(serializers.Serializer):
    next_question = Survey2QuestionSerializer(allow_null=True)
