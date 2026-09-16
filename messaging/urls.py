"""
messaging/urls.py
"""

from django.urls import path
from .views import google_form_webhook, get_all_reviews

urlpatterns = [
    path("google-form-response/", google_form_webhook),

    path("all-reviews/", get_all_reviews),
]
