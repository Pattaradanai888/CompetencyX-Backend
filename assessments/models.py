import uuid

from django.conf import settings
from django.db import models

from roadmaps.models import Question, QuestionOption, Role


class AssessmentSessionQuerySet(models.QuerySet):
    """Reusable read-path optimizations shared across assessment-session views."""

    def with_roles(self):
        return self.select_related('preferred_role', 'current_role', 'best_fit_role')

    def with_history(self):
        return self.prefetch_related(
            'answers__question__topic',
            'answers__selected_option',
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
    skill_assessment_completed = models.BooleanField(default=False)
    skill_assessment_completed_at = models.DateTimeField(null=True, blank=True)
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


class SkillAssessmentQuestion(models.Model):
    """One Skill Assessment item.

    An item either names a topic from a role's roadmap (``role`` and
    ``topic_slug`` set) or is a role-independent fallback item (both empty).
    Topic-anchored items are what make the assessment measure readiness *for a
    role*: the object the respondent rates is the object the roadmap orders and
    the recommendation names. See ADR-0002.
    """

    question_id = models.SlugField(max_length=128, unique=True)
    role = models.ForeignKey(
        'roadmaps.Role',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='skill_assessment_questions',
    )
    topic_slug = models.SlugField(max_length=200, blank=True, default='')
    topic_title = models.CharField(max_length=255, blank=True, default='')
    prompt = models.TextField()
    translations = models.JSONField(default=dict, blank=True)
    dimension_key = models.SlugField(max_length=128)
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['display_order', 'question_id']

    def __str__(self) -> str:
        return self.question_id


class SkillAssessmentDimension(models.Model):
    class Track(models.TextChoices):
        PSP = 'psp', 'PSP'
        SDLC = 'sdlc', 'SDLC'

    dimension_key = models.SlugField(max_length=128, unique=True)
    role = models.ForeignKey(
        'roadmaps.Role',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='skill_assessment_dimensions',
    )
    label = models.CharField(max_length=255)
    track = models.CharField(max_length=16, choices=Track.choices)
    low_score_action = models.TextField()
    translations = models.JSONField(default=dict, blank=True)
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['display_order', 'dimension_key']

    def __str__(self) -> str:
        return self.dimension_key


class SkillAssessmentRoleGuidance(models.Model):
    role = models.ForeignKey(
        Role,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='skill_assessment_guidance_items',
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


class SkillAssessmentAnswer(models.Model):
    """One Skill Assessment self-rating per session and catalog question.

    ``question_id`` is the catalog slug rather than a foreign key so answers
    survive catalog questions being deactivated or removed.
    """

    session = models.ForeignKey(
        AssessmentSession,
        on_delete=models.CASCADE,
        related_name='skill_assessment_answers',
    )
    question_id = models.SlugField(max_length=128)
    value = models.SmallIntegerField()
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['question_id']
        unique_together = [('session', 'question_id')]

    def __str__(self) -> str:
        return f'{self.session_id}:{self.question_id}={self.value}'


class AssessableTopicSet(models.Model):
    """A reviewed cluster of a role's roadmap topics, rated as one question.

    The assessable unit used to be read off the imported graph -- the first
    twelve nodes whose ``node_type`` was ``topic``. That predicate is not
    "top-level": Cyber Security Engineer/Analyst was assessed with six items
    against 301 nodes, and Backend Developer was never asked about Git, PHP, Go
    or JavaScript, because those nodes carry a subtopic type with no parent
    (ADR-0003). A set is authored for the role instead, and names the group of
    nodes a Held statement applies to.

    ``key`` is the role-local key the content is authored under; ``set_key``
    prefixes it with the role slug so it is stable and unique across the whole
    catalog, and is what a Skill Assessment answer is recorded against.
    ``node_slugs`` keeps the authored intent even when a slug matches no
    imported node, so the catalog validation can report the mismatch rather
    than lose it; ``nodes`` holds what the slugs resolved to.
    """

    set_key = models.SlugField(max_length=128, unique=True)
    key = models.SlugField(max_length=128)
    role = models.ForeignKey(
        'roadmaps.Role',
        on_delete=models.CASCADE,
        related_name='assessable_topic_sets',
    )
    title = models.CharField(max_length=255)
    title_th = models.CharField(max_length=255, blank=True, default='')
    node_slugs = models.JSONField(default=list, blank=True)
    nodes = models.ManyToManyField(
        'roadmaps.ExternalRoadmapNode',
        blank=True,
        related_name='assessable_topic_sets',
    )
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['role__slug', 'display_order', 'set_key']
        unique_together = [('role', 'key')]

    def __str__(self) -> str:
        return self.set_key
