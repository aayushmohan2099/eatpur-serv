"""
auth_app/urls.py
================

Route map
---------
GET    /auth/captcha/   → CaptchaView       (public, throttled)
POST   /auth/login/     → LoginView         (public, throttled, CAPTCHA-protected)
POST   /auth/logout/    → LogoutView        (requires Bearer access token)
POST   /auth/refresh/   → TokenRefreshView  (public, SimpleJWT rotation)
POST   /auth/register/  → RegisterView      (public, throttled, CAPTCHA-protected)
GET    /auth/me/        → MeView            (requires Bearer access token)

Include in root urls.py:
    from django.urls import path, include
    urlpatterns = [
        path("auth/", include("auth_app.urls")),
        ...
    ]
"""

from django.urls import path

from .views import (
    CaptchaView,
    LoginView,
    LogoutView,
    MeView,
    RegisterView,
    TokenRefreshView,
)

urlpatterns = [
    path("login/",    LoginView.as_view(),         name="auth-login"),
    path("logout/",   LogoutView.as_view(),        name="auth-logout"),
    path("refresh/",  TokenRefreshView.as_view(),  name="auth-refresh"),
    path("register/", RegisterView.as_view(),      name="auth-register"),
    path("me/",       MeView.as_view(),            name="auth-me"),
]
