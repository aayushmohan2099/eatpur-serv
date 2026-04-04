"""
auth_app/serializers.py
========================
Serializers for all auth endpoints.

LoginSerializer
    Validates captcha_id + captcha_answer + credentials in one pass.
    Returns validated `user` object in validated_data.

CaptchaSerializer
    Read-only output for GET /auth/captcha/.

LogoutSerializer
    Accepts refresh token for blacklisting.

RegisterSerializer
    New user creation with password strength + captcha validation.

UserProfileSerializer
    Read-only user profile for GET /auth/me/.
"""

import logging

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import serializers

from auth_app.models import CaptchaChallenge, LoginAttempt
from user.models import Role
from core.mixins import get_client_ip

logger = logging.getLogger("auth_app")
CustomUser = get_user_model()


# ===========================================================================
# CaptchaSerializer (response)
# ===========================================================================

class CaptchaResponseSerializer(serializers.Serializer):
    """Output for GET /auth/captcha/"""
    captcha_id = serializers.UUIDField(read_only=True)
    expires_at = serializers.DateTimeField(read_only=True)


# ===========================================================================
# LoginSerializer
# ===========================================================================

class LoginSerializer(serializers.Serializer):
    """
    Validates the full login payload in order:
      1. CAPTCHA (DB lookup + expiry + one-time-use)
      2. Rate limit check (DB query — no cache)
      3. Credential check (username or email + password)

    On success, `validated_data["user"]` holds the authenticated CustomUser.
    """

    username = serializers.CharField(
        max_length=255,
        help_text="Username or email address.",
    )
    password = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
        style={"input_type": "password"},
    )
    captcha_id = serializers.UUIDField(
        help_text="UUID returned by GET /auth/captcha/",
    )
    captcha_answer = serializers.CharField(
        max_length=10,
        help_text="User's answer to the CAPTCHA challenge.",
    )

    # ------------------------------------------------------------------
    # Validation pipeline
    # ------------------------------------------------------------------

    def validate(self, attrs):
        request = self.context.get("request")
        ip = get_client_ip(request) if request else "0.0.0.0"
        identifier = attrs["username"].strip()

        # ------ Step 1: CAPTCHA ------------------------------------------
        self._validate_captcha(attrs["captcha_id"], attrs["captcha_answer"])

        # ------ Step 2: Rate limiting (DB) --------------------------------
        if LoginAttempt.is_blocked(ip):
            raise serializers.ValidationError(
                {
                    "non_field_errors": (
                        f"Too many failed login attempts from your IP. "
                        f"Please wait {LoginAttempt.WINDOW_MINUTES} minutes and try again."
                    )
                }
            )

        # ------ Step 3: Credentials ----------------------------------------
        user = self._resolve_user(identifier)

        if user is None or not user.check_password(attrs["password"]):
            # Record failure before raising — keeps count accurate
            LoginAttempt.record_failure(ip, identifier)
            logger.warning("Failed login attempt: identifier=%s ip=%s", identifier, ip)
            raise serializers.ValidationError(
                {"non_field_errors": "Invalid credentials. Please check your username and password."}
            )

        if not user.is_active:
            raise serializers.ValidationError(
                {"non_field_errors": "This account has been deactivated. Please contact support."}
            )

        # Success — clear failure counter
        LoginAttempt.clear_for_ip(ip)
        attrs["user"] = user
        return attrs

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_captcha(captcha_id, answer: str) -> None:
        """
        Fetch the CaptchaChallenge by PK and call .validate().
        Raises ValidationError on any failure.
        """
        try:
            challenge = CaptchaChallenge.objects.get(captcha_id=captcha_id)
        except CaptchaChallenge.DoesNotExist:
            raise serializers.ValidationError(
                {"captcha_id": "Invalid CAPTCHA. Please request a new one."}
            )

        ok, reason = challenge.validate(answer)
        if not ok:
            raise serializers.ValidationError({"captcha_answer": reason})

    @staticmethod
    def _resolve_user(identifier: str):
        """Try username first, then email."""
        try:
            return CustomUser.objects.select_related("role").get(username=identifier)
        except CustomUser.DoesNotExist:
            pass
        try:
            return CustomUser.objects.select_related("role").get(email=identifier)
        except CustomUser.DoesNotExist:
            return None


