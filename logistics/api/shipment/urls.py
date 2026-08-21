"""
logistics/api/shipment/urls.py
"""
from django.urls import path
from .views import (
    CreateShipmentView, 
    CancelShipmentView, 
    GenerateLabelView, 
    GenerateManifestView
)

urlpatterns = [
    path('create/', CreateShipmentView.as_view(), name='shipment-create'),
    path('cancel/', CancelShipmentView.as_view(), name='shipment-cancel'),
    path('labels/', GenerateLabelView.as_view(), name='shipment-labels'),
    path('manifest/', GenerateManifestView.as_view(), name='shipment-manifest'),
]