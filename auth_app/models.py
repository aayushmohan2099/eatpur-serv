"""
auth_app/models.py
==================
Models for the authentication system.

1. CaptchaChallenge
   Server-generated text CAPTCHA stored in DB.
   No third-party services. Pure Django + MySQL.

2. LoginAttempt
   DB-backed rate limiting for login failures per IP.
   No Redis — pure DB queries with cleanup job.

These models inherit SoftDeleteMixin for consistency,
though hard-deletes are run periodically by a management command
to keep the table lean.
"""

import random
import string
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from core.mixins import SoftDeleteMixin


# ===========================================================================
# CaptchaChallenge
# ===========================================================================

def _generate_captcha_text() -> str:
    """
    Generate a random CAPTCHA string using the character set from settings.
    Excludes visually ambiguous characters (0/O, 1/I).
    """
    chars = getattr(settings, "CAPTCHA_CHARS", "ABCDEFGHJKLMNPQRSTUVWXYZ23456789")
    length = getattr(settings, "CAPTCHA_LENGTH", 6)
    return "".join(random.choices(chars, k=length))


def _captcha_expiry():
    """Return UTC datetime when this challenge expires."""
    minutes = getattr(settings, "CAPTCHA_EXPIRE_MINUTES", 5)
    return timezone.now() + timezone.timedelta(minutes=minutes)


class CaptchaChallenge(SoftDeleteMixin):
    """
    A single-use server-generated CAPTCHA challenge.

    Lifecycle
    ---------
    1. Client requests GET /auth/captcha/
       → A new CaptchaChallenge is created; captcha_id + text returned.
    2. Client submits login with captcha_id + captcha_answer.
       → CaptchaChallenge.validate(answer) is called.
    3. On successful match: is_used = True, can never be reused.
    4. Expired or used challenges are rejected immediately.

    Security properties
    -------------------
    * One-time use: is_used flag prevents replay.
    * Time-limited: expires_at prevents hoarding challenges.
    * Case-insensitive by default (configurable via CAPTCHA_CASE_SENSITIVE).
    * Soft-deleted after use for audit trail.
    """

    captcha_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name="CAPTCHA ID",
    )
    captcha_text = models.CharField(
        max_length=10,
        default=_generate_captcha_text,
        verbose_name="CAPTCHA Text",
    )
    expires_at = models.DateTimeField(
        default=_captcha_expiry,
        db_index=True,
        verbose_name="Expires At",
    )
    is_used = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name="Is Used",
    )
    # Track which IP requested this challenge (abuse prevention)
    requested_by_ip = models.GenericIPAddressField(
        null=True, blank=True, verbose_name="Requested By IP"
    )

    class Meta:
        db_table = "captcha_challenge"
        verbose_name = "CAPTCHA Challenge"
        verbose_name_plural = "CAPTCHA Challenges"
        indexes = [
            models.Index(fields=["expires_at", "is_used"]),
        ]

    def __str__(self):
        status = "used" if self.is_used else ("expired" if self.is_expired else "active")
        return f"CAPTCHA [{self.captcha_id}] — {status}"

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_expired(self) -> bool:
        return timezone.now() > self.expires_at

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate(self, answer: str) -> tuple[bool, str]:
        """
        Validate a user-supplied answer against this challenge.

        Returns
        -------
        (True,  "")        → valid
        (False, "reason")  → invalid, with human-readable reason

        Side effect: marks `is_used = True` on success (one-time use).
        """
        if self.is_used:
            return False, "This CAPTCHA has already been used."

        if self.is_expired:
            return False, "This CAPTCHA has expired. Please request a new one."

        case_sensitive = getattr(settings, "CAPTCHA_CASE_SENSITIVE", False)
        stored = self.captcha_text if case_sensitive else self.captcha_text.upper()
        given = answer.strip() if case_sensitive else answer.strip().upper()

        if stored != given:
            return False, "Incorrect CAPTCHA answer."

        # Mark used — prevent replay
        self.is_used = True
        self.save(update_fields=["is_used", "updated_at"])
        return True, ""

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def create_for_ip(cls, ip: str | None = None) -> "CaptchaChallenge":
        """Create and persist a new challenge for the given client IP."""
        return cls.objects.create(requested_by_ip=ip)


# ===========================================================================
# LoginAttempt — DB-backed rate limiting
# ===========================================================================

class LoginAttempt(models.Model):
    """
    Tracks failed login attempts per IP address.
    Used for DB-only rate limiting (no Redis).

    Strategy
    ---------
    * Count failed attempts within a rolling window (e.g. last 15 minutes).
    * Block the IP if attempts exceed MAX_ATTEMPTS.
    * Successful login resets the counter for that IP.
    * A periodic management command prunes old rows.

    Note: This is a simpler model (no SoftDeleteMixin) — rows are
    hard-deleted by the cleanup command since they have no audit value
    after they expire.
    """

    MAX_ATTEMPTS: int = 5
    WINDOW_MINUTES: int = 15

    ip_address = models.GenericIPAddressField(db_index=True, verbose_name="IP Address")
    attempted_at = models.DateTimeField(auto_now_add=True, db_index=True)
    username_tried = models.CharField(
        max_length=255, blank=True, verbose_name="Username Tried"
    )

    class Meta:
        db_table = "login_attempt"
        verbose_name = "Login Attempt"
        verbose_name_plural = "Login Attempts"
        indexes = [
            models.Index(fields=["ip_address", "attempted_at"]),
        ]

    def __str__(self):
        return f"Failed login from {self.ip_address} at {self.attempted_at}"

    # ------------------------------------------------------------------
    # Class-level helpers (DB queries, no cache)
    # ------------------------------------------------------------------

    @classmethod
    def is_blocked(cls, ip: str) -> bool:
        """
        Return True if this IP has exceeded MAX_ATTEMPTS in the last WINDOW_MINUTES.
        Pure DB query — no cache.
        """
        cutoff = timezone.now() - timezone.timedelta(minutes=cls.WINDOW_MINUTES)
        count = cls.objects.filter(ip_address=ip, attempted_at__gte=cutoff).count()
        return count >= cls.MAX_ATTEMPTS

    @classmethod
    def record_failure(cls, ip: str, username: str = "") -> None:
        """Insert a failed attempt row."""
        cls.objects.create(ip_address=ip, username_tried=username[:255])

    @classmethod
    def clear_for_ip(cls, ip: str) -> None:
        """Remove all attempts for an IP after a successful login."""
        cls.objects.filter(ip_address=ip).delete()

    @classmethod
    def cleanup_expired(cls) -> int:
        """
        Hard-delete attempt rows older than WINDOW_MINUTES.
        Call from a management command or a scheduled task.
        Returns number of rows deleted.
        """
        cutoff = timezone.now() - timezone.timedelta(minutes=cls.WINDOW_MINUTES)
        deleted, _ = cls.objects.filter(attempted_at__lt=cutoff).delete()
        return deleted
