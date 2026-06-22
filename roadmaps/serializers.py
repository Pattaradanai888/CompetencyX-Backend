from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .models import Question, QuestionOption, RoadmapTopic, Role


DEFAULT_LANGUAGE = 'en'
SUPPORTED_CONTENT_LANGUAGES = {'en', 'th'}

LIKERT_5_RESPONSE_SCALE = (
    {'key': 'strongly_agree', 'label': 'Strongly agree', 'labels': {'th': 'เห็นด้วยอย่างยิ่ง'}, 'value': 2, 'display_order': 1},
    {'key': 'agree', 'label': 'Agree', 'labels': {'th': 'เห็นด้วย'}, 'value': 1, 'display_order': 2},
    {'key': 'neutral', 'label': 'Neutral', 'labels': {'th': 'เป็นกลาง'}, 'value': 0, 'display_order': 3},
    {'key': 'disagree', 'label': 'Disagree', 'labels': {'th': 'ไม่เห็นด้วย'}, 'value': -1, 'display_order': 4},
    {'key': 'strongly_disagree', 'label': 'Strongly disagree', 'labels': {'th': 'ไม่เห็นด้วยอย่างยิ่ง'}, 'value': -2, 'display_order': 5},
)


def normalize_content_language(language):
    return language if language in SUPPORTED_CONTENT_LANGUAGES else DEFAULT_LANGUAGE


def get_translated_field(obj, language, field_name, fallback):
    language = normalize_content_language(language)
    if language == DEFAULT_LANGUAGE:
        return fallback
    if obj.stage != Question.Stage.ROLE:
        return fallback

    translations = obj.translations or {}
    translated_value = translations.get(language, {}).get(field_name)
    return translated_value or fallback


def get_likert_response_scale(language):
    language = normalize_content_language(language)
    return [
        {
            'key': choice['key'],
            'label': choice['labels'].get(language) or choice['label'],
            'value': choice['value'],
            'display_order': choice['display_order'],
        }
        for choice in LIKERT_5_RESPONSE_SCALE
    ]


class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ('id', 'slug', 'name', 'description', 'top_ka_codes', 'core_tasks', 'swebok_source_version')


class TopicPrerequisiteSerializer(serializers.Serializer):
    topic_id = serializers.IntegerField(source='prerequisite_id')
    required_mastery_threshold = serializers.FloatField()
    dependency_weight = serializers.FloatField()
    title = serializers.CharField(source='prerequisite.title', read_only=True, default='')


class RoadmapTopicSerializer(serializers.ModelSerializer):
    prerequisites = TopicPrerequisiteSerializer(many=True, read_only=True)

    class Meta:
        model = RoadmapTopic
        fields = (
            'id',
            'slug',
            'title',
            'topic_group',
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
    prompt = serializers.SerializerMethodField()
    help_text = serializers.SerializerMethodField()
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

    @extend_schema_field(serializers.CharField())
    def get_prompt(self, obj):
        return get_translated_field(obj, self.context.get('language'), 'prompt', obj.prompt)

    @extend_schema_field(serializers.CharField())
    def get_help_text(self, obj):
        return get_translated_field(obj, self.context.get('language'), 'help_text', obj.help_text)

    def get_response_scale(self, obj):
        if obj.question_type != Question.Type.LIKERT_5:
            return []
        return get_likert_response_scale(self.context.get('language'))
