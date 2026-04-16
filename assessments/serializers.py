from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from recommendations.serializers import RecommendationSerializer
from roadmaps.models import Question, QuestionOption, Role
from roadmaps.serializers import QuestionSerializer, RoleSerializer

from .models import Answer, AssessmentSession, TopicMastery
from .services import get_current_question, serialize_milestones


class SessionCreateSerializer(serializers.Serializer):
    selected_role_slug = serializers.SlugField(required=False)
    profile = serializers.DictField(required=False)

    def validate_selected_role_slug(self, value):
        if not Role.objects.filter(slug=value, is_active=True).exists():
            msg = 'Unknown role slug.'
            raise serializers.ValidationError(msg)
        return value


class AnswerSubmitSerializer(serializers.Serializer):
    question_id = serializers.IntegerField()
    option_id = serializers.IntegerField()
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
        try:
            option = QuestionOption.objects.get(id=attrs['option_id'], question=question)
        except QuestionOption.DoesNotExist as exc:
            raise serializers.ValidationError({'option_id': 'Option does not belong to the question.'}) from exc

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
        return attrs


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


class AssessmentSessionSerializer(serializers.ModelSerializer):
    selected_role = RoleSerializer(read_only=True)
    inferred_role = RoleSerializer(read_only=True)
    current_question = serializers.SerializerMethodField()
    mastery_scores = TopicMasterySerializer(many=True, read_only=True)
    latest_recommendation = serializers.SerializerMethodField()
    milestones = serializers.SerializerMethodField()

    class Meta:
        model = AssessmentSession
        fields = (
            'id',
            'status',
            'phase',
            'role_confidence',
            'selected_role',
            'inferred_role',
            'profile',
            'started_at',
            'updated_at',
            'completed_at',
            'milestones',
            'current_question',
            'mastery_scores',
            'latest_recommendation',
        )

    @extend_schema_field(QuestionSerializer(allow_null=True))
    def get_current_question(self, obj):
        question = get_current_question(obj)
        return QuestionSerializer(question).data if question else None

    @extend_schema_field(RecommendationSerializer(allow_null=True))
    def get_latest_recommendation(self, obj):
        recommendation = obj.recommendations.select_related('role', 'topic').first()
        return RecommendationSerializer(recommendation).data if recommendation else None

    @extend_schema_field(serializers.JSONField())
    def get_milestones(self, obj):
        return serialize_milestones(obj)


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
            'response_time_ms',
            'confidence_indicator',
            'responded_at',
        )


class AssessmentResultSerializer(serializers.ModelSerializer):
    selected_role = RoleSerializer(read_only=True)
    inferred_role = RoleSerializer(read_only=True)
    mastery_scores = TopicMasterySerializer(many=True, read_only=True)
    recommendations = RecommendationSerializer(many=True, read_only=True)
    answers = AnswerHistorySerializer(many=True, read_only=True)
    milestones = serializers.SerializerMethodField()

    class Meta:
        model = AssessmentSession
        fields = (
            'id',
            'status',
            'phase',
            'role_confidence',
            'selected_role',
            'inferred_role',
            'profile',
            'started_at',
            'updated_at',
            'completed_at',
            'milestones',
            'mastery_scores',
            'recommendations',
            'answers',
        )

    @extend_schema_field(serializers.JSONField())
    def get_milestones(self, obj):
        return serialize_milestones(obj)


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
