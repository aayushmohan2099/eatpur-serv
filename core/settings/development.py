"""
core/settings/development.py
=============================
Development environment settings.

Usage:
    export DJANGO_SETTINGS_MODULE=core.settings.development

Or in manage.py / wsgi.py:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings.development")
"""

from .base import *  # noqa: F401, F403

# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------
DEBUG = True
ALLOWED_HOSTS = ["*"]

# Development secret key — override via env var even in dev for consistency
SECRET_KEY = os.environ.get(  # noqa: F405
    "DJANGO_SECRET_KEY",
    "eatpur-#!bk-u$^nguh6z7xvr(4++ah4)4x*g&_8y%707lg8j&1ht-5u7",
)
SECRET_API_KEY = os.environ.get("SECRET_API_KEY", "HEALTHY_LIFE")  # noqa: F405

# ---------------------------------------------------------------------------
# Database — local MySQL
# ---------------------------------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": os.environ.get("DB_NAME", "eatpure_db"),       # noqa: F405
        "USER": os.environ.get("DB_USER", "eatUser"),          # noqa: F405
        "PASSWORD": os.environ.get("DB_PASSWORD", "lovelesh123"),  # noqa: F405
        "HOST": os.environ.get("DB_HOST", "localhost"),        # noqa: F405
        "PORT": os.environ.get("DB_PORT", "3306"),             # noqa: F405
        "OPTIONS": {
            "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
            "charset": "utf8mb4",
        },
        "CONN_MAX_AGE": 60,
    }
}

# ---------------------------------------------------------------------------
# CORS — wide open in dev
# ---------------------------------------------------------------------------
CORS_ALLOW_ALL_ORIGINS = True
CSRF_TRUSTED_ORIGINS = [
    "http://66.116.207.88:2203",
]
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SECURE = False

# ---------------------------------------------------------------------------
# Email — console backend (no real sending)
# ---------------------------------------------------------------------------
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# ---------------------------------------------------------------------------
# Security — relaxed for local dev
# ---------------------------------------------------------------------------
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_BROWSER_XSS_FILTER = False
SECURE_CONTENT_TYPE_NOSNIFF = False

# ---------------------------------------------------------------------------
# CAPTCHA — shorter expiry for fast testing
# ---------------------------------------------------------------------------
CAPTCHA_EXPIRE_MINUTES = 10   # more relaxed in dev
CAPTCHA_CASE_SENSITIVE = False

# ---------------------------------------------------------------------------
# Logging — verbose in dev
# ---------------------------------------------------------------------------
LOGGING["handlers"]["console"]["formatter"] = "verbose"  # noqa: F405
LOGGING["root"]["level"] = "DEBUG"                       # noqa: F405
LOGGING["loggers"]["auth_app"]["level"] = "DEBUG"        # noqa: F405
LOGGING["loggers"]["security"]["level"] = "DEBUG"        # noqa: F405
