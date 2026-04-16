from django.db import models

from roadmaps.models import RoadmapTopic, Role


class Recommendation(models.Model):
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
    policy_type = models.CharField(
        max_length=32,
        choices=PolicyType.choices,
        default=PolicyType.RULE_BASED,
    )
    score = models.FloatField(default=0.0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f'{self.session_id}:{self.topic_id or "none"}'
