from django.contrib import admin

from .models import Recommendation


@admin.register(Recommendation)
class RecommendationAdmin(admin.ModelAdmin):
    list_display = ('session', 'role', 'topic', 'policy_type', 'score', 'created_at')
    list_filter = ('policy_type', 'role')
    list_select_related = ('session', 'role', 'topic')
