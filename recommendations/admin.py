from django.contrib import admin

from .models import Recommendation, RecommendationQValue


@admin.register(Recommendation)
class RecommendationAdmin(admin.ModelAdmin):
    list_display = ('session', 'role', 'topic', 'policy_type', 'score', 'feedback_reward_applied', 'created_at')
    list_filter = ('policy_type', 'role')
    list_select_related = ('session', 'role', 'topic')


@admin.register(RecommendationQValue)
class RecommendationQValueAdmin(admin.ModelAdmin):
    list_display = ('state_key', 'path_kind', 'role', 'topic', 'q_value', 'update_count', 'updated_at')
    list_filter = ('path_kind', 'role')
    list_select_related = ('role', 'topic')
    search_fields = ('state_key', 'role__slug', 'topic__slug')
