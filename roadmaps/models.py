from django.db import models


class Role(models.Model):
    slug = models.SlugField(max_length=64, unique=True)
    name = models.CharField(max_length=128)
    description = models.TextField(blank=True)
    top_ka_codes = models.JSONField(default=list, blank=True)
    core_tasks = models.JSONField(default=list, blank=True)
    swebok_source_version = models.CharField(max_length=32, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self) -> str:
        return self.name


class RoadmapTopic(models.Model):
    class Difficulty(models.TextChoices):
        BEGINNER = 'beginner', 'Beginner'
        INTERMEDIATE = 'intermediate', 'Intermediate'
        ADVANCED = 'advanced', 'Advanced'

    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name='topics',
    )
    parent = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='children',
    )
    slug = models.SlugField(max_length=96)
    title = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    external_source = models.CharField(max_length=64, blank=True)
    external_id = models.CharField(max_length=128, blank=True)
    external_slug = models.CharField(max_length=128, blank=True)
    source_version = models.CharField(max_length=64, blank=True)
    difficulty = models.CharField(
        max_length=16,
        choices=Difficulty.choices,
        default=Difficulty.BEGINNER,
    )
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['role__name', 'display_order', 'title']
        unique_together = [('role', 'slug')]

    def __str__(self) -> str:
        return f'{self.role.name}: {self.title}'


class TopicPrerequisite(models.Model):
    topic = models.ForeignKey(
        RoadmapTopic,
        on_delete=models.CASCADE,
        related_name='prerequisites',
    )
    prerequisite = models.ForeignKey(
        RoadmapTopic,
        on_delete=models.CASCADE,
        related_name='unlocks',
    )
    required_mastery_threshold = models.FloatField(default=0.7)
    dependency_weight = models.FloatField(default=1.0)

    class Meta:
        unique_together = [('topic', 'prerequisite')]
        ordering = ['topic__role__name', 'topic__display_order']

    def __str__(self) -> str:
        return f'{self.prerequisite} -> {self.topic}'


class Question(models.Model):
    class Stage(models.TextChoices):
        ROLE = 'role', 'Role Discovery'
        SKILL = 'skill', 'Skill Estimation'

    class ItemGroup(models.TextChoices):
        CORE = 'core', 'Core'
        TIE_BREAK = 'tie_break', 'Tie Break'
        STANDARD = 'standard', 'Standard'

    class Type(models.TextChoices):
        YES_NO = 'yes_no', 'Yes / No'
        YES_NO_MAYBE = 'yes_no_maybe', 'Yes / No / Maybe'
        LIKERT_5 = 'likert_5', 'Five-Point Agreement Scale'
        SINGLE_CHOICE = 'single_choice', 'Single Choice'
        RANKED_CHOICE = 'ranked_choice', 'Ranked Choice'

    code = models.SlugField(max_length=96, unique=True)
    stage = models.CharField(max_length=16, choices=Stage.choices)
    question_type = models.CharField(max_length=24, choices=Type.choices)
    prompt = models.TextField()
    help_text = models.TextField(blank=True)
    translations = models.JSONField(default=dict, blank=True)
    role = models.ForeignKey(
        Role,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='questions',
    )
    topic = models.ForeignKey(
        RoadmapTopic,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='questions',
    )
    difficulty = models.PositiveSmallIntegerField(default=1)
    discrimination_score = models.FloatField(default=1.0)
    item_group = models.CharField(
        max_length=16,
        choices=ItemGroup.choices,
        default=ItemGroup.STANDARD,
    )
    discriminates_between = models.JSONField(default=list, blank=True)
    agree_dimension_signals = models.JSONField(default=dict, blank=True)
    disagree_dimension_signals = models.JSONField(default=dict, blank=True)
    trait_positive_dimension = models.SlugField(max_length=64, blank=True)
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['stage', 'display_order', '-discrimination_score', 'id']

    def __str__(self) -> str:
        return self.prompt[:80]


class QuestionOption(models.Model):
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name='options',
    )
    key = models.SlugField(max_length=64)
    label = models.CharField(max_length=160)
    value = models.CharField(max_length=64, blank=True)
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['display_order', 'id']
        unique_together = [('question', 'key')]

    def __str__(self) -> str:
        return f'{self.question.code}:{self.key}'


class QuestionTopicSignal(models.Model):
    question_option = models.ForeignKey(
        QuestionOption,
        on_delete=models.CASCADE,
        related_name='topic_signals',
    )
    topic = models.ForeignKey(
        RoadmapTopic,
        on_delete=models.CASCADE,
        related_name='question_topic_signals',
    )
    mastery_delta = models.FloatField(default=0.0)

    class Meta:
        ordering = ['question_option__question__code', 'topic__slug']
        unique_together = [('question_option', 'topic')]

    def __str__(self) -> str:
        return f'{self.question_option} -> {self.topic.slug}: {self.mastery_delta}'
