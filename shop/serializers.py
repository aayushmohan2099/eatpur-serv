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
    Validates the cart payload for Razorpay Order creation and stores
    customer delivery/logistics details required for fulfillment.
    """
    items = CheckoutItemSerializer(many=True, allow_empty=False)
    coupon_code = serializers.CharField(required=False, allow_blank=True)

    # Customer Delivery Details (Saved to SaleOrder)
    consignee_name = serializers.CharField(max_length=255)
    consignee_phone = serializers.CharField(max_length=20)
    consignee_alternate_phone = serializers.CharField(max_length=20)
    drop_location = serializers.CharField(help_text="Customer Address Line")
    drop_city = serializers.CharField(max_length=100)
    drop_state = serializers.CharField(max_length=100)
    drop_pincode = serializers.CharField(max_length=10)
    
    # Ekart Shipping Preferences (Saved to SaleOrder)
    pickup_location_alias = serializers.CharField(max_length=100, default="Primary Warehouse")
    service_type = serializers.ChoiceField(choices=["SURFACE", "EXPRESS"], default="SURFACE")
    preferred_dispatch_date = serializers.DateField(required=False, allow_null=True)

# ===========================================================================
# PHASE 4: SIGNATURE VERIFICATION SERIALIZER
# ===========================================================================

class VerifyPaymentSerializer(serializers.Serializer):
    """
    Validates the Razorpay success callback data sent from the React frontend.
    Shipping details are omitted here as they are already stored securely 
    in the SaleOrder during Checkout.
    """
    razorpay_payment_id = serializers.CharField(max_length=255)
    razorpay_order_id = serializers.CharField(max_length=255)
    razorpay_signature = serializers.CharField(max_length=255)