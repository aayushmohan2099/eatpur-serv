"""
messaging/urls.py
"""

from django.urls import path
from .views import *

urlpatterns = [
    path("google-form-response/", google_form_webhook),
]
