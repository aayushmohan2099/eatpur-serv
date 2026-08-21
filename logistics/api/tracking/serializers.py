"""
logistics/api/tracking/serializers.py
=====================================
Serializers for Customer and Admin tracking visibility.
"""

from rest_framework import serializers
from logistics.models import EkartTrackingEvent, EkartShipment

class EkartTrackingEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = EkartTrackingEvent
        fields = [
            "status", 
            "description", 
            "location", 
            "event_timestamp", 
            "ndr_status", 
            "attempts"
        ]

class CustomerShipmentTrackingSerializer(serializers.ModelSerializer):
    """
    Returns the core shipment details along with its chronological tracking events.
    """
    events = EkartTrackingEventSerializer(source="tracking_events", many=True, read_only=True)
    
    class Meta:
        model = EkartShipment
        fields = [
            "tracking_id",
            "order_number",
            "current_status",
            "is_delivered",
            "payment_mode",
            "service_type",
            "events"
        ]