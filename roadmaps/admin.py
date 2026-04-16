from django.contrib import admin

from .models import Question, QuestionOption, RoadmapTopic, Role, TopicPrerequisite


class QuestionOptionInline(admin.TabularInline):
    model = QuestionOption
    extra = 1


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(RoadmapTopic)
class RoadmapTopicAdmin(admin.ModelAdmin):
    list_display = ('title', 'role', 'difficulty', 'display_order', 'is_active')
    list_filter = ('role', 'difficulty', 'is_active')
    search_fields = ('title', 'slug')
    list_select_related = ('role', 'parent')
    prepopulated_fields = {'slug': ('title',)}


@admin.register(TopicPrerequisite)
class TopicPrerequisiteAdmin(admin.ModelAdmin):
    list_display = ('topic', 'prerequisite', 'required_mastery_threshold', 'dependency_weight')
    list_select_related = ('topic', 'prerequisite')


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('code', 'stage', 'role', 'topic', 'question_type', 'is_active')
    list_filter = ('stage', 'question_type', 'is_active', 'role')
    search_fields = ('code', 'prompt')
    list_select_related = ('role', 'topic')
    inlines = [QuestionOptionInline]
