"""
logistics/api/tracking/urls.py
"""
from django.urls import path
from .views import CustomerTrackingView, LiveEkartTrackingSyncView

urlpatterns = [
    path('customer/<str:tracking_id>/', CustomerTrackingView.as_view(), name='tracking-customer'),
    path('sync/<str:tracking_id>/', LiveEkartTrackingSyncView.as_view(), name='tracking-sync-live'),
]