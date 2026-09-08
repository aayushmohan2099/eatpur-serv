"""
logistics/api/shipment/serializers.py
=====================================
Serializers for Admin order fulfillment operations.
"""

from rest_framework import serializers

class CreateShipmentSerializer(serializers.Serializer):
    """
    Validates the dispatch request. 
    Reads core details from SaleOrder automatically, but allows 
    optional priority overrides for shipping dimensions.
    """
    sale_order_id = serializers.IntegerField(help_text="ID of the shop.SaleOrder")
    
    # Optional Global Overrides for Dimensions
    weight = serializers.IntegerField(required=False, allow_null=True)
    length = serializers.IntegerField(required=False, allow_null=True)
    height = serializers.IntegerField(required=False, allow_null=True)
    width = serializers.IntegerField(required=False, allow_null=True)
    
    # Optional Item-wise Overrides
    # Format: {"product_id_1": {"weight": 500, "length": 10}, "product_id_2": {...}}
    items_dimensions = serializers.JSONField(required=False, allow_null=True)


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