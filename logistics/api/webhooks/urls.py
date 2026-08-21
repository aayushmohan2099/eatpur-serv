"""
logistics/api/webhooks/urls.py
"""
from django.urls import path
from .views import EkartWebhookReceiverView

urlpatterns = [
    path('ekart/', EkartWebhookReceiverView.as_view(), name='webhook-ekart'),
]