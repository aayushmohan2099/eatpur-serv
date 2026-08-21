"""
logistics/api/ndr/serializers.py
================================
Serializer for handling Non-Delivery Report actions.
"""

from rest_framework import serializers
from logistics.models import EkartShipment

class NDRActionSerializer(serializers.Serializer):
    """
    Validates payload for taking action on an NDR shipment.
    """
    tracking_id = serializers.CharField(
        max_length=100, 
        help_text="Ekart tracking ID (Waybill Number)."
    )
    action = serializers.ChoiceField(
        choices=["Re-Attempt", "RTO"],
        help_text="Action to take: Re-Attempt or Return to Origin."
    )
    reattempt_date = serializers.DateField(
        required=False, 
        allow_null=True,
        help_text="Required if action is 'Re-Attempt'."
    )
    updated_phone = serializers.CharField(
        max_length=10, 
        required=False, 
        allow_blank=True,
        help_text="Updated 10-digit phone number if needed."
    )
    updated_address = serializers.CharField(
        required=False, 
        allow_blank=True,
        help_text="Updated delivery address if needed."
    )
    instructions = serializers.CharField(
        required=False, 
        allow_blank=True,
        help_text="Special instructions for the delivery executive."
    )

    def validate(self, attrs):
        if attrs.get("action") == "Re-Attempt" and not attrs.get("reattempt_date"):
            raise serializers.ValidationError({
                "reattempt_date": "Re-Attempt date is required when action is 'Re-Attempt'."
            })
            
        # Ensure shipment exists
        if not EkartShipment.objects.filter(tracking_id=attrs.get("tracking_id"), is_deleted=False).exists():
            raise serializers.ValidationError({
                "tracking_id": "Shipment not found in database."
            })
            
        return attrs