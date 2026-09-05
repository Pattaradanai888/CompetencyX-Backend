from django.contrib import admin

from .models import (
    Answer,
    AssessableTopicSet,
    AssessmentSession,
    HeldTopicMark,
    SkillAssessmentDimension,
    SkillAssessmentQuestion,
    SkillAssessmentRoleGuidance,
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


@admin.register(SkillAssessmentQuestion)
class SkillAssessmentQuestionAdmin(admin.ModelAdmin):
    list_display = ('question_id', 'dimension_key', 'display_order', 'is_active', 'updated_at')
    list_filter = ('dimension_key', 'is_active')
    search_fields = ('question_id', 'prompt')


@admin.register(SkillAssessmentDimension)
class SkillAssessmentDimensionAdmin(admin.ModelAdmin):
    list_display = ('dimension_key', 'role', 'label', 'display_order', 'is_active', 'updated_at')
    list_filter = ('role', 'is_active')
    list_select_related = ('role',)
    search_fields = ('dimension_key', 'label', 'low_score_action')


@admin.register(SkillAssessmentRoleGuidance)
class SkillAssessmentRoleGuidanceAdmin(admin.ModelAdmin):
    list_display = ('role', 'display_order', 'is_active', 'updated_at')
    list_filter = ('role', 'is_active')
    list_select_related = ('role',)
    search_fields = ('guidance', 'role__slug', 'role__name')


@admin.register(AssessableTopicSet)
class AssessableTopicSetAdmin(admin.ModelAdmin):
    list_display = ('set_key', 'role', 'title', 'display_order', 'is_active', 'updated_at')
    list_filter = ('role', 'is_active')
    list_select_related = ('role',)
    search_fields = ('set_key', 'title', 'title_th', 'role__slug')
    filter_horizontal = ('nodes',)


@admin.register(HeldTopicMark)
class HeldTopicMarkAdmin(admin.ModelAdmin):
    list_display = ('user', 'topic_set', 'marked_at')
    list_select_related = ('user', 'topic_set')
    search_fields = ('user__email', 'topic_set__set_key')
