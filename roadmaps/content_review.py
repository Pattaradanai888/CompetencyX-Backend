"""The review block every authored content item carries.

A Role Discovery question, a relevance-mapping role, and an Assessable Topic
Set all record where the human review of their Canonical Thai Wording stands
as ``review: {status: draft | reviewed}``. An agent may write ``draft``; only a
person sets ``reviewed`` (ADR-0004). Each catalog reads the block the same way
so the two statuses mean one thing everywhere.
"""

DRAFT = 'draft'
REVIEWED = 'reviewed'
VALID_REVIEW_STATUSES = frozenset({DRAFT, REVIEWED})


def read_review_status(entry: dict) -> str | None:
    """The status an item declares, or ``None`` when the block is missing or malformed.

    ``review: draft`` (a scalar where a mapping is expected) is the obvious
    authoring slip, so it reads as missing rather than raising.
    """
    review = entry.get('review')
    return review.get('status') if isinstance(review, dict) else None


def is_reviewed(entry: dict) -> bool:
    return read_review_status(entry) == REVIEWED


def invalid_review_status_message(subject: str, status: str | None) -> str:
    """The one-line error for an item whose status is not ``draft`` or ``reviewed``."""
    return f'{subject} review.status must be one of {sorted(VALID_REVIEW_STATUSES)} (got: {status!r}).'
