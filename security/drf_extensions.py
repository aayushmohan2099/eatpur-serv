"""
security/drf_extensions.py
===========================
Custom DRF renderer: EncryptedJSONRenderer

Intercepts ALL outgoing DRF responses and encrypts the payload
using security.encryption_utils.build_encrypted_envelope().

Registered globally in base.py:
    REST_FRAMEWORK = {
        "DEFAULT_RENDERER_CLASSES": [
            "security.drf_extensions.EncryptedJSONRenderer",
        ],
    }

Bypass (per-view, for health checks etc.):
    from rest_framework.renderers import JSONRenderer

    class HealthCheckView(APIView):
        renderer_classes = [JSONRenderer]
        ...
"""

import json
import logging

from rest_framework.renderers import BaseRenderer

from .encryption_utils import build_encrypted_envelope

logger = logging.getLogger("security")


class EncryptedJSONRenderer(BaseRenderer):
    """
    DRF renderer that wraps every response body inside an encrypted envelope.

    Output
    ------
    Content-Type: application/json
    Body: {"data": "<URL_SAFE_BASE64_STRING>"}

    The frontend decrypts using the shared SECRET_API_KEY.

    Error responses (4xx, 5xx) are also encrypted — the frontend
    always decrypts before reading the payload.

    Encryption is applied unconditionally. If SECRET_API_KEY is missing
    the key becomes an empty string (logged as error), which still produces
    valid (but insecure) base64 output so the system doesn't hard-crash.
    """

    media_type = "application/json"
    format = "json"
    charset = "utf-8"

    def render(self, data, accepted_media_type=None, renderer_context=None):
        if data is None:
            return b""

        try:
            envelope = build_encrypted_envelope(data)
        except Exception as exc:
            logger.error("EncryptedJSONRenderer: encryption failed — %s", exc)
            # Fallback: return unencrypted error so the client knows something went wrong
            envelope = {"data": None, "encryption_error": "Internal encryption failure"}

        return json.dumps(envelope, ensure_ascii=False, separators=(",", ":")).encode(self.charset)
