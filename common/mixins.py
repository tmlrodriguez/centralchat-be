from django.conf import settings
from django.db import models

# Define your mixins here.

class TemporalMixin(models.Model):
    """
    DOCSTRING: Temporal Mixin

    Description:
    - Provide standard creation and modification timestamps for CentralChat models.

    Notes:
    - created_at is assigned automatically when the record is created.
    - updated_at is refreshed automatically whenever the record is saved.
    - The mixin is abstract and does not create its own database table.
    """
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class LifeCycleMixin(models.Model):
    """
    DOCSTRING: Life Cycle Mixin

    Description:
    - Provide the standard active lifecycle state for CentralChat models.

    Notes:
    - Records should normally be deactivated instead of destructively deleted when historical integrity matters.
    - The mixin is abstract and does not create its own database table.
    """
    is_active = models.BooleanField(default=True)

    class Meta:
        abstract = True


class AuthorMixin(models.Model):
    """
    DOCSTRING: Author Mixin

    Description:
    - Record the CentralChat users responsible for creating and last updating a model record.

    Notes:
    - Author relationships are nullable to support migrations, system processes, and records created without an authenticated actor.
    - Deleting a user must not delete the authored business record.
    - The mixin is abstract and does not create its own database table.
    """
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, blank=True, null=True, on_delete=models.SET_NULL, related_name="%(app_label)s_%(class)s_created_records")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, blank=True, null=True, on_delete=models.SET_NULL, related_name="%(app_label)s_%(class)s_updated_records")

    class Meta:
        abstract = True