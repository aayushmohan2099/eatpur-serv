"""
security/jwt_custom.py
======================
Custom SimpleJWT integration.

Contents
--------
1. CustomTokenObtainPairSerializer
   Injects extra claims (urid, username, role, session_id) into both tokens.

2. CustomJWTAuthentication
   Extends JWTAuthentication to:
     * Decode and validate the access token (SimpleJWT handles this).
     * Resolve the Session from the session_id claim.
     * Attach request.user and request.session_obj for downstream use.

3. get_tokens_for_user()
   Utility to manually generate a token pair for a user + session.
   Used in LoginView and RegisterView.
"""

import logging

from django.conf import settings
from django.utils.translation import gettext_lazy as _
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.exceptions import AuthenticationFailed

logger = logging.getLogger("security")


# ===========================================================================
# 1. Custom token serializer — adds extra claims
# ===========================================================================

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Extends SimpleJWT's default serializer to embed project-specific
    claims into the JWT payload.

    Extra claims added to BOTH access and refresh tokens:
        urid        : user's UUID (for frontend use without exposing numeric PK)
        username    : display name
        role        : role_name string or null
        session_id  : DB session PK (attached after session creation in LoginView)

    Note: session_id is injected AFTER token creation via inject_session_id()
    because the session doesn't exist yet when the serializer runs.
    """

    @classmethod
    def get_token(cls, user) -> RefreshToken:
        token = super().get_token(user)

        # Extra claims
        token["urid"] = str(user.urid)
        token["username"] = user.username
        token["role"] = user.role.role_name if user.role else None
        token["session_id"] = None  # placeholder — injected by LoginView after session creation

        return token


# ===========================================================================
# 2. Token pair generator (used in views)
# ===========================================================================

def get_tokens_for_user(user, session_id: int) -> dict:
    """
    Generate an access + refresh token pair for a user with session context.

    Parameters
    ----------
    user       : CustomUser instance
    session_id : integer PK of the Session created at login

    Returns
    -------
    {
        "access":     "<JWT string>",
        "refresh":    "<JWT string>",
        "expires_in": 900,             # access token lifetime (seconds)
    }
    """
    refresh = RefreshToken.for_user(user)

    # Inject our custom claims
    refresh["urid"] = str(user.urid)
    refresh["username"] = user.username
    refresh["role"] = user.role.role_name if user.role else None
    refresh["session_id"] = session_id

    access = refresh.access_token
    access["urid"] = str(user.urid)
    access["username"] = user.username
    access["role"] = user.role.role_name if user.role else None
    access["session_id"] = session_id

    lifetime = settings.SIMPLE_JWT.get("ACCESS_TOKEN_LIFETIME")
    expires_in = int(lifetime.total_seconds()) if lifetime else 900

    return {
        "access": str(access),
        "refresh": str(refresh),
        "expires_in": expires_in,
    }


# ===========================================================================
# 3. Custom authentication class
# ===========================================================================

class CustomJWTAuthentication(JWTAuthentication):
    """
    Extends SimpleJWT's JWTAuthentication.

    On every authenticated request:
    1. Reads the Bearer token from Authorization header (SimpleJWT).
    2. Validates signature + expiry + blacklist (SimpleJWT).
    3. Resolves CustomUser from user_id claim (SimpleJWT).
    4. Resolves Session from session_id claim (DB query — no cache).
    5. Attaches:
         request.user           → CustomUser instance
         request.auth           → validated token payload (AccessToken object)
         request.session_obj    → Session instance (or None if not found)
         request.session_id     → integer session PK

    Why session_obj and not session?
    ---------------------------------
    Django's SessionMiddleware uses request.session for its own cookie-based
    session. We use request.session_obj to avoid colliding with that attribute.
    """

    def authenticate(self, request):
        # Let SimpleJWT do the heavy lifting (header parsing, decoding, blacklist)
        result = super().authenticate(request)

        if result is None:
            # No Authorization header → unauthenticated (let permission class handle)
            return None

        user, validated_token = result

        # ------------------------------------------------------------------
        # Attach session from DB
        # ------------------------------------------------------------------
        session_id = validated_token.get("session_id")
        session_obj = None

        if session_id:
            try:
                from user.models import Session
                session_obj = Session.objects.get(pk=session_id, is_deleted=False)
            except Exception:
                # Session was soft-deleted (logout) — treat as invalid
                logger.warning(
                    "JWT session_id=%s not found or deleted for user_id=%s",
                    session_id, user.pk,
                )
                raise AuthenticationFailed(
                    _("Session has been terminated. Please log in again."),
                    code="session_invalid",
                )

        # Attach to request for downstream access
        request.session_obj = session_obj
        request.session_id = session_id

        return user, validated_token

    def get_user(self, validated_token):
        """
        Override to use select_related('role') — avoids extra query in every view.
        """
        from django.contrib.auth import get_user_model
        UserModel = get_user_model()

        try:
            user_id = validated_token[settings.SIMPLE_JWT.get("USER_ID_CLAIM", "user_id")]
        except KeyError:
            raise InvalidToken(_("Token contained no recognisable user identification"))

        try:
            user = UserModel.objects.select_related("role").get(
                **{settings.SIMPLE_JWT.get("USER_ID_FIELD", "id"): user_id}
            )
        except UserModel.DoesNotExist:
            raise AuthenticationFailed(_("User not found."), code="user_not_found")

        if not user.is_active:
            raise AuthenticationFailed(_("User is inactive."), code="user_inactive")

        return user
