"""
shop/serializers.py
===================
Serializers for the shop & checkout flow.
"""

from rest_framework import serializers

class CheckoutItemSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1)

class CheckoutSerializer(serializers.Serializer):
    """
    Validates the cart payload for Razorpay Order creation.
    """
    items = CheckoutItemSerializer(many=True, allow_empty=False)
    coupon_code = serializers.CharField(required=False, allow_blank=True)

# ===========================================================================
# PHASE 4: SIGNATURE VERIFICATION SERIALIZER
# ===========================================================================

class VerifyPaymentSerializer(serializers.Serializer):
    """
    Validates the Razorpay success callback data sent from the React frontend.
    """
    razorpay_payment_id = serializers.CharField(max_length=255)
    razorpay_order_id = serializers.CharField(max_length=255)
    razorpay_signature = serializers.CharField(max_length=255)