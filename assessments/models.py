import uuid

from django.conf import settings
from django.db import models

from roadmaps.models import Question, QuestionOption, RoadmapTopic, Role


class AssessmentSession(models.Model):
    class Status(models.TextChoices):
        IN_PROGRESS = 'in_progress', 'In Progress'
        COMPLETED = 'completed', 'Completed'

    class Phase(models.TextChoices):
        ROLE_DISCOVERY = 'role_discovery', 'Role Discovery'
        SKILL_ASSESSMENT = 'skill_assessment', 'Skill Assessment'
        RECOMMENDATION_READY = 'recommendation_ready', 'Recommendation Ready'
        COMPLETED = 'completed', 'Completed'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='assessment_sessions',
    )
    selected_role = models.ForeignKey(
        Role,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='selected_sessions',
    )
    inferred_role = models.ForeignKey(
        Role,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='inferred_sessions',
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
    role_confidence = models.FloatField(default=0.0)
    profile = models.JSONField(default=dict, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

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
        on_delete=models.CASCADE,
        related_name='answers',
    )
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


class TopicMastery(models.Model):
    session = models.ForeignKey(
        AssessmentSession,
        on_delete=models.CASCADE,
        related_name='mastery_scores',
    )
    topic = models.ForeignKey(
        RoadmapTopic,
        on_delete=models.CASCADE,
        related_name='session_mastery_scores',
    )
    mastery_score = models.FloatField(default=0.0)
    confidence_score = models.FloatField(default=0.0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['topic__display_order', 'topic__id']
        unique_together = [('session', 'topic')]

    def __str__(self) -> str:
        return f'{self.session_id}:{self.topic_id}'
