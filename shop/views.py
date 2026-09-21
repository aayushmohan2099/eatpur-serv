"""
shop/views.py
=============
API Views for Shop, Orders, Checkout, and Webhooks.
"""

import uuid
import razorpay
import logging
import json
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions, generics

from .serializers import (
    CheckoutSerializer, 
    VerifyPaymentSerializer, 
    CustomerAddressSerializer,
     CouponSerializer
)
from .models import (
    SaleOrder, OrderProduct, OrderTransaction, 
    TransactionProcessor, TransactionStatus, Coupon
)

from inventory.models import Product, ProductStatus
from logistics.models import EkartShipment, EkartAddress
from logistics.utils.ekart_client import EkartClient, EkartAPIException

logger = logging.getLogger("shop")

# ===========================================================================
# HELPER: FULFILL ORDER
# ===========================================================================

def _fulfill_order(sale_order):
    """
    Deducts inventory and finalizes the order upon a successful payment.
    Called by both the VerifyPaymentView (Phase 4) and RazorpayWebhookView (Phase 5).
    """
    for order_product in sale_order.order_products.select_related('product'):
        product = order_product.product
        if product:
            # Deduct stock safely
            product.quantity = max(0, product.quantity - order_product.quantity)
            
            # Auto-update product status based on new quantity
            if product.quantity == 0:
                status_obj, _ = ProductStatus.objects.get_or_create(status_name="OUT_OF_STOCK")
                product.status = status_obj
            elif product.quantity <= 10:
                status_obj, _ = ProductStatus.objects.get_or_create(status_name="LOW")
                product.status = status_obj
                    
            product.save(update_fields=['quantity', 'status', 'updated_at'])
                
    # Phase 1 Completion: Mark order as Paid and queue for fulfillment
    sale_order.payment_status = "PAID"
    sale_order.fulfillment_status = "UNFULFILLED"
    sale_order.save(update_fields=['payment_status', 'fulfillment_status', 'updated_at'])


# ===========================================================================
# PHASE 2: RAZORPAY ORDER CREATION
# ===========================================================================

class CheckoutView(APIView):
    """
    POST /api/shop/checkout/
    """
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        serializer = CheckoutSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        valid_data = serializer.validated_data
        items_data = valid_data['items']
        coupon_code = valid_data.get('coupon_code')
        
        session_obj = getattr(request, 'session_obj', None)

        # 1. Calculate Secure Total Amount
        total_amount = Decimal("0.00")
        product_cache = {}

        for item in items_data:
            try:
                product = Product.objects.get(id=item['product_id'], is_deleted=False)
            except Product.DoesNotExist:
                return Response({"error": f"Product ID {item['product_id']} not found."}, status=status.HTTP_400_BAD_REQUEST)

            if product.quantity < item['quantity']:
                return Response({"error": f"Insufficient stock for '{product.name}'. Only {product.quantity} left."}, status=status.HTTP_400_BAD_REQUEST)

            product_cache[item['product_id']] = product
            total_amount += (product.discounted_price * item['quantity'])

        # 2. Apply Coupon
        applied_coupon = None
        if coupon_code:
            try:
                applied_coupon = Coupon.objects.get(
                    coupon_code=coupon_code, 
                    is_deleted=False, 
                    status__status_name="ONGOING",
                    start_date__lte=timezone.now(),
                    end_date__gte=timezone.now()
                )
                
                if applied_coupon.discount_type == "FLAT":
                    total_amount -= applied_coupon.discount_value
                elif applied_coupon.discount_type == "PERCENT":
                    total_amount -= (total_amount * applied_coupon.discount_value / Decimal("100.00"))
                
                total_amount = max(Decimal("0.00"), total_amount)
                
            except Coupon.DoesNotExist:
                return Response({"error": "Invalid or expired coupon."}, status=status.HTTP_400_BAD_REQUEST)

        if total_amount < Decimal("1.00"):
            return Response({"error": "Minimum order value is ₹1.00"}, status=status.HTTP_400_BAD_REQUEST)

        # 3. Create SaleOrder & Store all Delivery Info
        sale_order = SaleOrder.objects.create(
            total_amount=total_amount,
            session=session_obj,
            coupon=applied_coupon,
            consignee_name=valid_data.get('consignee_name', ''),
            consignee_phone=valid_data.get('consignee_phone', ''),
            consignee_alternate_phone=valid_data.get('consignee_alternate_phone', ''),
            drop_location=valid_data.get('drop_location', ''),
            drop_city=valid_data.get('drop_city', ''),
            drop_state=valid_data.get('drop_state', ''),
            drop_pincode=valid_data.get('drop_pincode', ''),
            preferred_dispatch_date=valid_data.get('preferred_dispatch_date'),
            service_type=valid_data.get('service_type', 'SURFACE'),
            pickup_location_alias=valid_data.get('pickup_location_alias', 'Primary Warehouse')
        )

        order_products = []
        for item in items_data:
            product = product_cache[item['product_id']]
            order_products.append(OrderProduct(
                sale_order=sale_order,
                product=product,
                quantity=item['quantity'],
                price_at_purchase=product.discounted_price
            ))
            
        for op in order_products:
            op.subtotal = op.price_at_purchase * op.quantity
            
        OrderProduct.objects.bulk_create(order_products)

        # 4. Talk to Razorpay API
        razorpay_client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
        amount_in_paise = int(total_amount * 100)

        try:
            razorpay_order = razorpay_client.order.create({
                "amount": amount_in_paise,
                "currency": "INR",
                "receipt": f"rcpt_eatpur_{sale_order.id}",
                "notes": {
                    "sale_order_id": sale_order.id,
                    "user_id": request.user.id
                }
            })
        except Exception as e:
            logger.error(f"Razorpay Order Creation Failed: {str(e)}")
            return Response({"error": "Payment gateway error."}, status=status.HTTP_502_BAD_GATEWAY)

        razorpay_order_id = razorpay_order['id']

        # 5. Log Transaction (INITIATED)
        processor, _ = TransactionProcessor.objects.get_or_create(processor_name="RAZORPAY", defaults={"processor_type": "UPI"})
        status_init, _ = TransactionStatus.objects.get_or_create(status_name="INITIATED")

        OrderTransaction.objects.create(
            sale_order=sale_order,
            transaction_id=razorpay_order_id,
            transaction_date=timezone.now(),
            processor=processor,
            session=session_obj,
            status=status_init,
            response=razorpay_order
        )

        return Response({
            "razorpay_order_id": razorpay_order_id,
            "amount": amount_in_paise,
            "currency": "INR",
            "key_id": settings.RAZORPAY_KEY_ID,
            "sale_order_id": sale_order.id,
            "customer": {
                "name": request.user.username,
                "email": request.user.email,
                "contact": request.user.mobile
            }
        }, status=status.HTTP_200_OK)


