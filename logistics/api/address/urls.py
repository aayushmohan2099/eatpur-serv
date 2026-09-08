"""
logistics/api/address/urls.py
"""
from django.urls import path
from .views import EkartAddressView

urlpatterns = [
    path('', EkartAddressView.as_view(), name='ekart-address-list-create'),
]