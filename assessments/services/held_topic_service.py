"""Held Topic marks: the respondent's statement that they can already do a set.

Marks belong to the account rather than the session (ADR-0003): a statement
about what a person can do follows the person, so it survives a device change
and is in effect in every session that person starts.
"""

from rest_framework.exceptions import NotFound

from assessments.models import AssessableTopicSet, HeldTopicMark


UNKNOWN_TOPIC_SET_MESSAGE = 'Unknown Assessable Topic Set.'


def _topic_set_or_404(topic_set_key: str) -> AssessableTopicSet:
    try:
        return AssessableTopicSet.objects.get(set_key=topic_set_key)
    except AssessableTopicSet.DoesNotExist as exc:
        raise NotFound({'topic_key': UNKNOWN_TOPIC_SET_MESSAGE}) from exc


def mark_topic_held(user, topic_set_key: str) -> AssessableTopicSet:
    """Record the statement, idempotently; the set must exist to be markable."""
    topic_set = _topic_set_or_404(topic_set_key)
    HeldTopicMark.objects.get_or_create(user=user, topic_set=topic_set)
    return topic_set


def unmark_topic_held(user, topic_set_key: str) -> AssessableTopicSet:
    """Withdraw the statement; unmarking something never marked is not an error."""
    topic_set = _topic_set_or_404(topic_set_key)
    HeldTopicMark.objects.filter(user=user, topic_set=topic_set).delete()
    return topic_set


def get_held_topic_keys(user) -> frozenset[str]:
    """The set keys the account has marked as already held."""
    if user is None or not getattr(user, 'is_authenticated', False):
        return frozenset()
    return frozenset(HeldTopicMark.objects.filter(user=user).values_list('topic_set__set_key', flat=True))
