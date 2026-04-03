"""
core/mixins.py
==============
Shared base mixin for all models across the project.
Provides: UUID primary key, timestamps, IP tracking, and soft-delete support.
"""

import uuid
from django.db import models
from django.utils import timezone


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def get_client_ip(request):
    """Extract real IP from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')

    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()

    return request.META.get('REMOTE_ADDR')

# ---------------------------------------------------------------------------
# Managers
# ---------------------------------------------------------------------------

class ActiveManager(models.Manager):
    """Default manager — returns only non-deleted records."""

    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


class AllObjectsManager(models.Manager):
    """Unfiltered manager — returns every record including soft-deleted ones."""

    def get_queryset(self):
        return super().get_queryset()

# ---------------------------------------------------------------------------
# Mixin
# ---------------------------------------------------------------------------

class SoftDeleteMixin(models.Model):
    """
    Abstract base mixin applied to EVERY model in this project.

    Fields
    ------
    urid          : Universally unique record identifier (UUID4).
    created_at    : Auto-set on first save.
    updated_at    : Auto-updated on every save.
    deleted_at    : Set when the record is soft-deleted; NULL means active.
    is_deleted    : Boolean flag for fast filtering.
    created_by_ip : IP address of the client that created the record.
    updated_by_ip : IP address of the client that last modified the record.
    """

    urid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        db_index=True,
        verbose_name="Unique Record ID",
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created At")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Updated At")
    deleted_at = models.DateTimeField(
        null=True, blank=True, verbose_name="Deleted At"
    )

    is_deleted = models.BooleanField(
        default=False, db_index=True, verbose_name="Is Deleted"
    )

    created_by_ip = models.GenericIPAddressField(
        null=True, blank=True, verbose_name="Created By IP"
    )
    updated_by_ip = models.GenericIPAddressField(
        null=True, blank=True, verbose_name="Updated By IP"
    )

    # ------------------------------------------------------------------
    # Managers
    # ------------------------------------------------------------------
    objects = ActiveManager()        # default: active records only
    all_objects = AllObjectsManager()  # includes soft-deleted records

    # ------------------------------------------------------------------
    # Soft-delete helpers
    # ------------------------------------------------------------------

    def soft_delete(self, ip: str | None = None):
        """Mark record as deleted without removing from DB."""
        self.is_deleted = True
        self.deleted_at = timezone.now()
        if ip:
            self.updated_by_ip = ip
        self.save(update_fields=["is_deleted", "deleted_at", "updated_by_ip", "updated_at"])

    def restore(self, ip: str | None = None):
        """Restore a previously soft-deleted record."""
        self.is_deleted = False
        self.deleted_at = None
        if ip:
            self.updated_by_ip = ip
        self.save(update_fields=["is_deleted", "deleted_at", "updated_by_ip", "updated_at"])

    class Meta:
        abstract = True
