import requests
from django.http import HttpResponse
from rest_framework.generics import ListAPIView
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
from django.utils.dateparse import parse_date
from django.shortcuts import get_object_or_404

from shop.models import SaleOrder
from .serializers import CustomerOrderListSerializer, CustomerInvoiceListSerializer
from logistics.utils.ekart_client import EkartClient, EkartAPIException

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
    
    Fetches the official invoice PDF from Ekart Logistics using their integrations API,
    downloads the PDF from the provided GCP link, and returns it directly to the frontend.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, order_id):
        # Order MUST EXIST, be paid, and belong to the requesting user
        order = get_object_or_404(
            SaleOrder, 
            id=order_id, 
            payment_status="PAID", 
            is_deleted=False
        )
        
        # Fetch related shipment
        shipment = order.logistics_shipments.filter(is_deleted=False).first()
        
        if not shipment:
            return Response(
                {"error": "Shipment not yet created. Invoice unavailable."}, 
                status=status.HTTP_404_NOT_FOUND
            )

        # Search EkartTrackingEvents for the 24-character hex orderId in raw_payload
        tracking_events = shipment.tracking_events.filter(is_deleted=False).order_by('-event_timestamp')
        mongo_order_id = None
        
        for event in tracking_events:
            payload = event.raw_payload or {}
            # Look for the strict 24-character hex ID required by Ekart's invoice API
            if "orderId" in payload and len(str(payload.get("orderId", ""))) == 24:
                mongo_order_id = payload["orderId"]
                break
                
        if not mongo_order_id:
            return Response({
                "error": "Internal logistics ID not yet synced. Please check back after tracking updates begin."
            }, status=status.HTTP_400_BAD_REQUEST)

        client = EkartClient()
        endpoint = "/integrations/order/invoice"
        
        # Ekart expects an array of objects.
        # We pass the extracted MongoDB orderId from the webhook payload.
        payload = [
            {
                "orderId": mongo_order_id 
            }
        ]

        try:
            response = client.request("POST", endpoint, payload=payload)
            data = response.get("data", {})
            
            # Check for successful response and presence of the invoice_link
            if response.get("status_code") == 200 and data.get("invoice_link"):
                invoice_url = data.get("invoice_link")
                
                # Fetch the raw PDF bytes from Ekart's GCP storage bucket
                pdf_response = requests.get(invoice_url, timeout=15)
                
                if pdf_response.status_code == 200:
                    # Return the PDF file directly to the client
                    http_response = HttpResponse(
                        pdf_response.content, 
                        content_type='application/pdf'
                    )
                    http_response['Content-Disposition'] = f'attachment; filename="Invoice-ORD-{order.id}.pdf"'
                    return http_response
                else:
                    return Response(
                        {"error": "Failed to download PDF from logistics provider."}, 
                        status=status.HTTP_502_BAD_GATEWAY
                    )
                    
            else:
                return Response({
                    "error": "Invoice generation failed or not ready.", 
                    "details": data.get("failed_requests", data)
                }, status=status.HTTP_400_BAD_REQUEST)

        except EkartAPIException as e:
            return Response({"error": str(e)}, status=status.HTTP_502_BAD_GATEWAY)
        except requests.RequestException as e:
            return Response({"error": "Error connecting to document storage."}, status=status.HTTP_502_BAD_GATEWAY)