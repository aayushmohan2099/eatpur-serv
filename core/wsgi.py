"""
WSGI config for core project.

Switch between environments using DJANGO_SETTINGS_MODULE.

Examples:
    export DJANGO_SETTINGS_MODULE=core.settings.development
    export DJANGO_SETTINGS_MODULE=core.settings.production
"""

import os
from django.core.wsgi import get_wsgi_application

# ---------------------------------------------------------------------------
# DEFAULT ENVIRONMENT
# ---------------------------------------------------------------------------

# ✅ CURRENT: Development
os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "core.settings.development"
)

# ❌ PRODUCTION (uncomment when deploying)
# os.environ.setdefault(
#     "DJANGO_SETTINGS_MODULE",
#     "core.settings.production"
# )

# ---------------------------------------------------------------------------
# WSGI Application
# ---------------------------------------------------------------------------

application = get_wsgi_application()