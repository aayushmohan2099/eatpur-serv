"""
logistics/api/serviceability/urls.py
"""
from django.urls import path
from .views import CheckPincodeServiceabilityView, ShippingEstimateView

urlpatterns = [
    path('check/<int:pincode>/', CheckPincodeServiceabilityView.as_view(), name='pincode-check'),
    path('estimate/', ShippingEstimateView.as_view(), name='shipping-estimate'),
]