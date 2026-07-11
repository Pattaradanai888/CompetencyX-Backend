import uuid

from django.conf import settings
from django.db import models

from roadmaps.models import Question, QuestionOption, Role


class AssessmentSessionQuerySet(models.QuerySet):
    """Reusable read-path optimizations shared across assessment-session views."""

    def with_roles(self):
        return self.select_related('preferred_role', 'current_role', 'best_fit_role')

    def with_results(self):
        return self.with_roles().prefetch_related(
            'recommendations__role',
            'recommendations__topic',
        )

    def with_history(self):
        return self.prefetch_related(
            'answers__question__topic',
            'answers__selected_option',
            'recommendations__role',
            'recommendations__topic',
        )


class AssessmentSession(models.Model):
    class Language(models.TextChoices):
        EN = 'en', 'English'
        TH = 'th', 'Thai'

    class Status(models.TextChoices):
        IN_PROGRESS = 'in_progress', 'In Progress'
        COMPLETED = 'completed', 'Completed'

    class Phase(models.TextChoices):
        ROLE_DISCOVERY = 'role_discovery', 'Role Discovery'
        RECOMMENDATION_READY = 'recommendation_ready', 'Recommendation Ready'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='assessment_sessions',
    )
    preferred_role = models.ForeignKey(
        Role,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='preferred_sessions',
    )
    current_role = models.ForeignKey(
        Role,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='current_sessions',
    )
    best_fit_role = models.ForeignKey(
        Role,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='best_fit_sessions',
    )
    status = models.CharField(
        max_length=24,
        choices=Status.choices,
        default=Status.IN_PROGRESS,
    )
    phase = models.CharField(
        max_length=32,
        choices=Phase.choices,
        default=Phase.ROLE_DISCOVERY,
    )
    best_fit_confidence = models.FloatField(default=0.0)
    language = models.CharField(
        max_length=8,
        choices=Language.choices,
        default=Language.EN,
    )
    profile = models.JSONField(default=dict, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    objects = AssessmentSessionQuerySet.as_manager()

    class Meta:
        ordering = ['-started_at']

    def __str__(self) -> str:
        return str(self.id)


class Answer(models.Model):
    class Confidence(models.TextChoices):
        LOW = 'low', 'Low'
        MEDIUM = 'medium', 'Medium'
        HIGH = 'high', 'High'

    session = models.ForeignKey(
        AssessmentSession,
        on_delete=models.CASCADE,
        related_name='answers',
    )
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name='answers',
    )
    selected_option = models.ForeignKey(
        QuestionOption,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='answers',
    )
    scale_value = models.SmallIntegerField(null=True, blank=True)
    response_time_ms = models.PositiveIntegerField(null=True, blank=True)
    confidence_indicator = models.CharField(
        max_length=16,
        choices=Confidence.choices,
        blank=True,
    )
    responded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['responded_at']
        unique_together = [('session', 'question')]

    def __str__(self) -> str:
        return f'{self.session_id}:{self.question_id}'


class Survey2Question(models.Model):
    question_id = models.SlugField(max_length=64, unique=True)
    prompt = models.TextField()
    translations = models.JSONField(default=dict, blank=True)
    dimension_key = models.SlugField(max_length=64)
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['display_order', 'question_id']

    def __str__(self) -> str:
        return self.question_id


class Survey2Dimension(models.Model):
    class Track(models.TextChoices):
        PSP = 'psp', 'PSP'
        SDLC = 'sdlc', 'SDLC'

    dimension_key = models.SlugField(max_length=64, unique=True)
    label = models.CharField(max_length=128)
    track = models.CharField(max_length=16, choices=Track.choices)
    low_score_action = models.TextField()
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['display_order', 'dimension_key']

    def __str__(self) -> str:
        return self.dimension_key


class Survey2RoleGuidance(models.Model):
    role = models.ForeignKey(
        Role,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='survey2_guidance_items',
    )
    guidance = models.TextField()
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['role__slug', 'display_order', 'id']

    def __str__(self) -> str:
        role_slug = self.role.slug if self.role_id else 'default'
        return f'{role_slug}:{self.display_order}'


class Survey2QuestionQValue(models.Model):
    state_key = models.CharField(max_length=255)
    question_id = models.SlugField(max_length=64)
    q_value = models.FloatField(default=0.0)
    reward_total = models.FloatField(default=0.0)
    update_count = models.PositiveIntegerField(default=0)
    last_reward = models.FloatField(default=0.0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['state_key', 'question_id']
        unique_together = [('state_key', 'question_id')]

    def __str__(self) -> str:
        return f'{self.state_key}:{self.question_id}:{self.q_value:.4f}'
