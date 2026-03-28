# core/mixins.py

import uuid
from django.db import models
from django.utils import timezone


def generate_urid():
    return str(uuid.uuid4())


def get_client_ip(request):
    """Extract real IP from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')

    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()

    return request.META.get('REMOTE_ADDR')


class ActiveManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_active=True)


class SoftDeleteMixin(models.Model):
    # 🔑 Unique ID (like your TH_urid)
    urid = models.CharField(
        max_length=36,
        unique=True,
        db_index=True,
        default=generate_urid,
        editable=False
    )

    # ⏱️ Time tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    # 🌐 IP tracking
    created_ip = models.GenericIPAddressField(null=True, blank=True)
    updated_ip = models.GenericIPAddressField(null=True, blank=True)
    deleted_ip = models.GenericIPAddressField(null=True, blank=True)

    # 🔥 Soft delete flag
    is_active = models.BooleanField(default=True)

    # Managers
    objects = ActiveManager()        # only active
    all_objects = models.Manager()  # includes deleted

    class Meta:
        abstract = True

    # ------------------------
    # 🔥 SOFT DELETE
    # ------------------------
    def soft_delete(self, request=None):
        self.deleted_at = timezone.now()
        self.is_active = False

        if request:
            self.deleted_ip = get_client_ip(request)

        self.save()

    # ------------------------
    # 🔥 RESTORE
    # ------------------------
    def restore(self):
        self.deleted_at = None
        self.is_active = True
        self.save()

    # ------------------------
    # 💀 HARD DELETE
    # ------------------------
    def hard_delete(self):
        super().delete()

    # ------------------------
    # AUTO TRACK IP ON SAVE
    # ------------------------
    def save(self, *args, **kwargs):
        request = kwargs.pop('request', None)

        if request:
            ip = get_client_ip(request)

            if not self.pk:
                self.created_ip = ip

            self.updated_ip = ip

        super().save(*args, **kwargs)