# ===========================================================================
# LogoutSerializer
# ===========================================================================

class LogoutSerializer(serializers.Serializer):
    """Accepts the refresh token to be blacklisted on logout."""

    refresh = serializers.CharField(
        help_text="The refresh token received at login.",
    )


# ===========================================================================
# RegisterSerializer
# ===========================================================================

class RegisterSerializer(serializers.ModelSerializer):
    """
    New user registration.

    Password rules
    --------------
    * Minimum 8 characters
    * At least 1 uppercase letter
    * At least 1 digit
    * At least 1 special character

    CAPTCHA is validated before any DB write.
    """

    password = serializers.CharField(
        write_only=True,
        min_length=8,
        trim_whitespace=False,
        style={"input_type": "password"},
    )
    password_confirm = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
        style={"input_type": "password"},
    )
    captcha_id = serializers.UUIDField(write_only=True)
    captcha_answer = serializers.CharField(max_length=10, write_only=True)

    class Meta:
        model = CustomUser
        fields = [
            "username",
            "email",
            "mobile",
            "password",
            "password_confirm",
            "captcha_id",
            "captcha_answer",
        ]

    # ------------------------------------------------------------------
    # Field validators
    # ------------------------------------------------------------------

    def validate_password(self, value: str) -> str:
        errors = []
        if not any(c.isupper() for c in value):
            errors.append("Must contain at least one uppercase letter.")
        if not any(c.isdigit() for c in value):
            errors.append("Must contain at least one digit.")
        if not any(c in "!@#$%^&*()_+-=[]{}|;':\",./<>?" for c in value):
            errors.append("Must contain at least one special character.")
        if errors:
            raise serializers.ValidationError(errors)
        return value

    def validate_email(self, value):
        if CustomUser.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email already registered.")
        return value


    def validate_username(self, value):
        if CustomUser.objects.filter(username=value).exists():
            raise serializers.ValidationError("Username already taken.")
        return value


    def validate_mobile(self, value):
        digits = "".join(c for c in value if c.isdigit())

        if not (10 <= len(digits) <= 15):
            raise serializers.ValidationError("Mobile number must be 10–15 digits.")

        if CustomUser.objects.filter(mobile=value).exists():
            raise serializers.ValidationError("Mobile already registered.")

        return value

    # ------------------------------------------------------------------
    # Cross-field validation
    # ------------------------------------------------------------------

    def validate(self, attrs):
        # CAPTCHA first
        LoginSerializer._validate_captcha(attrs["captcha_id"], attrs["captcha_answer"])

        # Password match
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError(
                {"password_confirm": "Passwords do not match."}
            )

        return attrs

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    def create(self, validated_data: dict) -> CustomUser:
        validated_data.pop("password_confirm")
        validated_data.pop("captcha_id")
        validated_data.pop("captcha_answer")
        password = validated_data.pop("password")
        customer_role = Role.objects.get(role_name="CUSTOMER")
        validated_data["role"] = customer_role
        request = self.context.get("request")
        ip = get_client_ip(request) if request else None

        user = CustomUser(
            created_by_ip=ip,
            updated_by_ip=ip,
            **validated_data,
        )
        user.set_password(password)
        user.save()
        return user


# ===========================================================================
# UserProfileSerializer (read-only)
# ===========================================================================

class UserProfileSerializer(serializers.ModelSerializer):
    role_name = serializers.CharField(
        source="role.role_name", read_only=True, default=None
    )

    class Meta:
        model = CustomUser
        fields = [
            "id",
            "urid",
            "username",
            "email",
            "mobile",
            "avatar",
            "role_name",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields
