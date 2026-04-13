"""
core/settings/base.py
=====================
Shared settings inherited by all environments.
Never import this directly — use development.py or production.py.

Switching:
    export DJANGO_SETTINGS_MODULE=core.settings.development
    export DJANGO_SETTINGS_MODULE=core.settings.production
"""

import os
from pathlib import Path
from datetime import timedelta
from corsheaders.defaults import default_headers

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent.parent   # project root

# ---------------------------------------------------------------------------
# Secret keys — MUST be overridden in environment variables
# ---------------------------------------------------------------------------
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "CHANGE_ME_IN_ENV")

# Shared with the React frontend for response decryption
# Format: base64( SECRET_API_KEY + json_string )
SECRET_API_KEY = os.environ.get("SECRET_API_KEY", "EATPURx220326")

# ---------------------------------------------------------------------------
# Application definition
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Third-party
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",  # DB-backed blacklist
    "corsheaders",

    # Project apps
    "core",
    "user",
    "auth_app",
    "security",
    "blog.apps.BlogConfig",
    "inventory",
    "messaging",
    "shop",
]

AUTH_USER_MODEL = "user.CustomUser"

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------
MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "core.urls"
WSGI_APPLICATION = "core.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "core" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# ---------------------------------------------------------------------------
# Password validation
# ---------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------------------------------------------------------------------------
# Internationalisation
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static / Media
# ---------------------------------------------------------------------------
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

STATICFILES_DIRS = [
    BASE_DIR / "core" / "templates" / "static",
]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# DRF — global defaults
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    # JWT via our custom subclass that also attaches session to request
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "security.jwt_custom.CustomJWTAuthentication",
    ],
    # All responses encrypted
    "DEFAULT_RENDERER_CLASSES": [
        "security.drf_extensions.EncryptedJSONRenderer",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    # DRF-level throttling (DB-backed, no cache required)
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "60/min",
        "user": "300/min",
        "login": "5/min",
        "captcha": "20/min",
    },
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 12,
}

# ---------------------------------------------------------------------------
# SimpleJWT configuration
# ---------------------------------------------------------------------------
SIMPLE_JWT = {
    # Lifetimes
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),

    # Rotation & blacklisting
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,   # requires rest_framework_simplejwt.token_blacklist
    "UPDATE_LAST_LOGIN": False,

    # Signing
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,          # overridden per environment via SECRET_KEY

    # Header
    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_HEADER_NAME": "HTTP_AUTHORIZATION",

    # Payload fields
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",

    # Custom token classes that inject extra claims
    "TOKEN_OBTAIN_PAIR_SERIALIZER": "auth_app.serializers.CustomTokenObtainPairSerializer",

    # Token type claim
    "TOKEN_TYPE_CLAIM": "token_type",
    "JTI_CLAIM": "jti",
}

# ---------------------------------------------------------------------------
# CAPTCHA config
# ---------------------------------------------------------------------------
CAPTCHA_LENGTH = 6                          # characters in challenge string
CAPTCHA_EXPIRE_MINUTES = 5                  # challenge TTL
CAPTCHA_CASE_SENSITIVE = False              # comparison mode
CAPTCHA_CHARS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # exclude 0/O/1/I confusion

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = list(default_headers) + ["x-api-key"]

# ---------------------------------------------------------------------------
# Logging — base config (environments extend this)
# ---------------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{asctime}] {levelname} {name} {process:d} {thread:d}: {message}",
            "style": "{",
        },
        "simple": {
            "format": "[{asctime}] {levelname} {name}: {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
    },
    "loggers": {
        "auth_app": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "security": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
    "root": {"handlers": ["console"], "level": "WARNING"},
}
