"""
logistics/api/ekart_auth/urls.py
"""
from django.urls import path
from .views import EkartTokenRefreshView

urlpatterns = [
    path('refresh/', EkartTokenRefreshView.as_view(), name='ekart-auth-refresh'),
]