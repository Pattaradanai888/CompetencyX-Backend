from rest_framework import serializers

from .models import Recommendation


class RecommendationSerializer(serializers.ModelSerializer):
    role_slug = serializers.SlugRelatedField(source='role', read_only=True, slug_field='slug')
    topic_slug = serializers.SlugRelatedField(source='topic', read_only=True, slug_field='slug')
    topic_title = serializers.CharField(source='topic.title', read_only=True)

    class Meta:
        model = Recommendation
        fields = (
            'id',
            'role_slug',
            'topic_id',
            'topic_slug',
            'topic_title',
            'reason',
            'policy_type',
            'score',
            'created_at',
        )
