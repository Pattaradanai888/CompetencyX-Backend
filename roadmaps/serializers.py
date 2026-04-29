from rest_framework import serializers

from .models import Question, QuestionOption, RoadmapTopic, Role


class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ('id', 'slug', 'name', 'description')


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
        )
