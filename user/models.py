"""
user/models.py
==============
Authentication system: Roles, Users (AbstractBaseUser), and Sessions.

Design decisions
----------------
* CustomUser extends AbstractBaseUser for full control over auth fields.
* Roles are stored as strings (not ENUM) for flexibility and easy migration.
* Sessions capture rich device/geo metadata per request.
* All tables participate in soft-delete via SoftDeleteMixin.
"""

import uuid
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models

from core.mixins import SoftDeleteMixin, ActiveManager, AllObjectsManager


# ===========================================================================
# ROLE
# ===========================================================================

class Role(SoftDeleteMixin):
    """
    Lookup table for user roles.
    Stored as plain strings (not DB ENUM) so new roles require no migration.

    Examples: ADMIN, DEV, CUSTOMER, STAFF, SUPERVISOR, INVENTORY_MANAGER
    """

    ROLE_CHOICES = [
        ("ADMIN", "Admin"),
        ("DEV", "Developer"),
        ("CUSTOMER", "Customer"),
        ("STAFF", "Staff"),
        ("SUPERVISOR", "Supervisor"),
        ("INVENTORY_MANAGER", "Inventory Manager"),
    ]

    role_name = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        choices=ROLE_CHOICES,
        verbose_name="Role Name",
    )

    class Meta:
        db_table = "roles"
        verbose_name = "Role"
        verbose_name_plural = "Roles"
        ordering = ["role_name"]

    def __str__(self):
        return self.role_name


# ===========================================================================
# CUSTOM USER MANAGER
# ===========================================================================

class CustomUserManager(BaseUserManager):
    """
    Manager for CustomUser.
    Overrides create_user / create_superuser to use email as the unique
    identifier instead of username.
    """

    def _create_user(self, username, email, mobile, password, **extra_fields):
        if not email:
            raise ValueError("Email is required.")
        if not username:
            raise ValueError("Username is required.")
        email = self.normalize_email(email)
        user = self.model(username=username, email=email, mobile=mobile, **extra_fields)
        user.set_password(password)  # hashes with PBKDF2 by default
        user.save(using=self._db)
        return user

    def create_user(self, username, email, mobile, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(username, email, mobile, password, **extra_fields)

    def create_superuser(self, username, email, mobile, password, **extra_fields):
        extra_fields["is_staff"] = True
        extra_fields["is_superuser"] = True
        return self._create_user(username, email, mobile, password, **extra_fields)

    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


class AllUsersManager(BaseUserManager):
    """Unfiltered manager including soft-deleted users."""

    def get_queryset(self):
        return super().get_queryset()


# ===========================================================================
# CUSTOM USER
# ===========================================================================

class CustomUser(AbstractBaseUser, PermissionsMixin):
    """
    Central authentication model.

    Extends AbstractBaseUser so Django handles password hashing and
    session auth properly.  PermissionsMixin adds groups / permissions.

    USERNAME_FIELD = 'username'  (used by authenticate())
    REQUIRED_FIELDS used by createsuperuser CLI.
    """

    # --- Identification ---
    urid = models.UUIDField(
        default=uuid.uuid4, editable=False, unique=True, db_index=True,
        verbose_name="Unique Record ID",
    )

    username = models.CharField(
        max_length=150, unique=True, db_index=True, verbose_name="Username"
    )
    email = models.EmailField(
        max_length=255, unique=True, db_index=True, verbose_name="Email"
    )
    mobile = models.CharField(
        max_length=20, unique=True, db_index=True, verbose_name="Mobile Number"
    )

    # --- Profile ---
    avatar = models.ImageField(
        upload_to="avatars/%Y/%m/", null=True, blank=True, verbose_name="Avatar"
    )

    # --- Role ---
    role = models.ForeignKey(
        Role,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="users",
        db_index=True,
        verbose_name="Role",
    )

    # --- Django auth flags ---
    is_active = models.BooleanField(default=True, verbose_name="Is Active")
    is_staff = models.BooleanField(default=False, verbose_name="Is Staff")
    is_superuser = models.BooleanField(default=False, verbose_name="Is Superuser")

    # --- Soft delete & timestamps ---
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    is_deleted = models.BooleanField(default=False, db_index=True)
    created_by_ip = models.GenericIPAddressField(null=True, blank=True)
    updated_by_ip = models.GenericIPAddressField(null=True, blank=True)

    # --- Manager ---
    objects = CustomUserManager()
    all_objects = AllUsersManager()

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = ["email", "mobile"]

    class Meta:
        db_table = "user"
        verbose_name = "User"
        verbose_name_plural = "Users"
        indexes = [
            models.Index(fields=["username"]),
            models.Index(fields=["email"]),
            models.Index(fields=["mobile"]),
            models.Index(fields=["role"]),
            models.Index(fields=["is_deleted"]),
        ]

    def __str__(self):
        return f"{self.username} <{self.email}>"

    def soft_delete(self, ip=None):
        from django.utils import timezone
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.is_active = False
        if ip:
            self.updated_by_ip = ip
        self.save(update_fields=["is_deleted", "deleted_at", "is_active", "updated_by_ip", "updated_at"])

    def restore(self, ip=None):
        self.is_deleted = False
        self.deleted_at = None
        self.is_active = True
        if ip:
            self.updated_by_ip = ip
        self.save(update_fields=["is_deleted", "deleted_at", "is_active", "updated_by_ip", "updated_at"])


# ===========================================================================
# SESSION
# ===========================================================================

class Session(SoftDeleteMixin):
    """
    Captures rich request/session metadata per authenticated action.

    geo_location stores city + country as JSON, e.g.:
        {"city": "Mumbai", "country": "IN", "lat": 19.07, "lng": 72.87}

    device_info stores parsed UA data, e.g.:
        {"browser": "Chrome", "os": "Android", "device": "mobile"}
    """

    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="sessions",
        db_index=True,
        verbose_name="User",
    )

    ip_address = models.GenericIPAddressField(
        db_index=True, verbose_name="IP Address"
    )

    # JSON stores {"city": ..., "country": ..., "lat": ..., "lng": ...}
    geo_location = models.JSONField(
        null=True, blank=True, verbose_name="Geo Location"
    )

    user_agent = models.TextField(blank=True, verbose_name="User Agent String")

    # Parsed device metadata
    device_info = models.JSONField(
        null=True, blank=True, verbose_name="Device Info"
    )

    class Meta:
        db_table = "session"
        verbose_name = "Session"
        verbose_name_plural = "Sessions"
        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["ip_address"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"Session [{self.user}] @ {self.ip_address} ({self.created_at:%Y-%m-%d %H:%M})"
