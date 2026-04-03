"""
auth_app/views.py
=================
Authentication API views.

Endpoints
---------
GET    /auth/captcha/   → CaptchaView         — generate a fresh CAPTCHA challenge
POST   /auth/login/     → LoginView           — CAPTCHA + credential check, return JWT pair
POST   /auth/logout/    → LogoutView          — blacklist refresh token, soft-delete session
POST   /auth/refresh/   → TokenRefreshView    — rotate refresh token, issue new pair
POST   /auth/register/  → RegisterView        — create account, return JWT pair
GET    /auth/me/        → MeView              — authenticated user's profile

All responses pass through EncryptedJSONRenderer automatically (globally configured).
No view ever returns raw JSON.

Rate limiting
-------------
CaptchaView + LoginView + RegisterView are throttled at DRF level.
LoginView additionally uses DB-backed LoginAttempt (checked inside LoginSerializer).
"""

import logging

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView as SimpleJWTRefreshView

from security.captcha_image import generate_captcha_image

from auth_app.models import CaptchaChallenge
from core.mixins import get_client_ip
from security.jwt_custom import get_tokens_for_user

from .serializers import (
    CaptchaResponseSerializer,
    LoginSerializer,
    LogoutSerializer,
    RegisterSerializer,
    UserProfileSerializer,
)

logger = logging.getLogger("auth_app")
CustomUser = get_user_model()


# ===========================================================================
# Throttle classes
# ===========================================================================

class CaptchaThrottle(AnonRateThrottle):
    scope = "captcha"   # 20/min — defined in base.py


class LoginThrottle(AnonRateThrottle):
    scope = "login"     # 5/min — defined in base.py


class RegisterThrottle(AnonRateThrottle):
    scope = "login"     # reuses login scope (5/min)


# ===========================================================================
# Session helper
# ===========================================================================

def _build_session(user, request) -> "Session":  # noqa: F821
    """
    Create a Session record capturing device + geo metadata.

    Geo-location: stubbed as null — replace with a DB-backed GeoIP
    lookup (e.g., django-geoip2-extras + MaxMind DB file) if needed.
    No external API calls, no cache — pure local DB write.
    """
    from user.models import Session

    ip = get_client_ip(request) or "0.0.0.0"
    ua = request.META.get("HTTP_USER_AGENT", "")

    # Lightweight device classification from UA
    ua_lower = ua.lower()
    if any(k in ua_lower for k in ("mobile", "android", "iphone")):
        device_type = "mobile"
    elif any(k in ua_lower for k in ("tablet", "ipad")):
        device_type = "tablet"
    else:
        device_type = "desktop"

    return Session.objects.create(
        user=user,
        ip_address=ip,
        user_agent=ua[:1000],
        geo_location=None,          # populate with MaxMind if available
        device_info={"type": device_type, "ua": ua[:200]},
        created_by_ip=ip,
        updated_by_ip=ip,
    )


# ===========================================================================
# CaptchaView — GET /auth/captcha/
# ===========================================================================

class CaptchaView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [CaptchaThrottle]

    def get(self, request):
        ip = get_client_ip(request)

        challenge = CaptchaChallenge.create_for_ip(ip)

        # 🔥 Convert text → image
        captcha_image = generate_captcha_image(challenge.captcha_text)

        return Response(
            {
                "captcha_id": str(challenge.captcha_id),
                "captcha_image": f"data:image/png;base64,{captcha_image}",
                "expires_at": challenge.expires_at.isoformat(),
            },
            status=status.HTTP_200_OK,
        )

# ===========================================================================
# LoginView — POST /auth/login/
# ===========================================================================

