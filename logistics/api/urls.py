"""
logistics/api/urls.py
=====================
Main URL router for the logistics app.

Include in core/urls.py:
    path("api/logistics/", include("logistics.api.urls")),
"""
from django.urls import path, include

urlpatterns = [
    path("auth/", include("logistics.api.ekart_auth.urls")),
    path("serviceability/", include("logistics.api.serviceability.urls")),
    path("shipment/", include("logistics.api.shipment.urls")),
    path("tracking/", include("logistics.api.tracking.urls")),
    path("ndr/", include("logistics.api.ndr.urls")),
    path("dashboard/", include("logistics.api.admin_dashboard.urls")),
    path("webhooks/", include("logistics.api.webhooks.urls")),
]