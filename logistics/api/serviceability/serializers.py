"""
logistics/api/serviceability/serializers.py
===========================================
Serializers for customer-facing checkout tools (pincode checks & pricing).
"""

from rest_framework import serializers

class ShippingEstimateSerializer(serializers.Serializer):
    """
    Validates the payload required by Ekart's /data/pricing/estimate API.
    """
    pickupPincode = serializers.IntegerField(
        help_text="Seller warehouse pincode."
    )
    dropPincode = serializers.IntegerField(
        help_text="Customer delivery pincode."
    )
    invoiceAmount = serializers.FloatField(
        min_value=0, 
        default=0.0, 
        help_text="Total value of the cart."
    )
    weight = serializers.IntegerField(
        min_value=1, 
        help_text="Total weight in grams."
    )
    length = serializers.IntegerField(
        min_value=1, 
        help_text="Box length in cm."
    )
    height = serializers.IntegerField(
        min_value=1, 
        help_text="Box height in cm."
    )
    width = serializers.IntegerField(
        min_value=1, 
        help_text="Box width in cm."
    )
    serviceType = serializers.ChoiceField(
        choices=["SURFACE", "EXPRESS"], 
        default="SURFACE",
        help_text="Shipping speed."
    )
    paymentType = serializers.ChoiceField(
        choices=["COD", "Prepaid"], 
        default="Prepaid",
        help_text="Determines if COD charges apply."
    )
    codAmount = serializers.FloatField(
        min_value=0, 
        default=0.0, 
        help_text="Amount to collect if COD. Must be 0 for Prepaid."
    )
    shippingDirection = serializers.ChoiceField(
        choices=["FORWARD", "REVERSE"],
        default="FORWARD",
        help_text="Direction of shipment relative to the seller warehouse."
    )

    def validate(self, attrs):
        if attrs.get("paymentType") == "COD" and attrs.get("codAmount", 0) <= 0:
            raise serializers.ValidationError({"codAmount": "COD Amount must be greater than 0 for COD payment type."})
        if attrs.get("paymentType") == "Prepaid" and attrs.get("codAmount", 0) > 0:
            raise serializers.ValidationError({"codAmount": "COD Amount must be 0 for Prepaid orders."})
        return attrs