from django.db import models


class Role(models.Model):
    slug = models.SlugField(max_length=64, unique=True)
    name = models.CharField(max_length=128)
    description = models.TextField(blank=True)
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

    class Type(models.TextChoices):
        YES_NO = 'yes_no', 'Yes / No'
        YES_NO_MAYBE = 'yes_no_maybe', 'Yes / No / Maybe'
        SINGLE_CHOICE = 'single_choice', 'Single Choice'
        RANKED_CHOICE = 'ranked_choice', 'Ranked Choice'

    code = models.SlugField(max_length=96, unique=True)
    stage = models.CharField(max_length=16, choices=Stage.choices)
    question_type = models.CharField(max_length=24, choices=Type.choices)
    prompt = models.TextField()
    help_text = models.TextField(blank=True)
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
    mastery_value = models.FloatField(default=0.0)
    role_weights = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['display_order', 'id']
        unique_together = [('question', 'key')]

    def __str__(self) -> str:
        return f'{self.question.code}:{self.key}'
