from rest_framework.generics import ListAPIView
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
from django.utils.dateparse import parse_date
from django.shortcuts import get_object_or_404

from shop.models import SaleOrder
from .serializers import CustomerOrderListSerializer, CustomerInvoiceListSerializer

class CustomerOrderListView(ListAPIView):
    """
    GET /api/shop/customer/orders/
    Returns the authenticated user's order history with comprehensive filtering.
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = CustomerOrderListSerializer

    def get_queryset(self):
        # STRICT SECURITY: Force filter by the authenticated user's sessions
        user = self.request.user
        qs = SaleOrder.objects.filter(session__user=user, is_deleted=False).order_by('-order_date')

        # Filters
        payment_status = self.request.query_params.get('payment_status')
        fulfillment_status = self.request.query_params.get('fulfillment_status')
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')

        if payment_status:
            qs = qs.filter(payment_status=payment_status.upper())
        
        if fulfillment_status:
            qs = qs.filter(fulfillment_status=fulfillment_status.upper())
        
        if start_date:
            parsed_start = parse_date(start_date)
            if parsed_start: 
                qs = qs.filter(order_date__date__gte=parsed_start)
                
        if end_date:
            parsed_end = parse_date(end_date)
            if parsed_end: 
                qs = qs.filter(order_date__date__lte=parsed_end)

        return qs.prefetch_related('order_products__product__media', 'logistics_shipments')


class CustomerInvoiceListView(ListAPIView):
    """
    GET /api/shop/customer/invoices/
    Returns only PAID orders, serving as the official invoice history.
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = CustomerInvoiceListSerializer

    def get_queryset(self):
        user = self.request.user
        # Invoices only exist for successfully PAID orders
        qs = SaleOrder.objects.filter(session__user=user, payment_status="PAID", is_deleted=False).order_by('-order_date')

        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')

        if start_date:
            parsed_start = parse_date(start_date)
            if parsed_start: 
                qs = qs.filter(order_date__date__gte=parsed_start)
        
        if end_date:
            parsed_end = parse_date(end_date)
            if parsed_end: 
                qs = qs.filter(order_date__date__lte=parsed_end)

        return qs.prefetch_related('logistics_shipments')


class CustomerInvoiceDownloadView(APIView):
    """
    GET /api/shop/customer/invoices/<order_id>/download/
    
    Returns a richly formatted JSON payload of the invoice. 
    (In modern React stacks, returning JSON allows the frontend to render a beautiful, 
    brand-matched printable component instantly without heavy backend PDF libraries).
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, order_id):
        # Strict security constraint: Only the owner can fetch their invoice
        order = get_object_or_404(
            SaleOrder, 
            id=order_id, 
            session__user=request.user, 
            payment_status="PAID", 
            is_deleted=False
        )
        
        # Fetch related shipment for official invoice number if dispatched
        shipment = order.logistics_shipments.filter(is_deleted=False).first()
        invoice_number = shipment.invoice_number if shipment else f"PROFORMA-{order.id}"
        invoice_date = shipment.invoice_date.isoformat() if shipment and shipment.invoice_date else order.order_date.date().isoformat()

        # Calculate taxes strictly based on the snapshotted order amounts
        total = float(order.total_amount)
        taxable_val = round(total / 1.05, 2)
        tax_val = round(total - taxable_val, 2)

        invoice_data = {
            "company_info": {
                "name": "Eatpur Naturals LLP",
                "address": "Sec- 5/77, Vikas Nagar, Lucknow- 226022, U.P.",
                "gstin": "09ABCDE1234F1Z5",
                "email": "support@eatpur.in"
            },
            "customer_info": {
                "name": order.consignee_name,
                "phone": order.consignee_alternate_phone,
                "address": f"{order.drop_location}, {order.drop_city}, {order.drop_state} - {order.drop_pincode}"
            },
            "invoice_details": {
                "invoice_number": invoice_number,
                "order_id": f"ORD-{order.id}",
                "date": invoice_date,
                "payment_status": order.payment_status,
                "payment_mode": "Prepaid (Razorpay)"
            },
            "items": [
                {
                    "name": op.product.name,
                    "quantity": op.quantity,
                    "unit_price": float(op.price_at_purchase),
                    "subtotal": float(op.subtotal)
                } for op in order.order_products.select_related('product')
            ],
            "totals": {
                "taxable_amount": taxable_val,
                "tax_amount": tax_val,
                "grand_total": total
            }
        }

        return Response(invoice_data, status=status.HTTP_200_OK)