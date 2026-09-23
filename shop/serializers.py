"""
shop/serializers.py
===================
Serializers for the shop & checkout flow.
"""

from rest_framework import serializers
from .models import SaleOrder, Coupon, CouponStatus

# ===========================================================================
# CHECKOUT & PAYMENT SERIALIZERS
# ===========================================================================

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
    total_amount = serializers.DecimalField(required=True, max_digits=14, decimal_places=2)

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

# ===========================================================================
# ADMIN CUSTOMER ADDRESS SERIALIZER 
# ===========================================================================

class CustomerAddressSerializer(serializers.ModelSerializer):
    """
    Extracts delivery addresses from a customer's past orders.
    Used by the Admin API to group order history by address.
    """
    class Meta:
        model = SaleOrder
        fields = [
            'consignee_name', 
            'consignee_phone', 
            'consignee_alternate_phone', 
            'drop_location', 
            'drop_city', 
            'drop_state', 
            'drop_pincode'
        ]

# ===========================================================================
# ADMIN COUPON SERIALIZER 
# ===========================================================================

class CouponSerializer(serializers.ModelSerializer):
    """
    Serializer for Admin CRUD operations on Coupons.
    """
   
    status_name = serializers.ChoiceField(
        choices=[("ONGOING", "Ongoing"), ("EXPIRED", "Expired"), ("DRAFT", "Draft")],
        write_only=True
    )
    
    status = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = Coupon
        fields = [
            'id', 'coupon_code', 'description', 'status', 'status_name', 
            'start_date', 'end_date', 'discount_type', 'discount_value', 
            'min_order_value', 'is_auto_apply', # Added the new fields here
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def create(self, validated_data):
        status_name = validated_data.pop('status_name')
        status_obj, _ = CouponStatus.objects.get_or_create(status_name=status_name)
        validated_data['status'] = status_obj
        return super().create(validated_data)

    def update(self, instance, validated_data):
        status_name = validated_data.pop('status_name', None)
        if status_name:
            status_obj, _ = CouponStatus.objects.get_or_create(status_name=status_name)
            instance.status = status_obj
        return super().update(instance, validated_data)