class LoginView(APIView):
    """
    POST /auth/login/

    Body
    ----
    {
        "username":       "john_doe" | "john@example.com",
        "password":       "••••••••",
        "captcha_id":     "<UUID from /auth/captcha/>",
        "captcha_answer": "A3K9PX"
    }

    Flow
    ----
    1. Validate CAPTCHA  (DB lookup)
    2. Check rate limit  (DB query)
    3. Authenticate user (password check)
    4. Create Session    (DB write)
    5. Generate JWT pair with session_id in payload
    6. Return encrypted response

    Success response (after decryption)
    ------------------------------------
    {
        "access":     "<JWT>",
        "refresh":    "<JWT>",
        "expires_in": 900,
        "token_type": "Bearer",
        "user": { ... }
    }
    """

    permission_classes = [permissions.AllowAny]
    throttle_classes = [LoginThrottle]

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})

        if not serializer.is_valid():
            return Response(
                {"errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = serializer.validated_data["user"]
        session = _build_session(user, request)

        tokens = get_tokens_for_user(user, session_id=session.pk)

        logger.info(
            "Login success: user_id=%s session_id=%s ip=%s",
            user.pk, session.pk, get_client_ip(request),
        )

        return Response(
            {
                **tokens,
                "token_type": "Bearer",
                "user": UserProfileSerializer(user).data,
            },
            status=status.HTTP_200_OK,
        )


# ===========================================================================
# LogoutView — POST /auth/logout/
# ===========================================================================

class LogoutView(APIView):
    """
    POST /auth/logout/

    Requires: Authorization: Bearer <access_token>

    Body
    ----
    { "refresh": "<refresh_token>" }

    Actions (all DB-only, no cache)
    --------------------------------
    1. Decode refresh token via SimpleJWT.
    2. Add to SimpleJWT's DB blacklist (OutstandingToken + BlacklistedToken).
    3. Soft-delete the associated Session.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = LogoutSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(
                {"errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        refresh_token_str = serializer.validated_data["refresh"]

        # ------------------------------------------------------------------
        # Blacklist via SimpleJWT (DB-backed, no Redis)
        # ------------------------------------------------------------------
        try:
            token = RefreshToken(refresh_token_str)
            token.blacklist()   # writes to rest_framework_simplejwt.token_blacklist tables
        except TokenError as exc:
            return Response(
                {"error": str(exc), "code": "token_invalid"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ------------------------------------------------------------------
        # Soft-delete the session
        # ------------------------------------------------------------------
        session_id = getattr(request, "session_id", None)
        if session_id:
            from user.models import Session
            ip = get_client_ip(request)
            Session.objects.filter(pk=session_id, is_deleted=False).update(
                is_deleted=True,
                deleted_at=timezone.now(),
                updated_by_ip=ip,
            )

        logger.info(
            "Logout: user_id=%s session_id=%s ip=%s",
            request.user.pk, session_id, get_client_ip(request),
        )

        return Response({"message": "Logged out successfully."}, status=status.HTTP_200_OK)


# ===========================================================================
# TokenRefreshView — POST /auth/refresh/
# ===========================================================================

class TokenRefreshView(SimpleJWTRefreshView):
    """
    POST /auth/refresh/

    Extends SimpleJWT's built-in refresh view.

    SimpleJWT handles:
    * Validate refresh token signature + expiry
    * Check DB blacklist (OutstandingToken)
    * Rotate: blacklist old token, issue new pair (ROTATE_REFRESH_TOKENS=True)

    We override get_serializer() to ensure responses go through our
    EncryptedJSONRenderer automatically (it's the global default renderer).

    Body:  { "refresh": "<refresh_token>" }
    Returns: { "access": "...", "refresh": "..." }  (encrypted)
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as exc:
            raise InvalidToken(exc.args[0])

        # DRF Response → picked up by EncryptedJSONRenderer automatically
        return Response(serializer.validated_data, status=status.HTTP_200_OK)


# ===========================================================================
# RegisterView — POST /auth/register/
# ===========================================================================

class RegisterView(APIView):
    """
    POST /auth/register/

    Body
    ----
    {
        "username":        "john_doe",
        "email":           "john@example.com",
        "mobile":          "9876543210",
        "password":        "SecurePass1!",
        "password_confirm":"SecurePass1!",
        "captcha_id":      "<UUID>",
        "captcha_answer":  "A3K9PX"
    }

    On success: creates user + session, returns token pair (identical to login).
    """

    permission_classes = [permissions.AllowAny]
    throttle_classes = [RegisterThrottle]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data, context={"request": request})

        if not serializer.is_valid():
            return Response(
                {"errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = serializer.save()
        session = _build_session(user, request)
        tokens = get_tokens_for_user(user, session_id=session.pk)

        logger.info(
            "Registration: user_id=%s ip=%s",
            user.pk, get_client_ip(request),
        )

        return Response(
            {
                **tokens,
                "token_type": "Bearer",
                "user": UserProfileSerializer(user).data,
            },
            status=status.HTTP_201_CREATED,
        )


# ===========================================================================
# MeView — GET /auth/me/
# ===========================================================================

class MeView(APIView):
    """
    GET /auth/me/

    Returns the authenticated user's profile.
    Requires: Authorization: Bearer <access_token>
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(
            UserProfileSerializer(request.user).data,
            status=status.HTTP_200_OK,
        )
