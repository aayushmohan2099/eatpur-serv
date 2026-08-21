"""
logistics/api/shipment/serializers.py
=====================================
Serializers for Admin order fulfillment operations.
"""

from rest_framework import serializers
from logistics.models import EkartAddress

class CreateShipmentSerializer(serializers.Serializer):
    """
    Accepts the minimum required data from the Admin panel to dispatch a SaleOrder.
    """
    sale_order_id = serializers.IntegerField(
        help_text="The internal ID of the shop.SaleOrder to dispatch."
    )
    payment_mode = serializers.ChoiceField(
        choices=["COD", "Prepaid", "Pickup"], 
        default="Prepaid"
    )
    pickup_location_alias = serializers.CharField(
        max_length=100, 
        help_text="The alias of the registered EkartAddress for pickup."
    )
    service_type = serializers.ChoiceField(
        choices=["SURFACE", "EXPRESS"], 
        default="SURFACE"
    )
    weight = serializers.IntegerField(min_value=1, help_text="Weight in grams")
    length = serializers.IntegerField(min_value=1, help_text="Length in cm")
    height = serializers.IntegerField(min_value=1, help_text="Height in cm")
    width = serializers.IntegerField(min_value=1, help_text="Width in cm")
    
    # Optional advanced flags
    delayed_dispatch = serializers.BooleanField(default=False)
    obd_shipment = serializers.BooleanField(default=False)

    def validate_pickup_location_alias(self, value):
        if not EkartAddress.objects.filter(alias=value, is_deleted=False).exists():
            raise serializers.ValidationError(f"Pickup location alias '{value}' does not exist in database.")
        return value


class TrackingIdListSerializer(serializers.Serializer):
    """
    Generic serializer for bulk actions (Labels, Manifests).
    """
    tracking_ids = serializers.ListField(
        child=serializers.CharField(max_length=100),
        allow_empty=False,
        max_length=100,
        help_text="List of Ekart tracking IDs (Max 100)."
    )


class CancelShipmentSerializer(serializers.Serializer):
    """
    Serializer for cancelling a single shipment.
    """
    tracking_id = serializers.CharField(
        max_length=100, 
        help_text="The Ekart tracking ID to cancel."
    )