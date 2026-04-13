"""
core/settings/production.py
============================
Production environment settings.

Usage:
    export DJANGO_SETTINGS_MODULE=core.settings.production

ALL sensitive values MUST come from environment variables.
Never hardcode secrets here.

Required environment variables
-------------------------------
    DJANGO_SECRET_KEY      Django SECRET_KEY
    SECRET_API_KEY         Shared encryption key with frontend
    DB_NAME                MySQL database name
    DB_USER                MySQL user
    DB_PASSWORD            MySQL password
    DB_HOST                MySQL host
    DB_PORT                MySQL port (default 3306)
    ALLOWED_HOSTS          Comma-separated list of allowed hostnames
    CORS_ALLOWED_ORIGINS   Comma-separated list of allowed origins
"""

import os
from .base import *  # noqa: F401, F403

# ---------------------------------------------------------------------------
# Core — must come from environment
# ---------------------------------------------------------------------------
DEBUG = False

SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]    # hard fail if missing
SECRET_API_KEY = os.environ["SECRET_API_KEY"]   # hard fail if missing

ALLOWED_HOSTS = [
    h.strip()
    for h in os.environ.get("ALLOWED_HOSTS", "").split(",")
    if h.strip()
]

# ---------------------------------------------------------------------------
# Database — production MySQL (tuned for connection reuse)
# ---------------------------------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": os.environ["DB_NAME"],
        "USER": os.environ["DB_USER"],
        "PASSWORD": os.environ["DB_PASSWORD"],
        "HOST": os.environ.get("DB_HOST", "localhost"),
        "PORT": os.environ.get("DB_PORT", "3306"),
        "OPTIONS": {
            "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
            "charset": "utf8mb4",
            "connect_timeout": 10,
        },
        # Keep connections alive for up to 5 minutes (reduces per-request overhead)
        "CONN_MAX_AGE": 300,
    }
}

# ---------------------------------------------------------------------------
# CORS — strict whitelist
# ---------------------------------------------------------------------------
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = [
    o.strip()
    for o in os.environ.get("CORS_ALLOWED_ORIGINS", "").split(",")
    if o.strip()
]

# ---------------------------------------------------------------------------
# Security hardening
# ---------------------------------------------------------------------------
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# HSTS — 1 year, include subdomains, submit to preload list
SECURE_HSTS_SECONDS = 31_536_000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

# Cookies
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Lax"

# ---------------------------------------------------------------------------
# CAPTCHA — strict in production
# ---------------------------------------------------------------------------
CAPTCHA_EXPIRE_MINUTES = 5
CAPTCHA_CASE_SENSITIVE = False

# ---------------------------------------------------------------------------
# Email — configure for your mail provider
# ---------------------------------------------------------------------------
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.environ.get("EMAIL_HOST", "smtp.example.com")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "no-reply@example.com")

TEMPLATES[0]["OPTIONS"]["context_processors"] += [
    "core.admin_panel.context_processors.user_role",
]

# ---------------------------------------------------------------------------
# Logging — file-backed in production
# ---------------------------------------------------------------------------
LOG_DIR = BASE_DIR / "logs"                                  # noqa: F405
LOG_DIR.mkdir(parents=True, exist_ok=True)

LOGGING["handlers"]["auth_file"] = {                         # noqa: F405
    "class": "logging.handlers.RotatingFileHandler",
    "filename": str(LOG_DIR / "auth.log"),
    "maxBytes": 10 * 1024 * 1024,   # 10 MB
    "backupCount": 10,
    "formatter": "verbose",
}
LOGGING["handlers"]["security_file"] = {                     # noqa: F405
    "class": "logging.handlers.RotatingFileHandler",
    "filename": str(LOG_DIR / "security.log"),
    "maxBytes": 10 * 1024 * 1024,
    "backupCount": 10,
    "formatter": "verbose",
}
LOGGING["loggers"]["auth_app"] = {                           # noqa: F405
    "handlers": ["console", "auth_file"],
    "level": "INFO",
    "propagate": False,
}
LOGGING["loggers"]["security"] = {                           # noqa: F405
    "handlers": ["console", "security_file"],
    "level": "WARNING",
    "propagate": False,
}
LOGGING["root"]["level"] = "ERROR"                           # noqa: F405
