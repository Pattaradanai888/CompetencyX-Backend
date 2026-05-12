from django.db import models

from roadmaps.models import RoadmapTopic, Role


class Recommendation(models.Model):
    class PathKind(models.TextChoices):
        PREFERRED = 'preferred', 'Preferred Role Path'
        BEST_FIT = 'best_fit', 'Best-Fit Role Path'

    class PolicyType(models.TextChoices):
        RULE_BASED = 'rule_based', 'Rule Based'
        BANDIT = 'bandit', 'Bandit'
        Q_LEARNING = 'q_learning', 'Q Learning'

    session = models.ForeignKey(
        'assessments.AssessmentSession',
        on_delete=models.CASCADE,
        related_name='recommendations',
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name='recommendations',
    )
    topic = models.ForeignKey(
        RoadmapTopic,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='recommendations',
    )
    reason = models.TextField()
    path_kind = models.CharField(
        max_length=24,
        choices=PathKind.choices,
        default=PathKind.PREFERRED,
    )
    policy_type = models.CharField(
        max_length=32,
        choices=PolicyType.choices,
        default=PolicyType.RULE_BASED,
    )
    score = models.FloatField(default=0.0)
    state_key = models.CharField(max_length=255, blank=True)
    feedback_reward_applied = models.BooleanField(default=False)
    feedback_reward_applied_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f'{self.session_id}:{self.topic_id or "none"}'


class RecommendationQValue(models.Model):
    state_key = models.CharField(max_length=255)
    path_kind = models.CharField(
        max_length=24,
        choices=Recommendation.PathKind.choices,
        default=Recommendation.PathKind.PREFERRED,
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name='recommendation_q_values',
    )
    topic = models.ForeignKey(
        RoadmapTopic,
        on_delete=models.CASCADE,
        related_name='recommendation_q_values',
    )
    q_value = models.FloatField(default=0.0)
    reward_total = models.FloatField(default=0.0)
    update_count = models.PositiveIntegerField(default=0)
    last_reward = models.FloatField(default=0.0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['state_key', 'path_kind', 'role__slug', 'topic__display_order', 'topic__id']
        unique_together = [('state_key', 'path_kind', 'role', 'topic')]

    def __str__(self) -> str:
        return f'{self.state_key}:{self.path_kind}:{self.role.slug}:{self.topic.slug}'
