from django.contrib import admin

from .models import (
    Answer,
    AssessmentSession,
    QuestionBanditStat,
    QuestionSelectionEvent,
    Survey2Dimension,
    Survey2Question,
    Survey2RoleGuidance,
    TopicMastery,
)


@admin.register(AssessmentSession)
class AssessmentSessionAdmin(admin.ModelAdmin):
    list_display = ('id', 'preferred_role', 'best_fit_role', 'phase', 'status', 'started_at')
    list_filter = ('phase', 'status', 'preferred_role', 'best_fit_role')
    readonly_fields = ('id', 'started_at', 'updated_at', 'completed_at')
    list_select_related = ('preferred_role', 'best_fit_role')


@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = ('session', 'question', 'selected_option', 'responded_at')
    list_select_related = ('question', 'selected_option', 'session')


@admin.register(TopicMastery)
class TopicMasteryAdmin(admin.ModelAdmin):
    list_display = ('session', 'topic', 'mastery_score', 'confidence_score', 'updated_at')
    list_select_related = ('session', 'topic')


@admin.register(QuestionSelectionEvent)
class QuestionSelectionEventAdmin(admin.ModelAdmin):
    list_display = ('session', 'stage', 'policy_mode', 'chosen_question', 'selection_score', 'reward', 'selected_at', 'answered_at')
    list_filter = ('stage', 'policy_mode')
    readonly_fields = ('selected_at', 'answered_at', 'selection_score', 'candidate_scores')
    list_select_related = ('session', 'chosen_question', 'heuristic_question', 'shadow_bandit_question')


@admin.register(QuestionBanditStat)
class QuestionBanditStatAdmin(admin.ModelAdmin):
    list_display = ('question', 'stage', 'pulls', 'mean_reward', 'cumulative_reward', 'last_selected_at')
    list_filter = ('stage',)
    list_select_related = ('question',)


@admin.register(Survey2Question)
class Survey2QuestionAdmin(admin.ModelAdmin):
    list_display = ('question_id', 'dimension_key', 'display_order', 'is_active', 'updated_at')
    list_filter = ('dimension_key', 'is_active')
    search_fields = ('question_id', 'prompt')


@admin.register(Survey2Dimension)
class Survey2DimensionAdmin(admin.ModelAdmin):
    list_display = ('dimension_key', 'label', 'track', 'display_order', 'is_active', 'updated_at')
    list_filter = ('track', 'is_active')
    search_fields = ('dimension_key', 'label', 'low_score_action')


@admin.register(Survey2RoleGuidance)
class Survey2RoleGuidanceAdmin(admin.ModelAdmin):
    list_display = ('role', 'display_order', 'is_active', 'updated_at')
    list_filter = ('role', 'is_active')
    list_select_related = ('role',)
    search_fields = ('guidance', 'role__slug', 'role__name')