# ===========================================================================
# PHASE 4: SIGNATURE VERIFICATION API (MANUAL DISPATCH FLOW)
# ===========================================================================

class VerifyPaymentView(APIView):
    """
    POST /api/shop/verify-payment/
    Verifies the success callback from the React frontend, and fulfills the order.
    Dispatching to Ekart is now handled manually by admins.
    """
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        serializer = VerifyPaymentSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        valid_data = serializer.validated_data
        payment_id = valid_data['razorpay_payment_id']
        order_id = valid_data['razorpay_order_id']
        signature = valid_data['razorpay_signature']

        razorpay_client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

        try:
            transaction_record = OrderTransaction.objects.select_related('sale_order').get(transaction_id=order_id)
            order = transaction_record.sale_order
        except OrderTransaction.DoesNotExist:
            return Response({"error": "Transaction not found."}, status=status.HTTP_404_NOT_FOUND)

        try:
            # 1. Razorpay SDK Verification (Bypass for testing)
            if not payment_id.startswith("pay_TEST_"):
                razorpay_client.utility.verify_payment_signature({
                    'razorpay_order_id': order_id,
                    'razorpay_payment_id': payment_id,
                    'razorpay_signature': signature
                })
            
            # 2. Prevent double-fulfillment if webhook beat the frontend
            if transaction_record.status.status_name != "SUCCESS":
                status_success, _ = TransactionStatus.objects.get_or_create(status_name="SUCCESS")
                transaction_record.status = status_success
                
                # Append verification data to audit log
                current_response = transaction_record.response or {}
                current_response['razorpay_payment_id'] = payment_id
                current_response['razorpay_signature'] = signature
                transaction_record.response = current_response
                
                transaction_record.save(update_fields=['status', 'response', 'updated_at'])
                
                # Deduct Inventory & Mark Order as PAID and UNFULFILLED
                _fulfill_order(order)

            return Response({"message": "Payment verified successfully."}, status=status.HTTP_200_OK)

        except razorpay.errors.SignatureVerificationError:
            status_failed, _ = TransactionStatus.objects.get_or_create(status_name="FAILED")
            transaction_record.status = status_failed
            transaction_record.save(update_fields=['status', 'updated_at'])
            return Response({"error": "Invalid payment signature."}, status=status.HTTP_400_BAD_REQUEST)
        

# ===========================================================================
# PHASE 5: RAZORPAY WEBHOOKS (The Safety Net)
# ===========================================================================

