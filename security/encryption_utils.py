"""
security/encryption_utils.py
=============================
Response payload encryption.

Mechanism (as specified)
------------------------
1. Serialize response data → compact JSON string.
2. Prepend SECRET_API_KEY to the JSON string.
3. UTF-8 encode the combined string.
4. Base64-encode (URL-safe, no padding).
5. Wrap: {"data": "<encoded>"}

Frontend decryption (React)
----------------------------
    const SECRET_API_KEY = import.meta.env.VITE_SECRET_API_KEY;

    function decrypt(encodedStr) {
        // Restore padding
        const pad = encodedStr.length % 4;
        const padded = pad ? encodedStr + "=".repeat(4 - pad) : encodedStr;
        // URL-safe base64 → standard
        const std = padded.replace(/-/g, "+").replace(/_/g, "/");
        // Decode
        const raw = atob(std);
        // Strip key prefix
        const json = raw.slice(SECRET_API_KEY.length);
        return JSON.parse(json);
    }

    // Usage
    const payload = decrypt(response.data.data);
"""

import base64
import json
import logging
from typing import Any

from django.conf import settings

logger = logging.getLogger("security")


# ===========================================================================
# Core helpers
# ===========================================================================

def _get_key() -> str:
    key = getattr(settings, "SECRET_API_KEY", "")
    if not key:
        logger.error(
            "SECRET_API_KEY is not configured. "
            "Responses are being 'encrypted' with an empty key — set this in settings."
        )
    return key


def encrypt_payload(data: Any) -> str:
    """
    Encrypt any JSON-serialisable Python object.

    Parameters
    ----------
    data : dict, list, str, int, None — any JSON-serialisable value

    Returns
    -------
    URL-safe Base64 string without padding ('=').

    Raises
    ------
    EncryptionError if serialisation fails.
    """
    try:
        json_str = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise EncryptionError(f"Cannot serialise response payload: {exc}") from exc

    raw = _get_key() + json_str
    encoded = (
        base64.urlsafe_b64encode(raw.encode("utf-8"))
        .rstrip(b"=")
        .decode("utf-8")
    )
    return encoded


def decrypt_payload(encoded: str) -> Any:
    """
    Reverse of encrypt_payload. Primarily used for integration testing.

    Parameters
    ----------
    encoded : URL-safe Base64 string (with or without '=' padding)

    Returns
    -------
    Original Python object.

    Raises
    ------
    EncryptionError on any decoding/parsing failure.
    """
    try:
        # Restore stripped padding
        rem = len(encoded) % 4
        if rem:
            encoded += "=" * (4 - rem)
        raw = base64.urlsafe_b64decode(encoded.encode("utf-8")).decode("utf-8")
    except Exception as exc:
        raise EncryptionError(f"Base64 decoding failed: {exc}") from exc

    key = _get_key()
    if not raw.startswith(key):
        raise EncryptionError("Payload key mismatch — response may have been tampered with.")

    json_str = raw[len(key):]
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as exc:
        raise EncryptionError(f"JSON parsing failed after decryption: {exc}") from exc


def build_encrypted_envelope(data: Any) -> dict:
    """
    Build the standard API response envelope.

    Returns
    -------
    {"data": "<BASE64_ENCRYPTED_STRING>"}
    """
    return {"data": encrypt_payload(data)}


# ===========================================================================
# Exception
# ===========================================================================

class EncryptionError(Exception):
    """Raised when encryption or decryption fails."""
