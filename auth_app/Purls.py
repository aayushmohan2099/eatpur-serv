# auth_app/Purls.py
from django.urls import path

from .views import (
    CaptchaView,
)

urlpatterns = [
    path("captcha/",  CaptchaView.as_view(),      name="auth-captcha"),
]
