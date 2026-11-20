"""
messaging/urls.py
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .views import FarmerContactViewSet, google_form_webhook, get_all_reviews

router = DefaultRouter()
router.register(r'farmer-contacts', FarmerContactViewSet, basename='farmer-contact')

urlpatterns = [
    path("google-form-response/", google_form_webhook),

    path("all-reviews/", get_all_reviews),
    path("", include(router.urls)),
]
