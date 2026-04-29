from django.contrib import admin

from .models import Answer, AssessmentSession, QuestionBanditStat, QuestionSelectionEvent, TopicMastery


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
