"""
logistics/api/ndr/urls.py
"""
from django.urls import path
from .views import NDRActionView

urlpatterns = [
    path('action/', NDRActionView.as_view(), name='ndr-action'),
]