import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """The account a respondent signs in with.

    Django's own user model — username, email, password hashing, permissions —
    keyed by a UUID rather than a sequential integer, so an account identifier
    appearing in a URL or a payload discloses neither how many accounts exist
    nor the order they were created in. The identifier a respondent signs in
    with is their email; it is stored in ``username`` as well, which is what
    makes one account per email a database guarantee rather than a check.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
