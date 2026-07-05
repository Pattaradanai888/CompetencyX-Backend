from django.contrib import admin

from .models import (
    Answer,
    AssessmentSession,
    Survey2Dimension,
    Survey2Question,
    Survey2RoleGuidance,
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
