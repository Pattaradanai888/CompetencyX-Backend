from rest_framework import serializers

from .models import Question, QuestionOption, RoadmapTopic, Role


LIKERT_5_RESPONSE_SCALE = (
    {'key': 'strongly_agree', 'label': 'Strongly agree', 'value': 2, 'display_order': 1},
    {'key': 'agree', 'label': 'Agree', 'value': 1, 'display_order': 2},
    {'key': 'neutral', 'label': 'Neutral', 'value': 0, 'display_order': 3},
    {'key': 'disagree', 'label': 'Disagree', 'value': -1, 'display_order': 4},
    {'key': 'strongly_disagree', 'label': 'Strongly disagree', 'value': -2, 'display_order': 5},
)


class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ('id', 'slug', 'name', 'description', 'top_ka_codes', 'core_tasks', 'swebok_source_version')


class TopicPrerequisiteSerializer(serializers.Serializer):
    topic_id = serializers.IntegerField(source='prerequisite_id')
    required_mastery_threshold = serializers.FloatField()
    dependency_weight = serializers.FloatField()


class RoadmapTopicSerializer(serializers.ModelSerializer):
    prerequisites = TopicPrerequisiteSerializer(many=True, read_only=True)

    class Meta:
        model = RoadmapTopic
        fields = (
            'id',
            'slug',
            'title',
            'description',
            'difficulty',
            'display_order',
            'parent_id',
            'prerequisites',
        )


class QuestionOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuestionOption
        fields = ('id', 'key', 'label', 'value', 'display_order')


class QuestionSerializer(serializers.ModelSerializer):
    options = QuestionOptionSerializer(many=True, read_only=True)
    response_scale = serializers.SerializerMethodField()
    role = serializers.SlugRelatedField(read_only=True, slug_field='slug')
    topic = serializers.SlugRelatedField(read_only=True, slug_field='slug')

    class Meta:
        model = Question
        fields = (
            'id',
            'code',
            'stage',
            'question_type',
            'prompt',
            'help_text',
            'role',
            'topic',
            'difficulty',
            'options',
            'response_scale',
        )

    def get_response_scale(self, obj):
        if obj.question_type != Question.Type.LIKERT_5:
            return []
        return list(LIKERT_5_RESPONSE_SCALE)