class RazorpayWebhookView(APIView):
    """
    POST /api/shop/razorpay-webhook/
    Listens for Razorpay background events (e.g. payment.captured).
    MUST be completely public (no JWT auth).
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        webhook_secret = getattr(settings, 'RAZORPAY_WEBHOOK_SECRET', None)
        signature = request.headers.get('X-Razorpay-Signature')

        if not webhook_secret or not signature:
            logger.error("Webhook missing secret or signature header.")
            return Response(status=status.HTTP_400_BAD_REQUEST)

        razorpay_client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

        try:
            # Verify using the raw request body
            razorpay_client.utility.verify_webhook_signature(
                request.body.decode('utf-8'), 
                signature, 
                webhook_secret
            )
        except razorpay.errors.SignatureVerificationError:
            logger.warning("Webhook signature verification failed.")
            return Response(status=status.HTTP_400_BAD_REQUEST)

        payload = request.data
        event = payload.get('event')

        # -------------------------------------------------------------------
        # Event: Payment Captured (Success)
        # -------------------------------------------------------------------
        if event == 'payment.captured':
            payment_entity = payload['payload']['payment']['entity']
            order_id = payment_entity.get('order_id')

            if order_id:
                try:
                    transaction_record = OrderTransaction.objects.select_related('sale_order').get(transaction_id=order_id)
                    
                    # Only update and fulfill if the frontend didn't already mark it SUCCESS
                    if transaction_record.status.status_name != "SUCCESS":
                        status_success, _ = TransactionStatus.objects.get_or_create(status_name="SUCCESS")
                        transaction_record.status = status_success
                        
                        current_response = transaction_record.response or {}
                        current_response['webhook_payment_captured'] = payment_entity
                        transaction_record.response = current_response
                        
                        transaction_record.save(update_fields=['status', 'response', 'updated_at'])
                        
                        # Deduct Inventory
                        _fulfill_order(transaction_record.sale_order)
                        logger.info(f"Webhook marked order {order_id} as SUCCESS and fulfilled inventory.")
                        
                        # Note: We deliberately skip Auto-Dispatch here to avoid duplicate dispatch calls
                        # if the webhook and frontend race each other. If webhook wins, Admin can manually dispatch.
                        
                except OrderTransaction.DoesNotExist:
                    logger.error(f"Webhook received for unknown order: {order_id}")
        
        # -------------------------------------------------------------------
        # Event: Payment Failed
        # -------------------------------------------------------------------
        elif event == 'payment.failed':
            payment_entity = payload['payload']['payment']['entity']
            order_id = payment_entity.get('order_id')
            
            if order_id:
                try:
                    transaction_record = OrderTransaction.objects.get(transaction_id=order_id)
                    # Don't overwrite if it somehow succeeded
                    if transaction_record.status.status_name not in ["SUCCESS", "FAILED"]:
                        status_failed, _ = TransactionStatus.objects.get_or_create(status_name="FAILED")
                        transaction_record.status = status_failed
                        
                        current_response = transaction_record.response or {}
                        current_response['webhook_payment_failed'] = payment_entity
                        transaction_record.response = current_response
                        
                        transaction_record.save(update_fields=['status', 'response', 'updated_at'])
                except OrderTransaction.DoesNotExist:
                    pass

        # Always return 200 OK to Razorpay so it stops retrying the webhook
        return Response(status=status.HTTP_200_OK)
# ===========================================================================
# ADMIN SPECIFIC API (Admin Dashboard ke liye)
# ===========================================================================

class AdminCustomerAddressHistoryView(APIView):
    """
    GET /api/shop/admin/customer-address-history/
    Sirf Admin ke liye: Har customer ka order history (address par kitne orders hue).
    """
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        orders = SaleOrder.objects.filter(is_deleted=False).order_by('-order_date')
        serializer = CustomerAddressSerializer(orders, many=True)
        grouped_addresses = {}

        for i, address in enumerate(serializer.data):
            name = (address.get('consignee_name') or "").strip().lower()
            location = (address.get('drop_location') or "").strip().lower()
            pincode = (address.get('drop_pincode') or "").strip()

            address_key = (name, location, pincode)
            
            if address_key not in grouped_addresses:
                address['order_count'] = 1
                address['order_ids'] = [orders[i].id] 
                grouped_addresses[address_key] = address
            else:
                grouped_addresses[address_key]['order_count'] += 1
                grouped_addresses[address_key]['order_ids'].append(orders[i].id)
                
                if not grouped_addresses[address_key]['consignee_phone'] and address.get('consignee_phone'):
                    grouped_addresses[address_key]['consignee_phone'] = address.get('consignee_phone')

        return Response(list(grouped_addresses.values()), status=status.HTTP_200_OK)

# ===========================================================================
# ADMIN SPECIFIC API: COUPON MANAGEMENT
# ===========================================================================

class AdminCouponListCreateView(generics.ListCreateAPIView):
    """
    GET /api/shop/admin/coupons/ - List all active coupons
    POST /api/shop/admin/coupons/ - Create a new coupon
    """
    queryset = Coupon.objects.filter(is_deleted=False).order_by('-created_at')
    serializer_class = CouponSerializer
    permission_classes = [permissions.IsAdminUser]


class AdminCouponDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET /api/shop/admin/coupons/<id>/ - Get single coupon details
    PUT/PATCH /api/shop/admin/coupons/<id>/ - Update coupon details
    DELETE /api/shop/admin/coupons/<id>/ - Soft delete a coupon
    """
    queryset = Coupon.objects.filter(is_deleted=False)
    serializer_class = CouponSerializer
    permission_classes = [permissions.IsAdminUser]

    def perform_destroy(self, instance):
        # Calls the SoftDeleteMixin's delete() method to set is_deleted = True
        instance.delete()