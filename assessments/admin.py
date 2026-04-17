from django.contrib import admin

from .models import Answer, AssessmentSession, TopicMastery


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
