import requests
from django.http import HttpResponse
from rest_framework.generics import ListAPIView
from django.template.loader import get_template
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
from django.utils.dateparse import parse_date
from django.shortcuts import get_object_or_404
from xhtml2pdf import pisa
from num2words import num2words
from django.utils import timezone
import math

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

class LocalInvoiceGenerateView(APIView):
    """
    GET /api/shop/customer/invoices/<order_id>/local-data/
    Frontend ko invoice HTML render karne ke liye JSON data deta hai.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, order_id):
        
        order = get_object_or_404(
            SaleOrder,
            id=order_id,
            session__user=request.user,
            payment_status="PAID",
            is_deleted=False,
        )

        order_products = order.order_products.select_related('product', 'coupon').all()

        
        sum_of_all_items = 0.0
        for item in order_products:
            sum_of_all_items += float(item.price_at_purchase) * item.quantity

        grand_total = float(order.total_amount)
        
        
        global_discount = max(0.0, sum_of_all_items - grand_total)

        items_data = []
        total_taxable_amount = 0.0
        total_tax_amount = 0.0

        
        for item in order_products:
            unit_price_inclusive = float(item.price_at_purchase) 
            quantity = item.quantity
            item_total_inclusive = unit_price_inclusive * quantity
            
            
            item_ratio = item_total_inclusive / sum_of_all_items if sum_of_all_items > 0 else 0
            
            
            item_discount = global_discount * item_ratio
            
          
            discounted_item_total = item_total_inclusive - item_discount

            
            tax_rate = float(item.tax_rate) if item.tax_rate else 5.0
            
            
            divisor = 1 + (tax_rate / 100.0)
            
           
            taxable_amount = round(discounted_item_total / divisor, 2)
            tax_value = round(discounted_item_total - taxable_amount, 2)

            total_taxable_amount += taxable_amount
            total_tax_amount += tax_value

            if item.product:
                full_name = getattr(item.product, 'description', item.product.name)
            else:
                full_name = "Unknown Product"

            applied_coupon = getattr(item.coupon, 'code', "None") if item.coupon else "None"

           
            unit_price_exclusive = round((discounted_item_total / quantity) / divisor, 2) if quantity else 0

            items_data.append({
                "product_name": full_name,
                "unit_price": unit_price_exclusive, 
                
                "quantity": quantity,
                "item_discount": round(item_discount, 2), 
                "taxable_amount": taxable_amount,
                "tax_rate": f"{tax_rate}%",
                "tax_value": tax_value,
                "tax_type": "IGST",
                
                "subtotal": round(discounted_item_total, 2), 
                "applied_coupon": applied_coupon
            })

        
        rupees = math.floor(grand_total)
        paise = int(round((grand_total - rupees) * 100))

        rupees_text = num2words(rupees, lang='en_IN').title() + " Rupees"
        if paise > 0:
            amount_in_words = f"{rupees_text} And {num2words(paise, lang='en_IN').title()} Paise Only"
        else:
            amount_in_words = f"{rupees_text} Only"

        formatted_order_date = order.order_date.strftime('%d-%m-%Y %I:%M %p') if order.order_date else "N/A"
        formatted_invoice_date = timezone.now().strftime('%d-%m-%Y')  

        response_data = {
            "company_info": {
                "name": "Eatpur Naturals LLP",
                "address": "5/77 Vikas Nagar Lucknow - 226022 Uttar Pradesh India",
                "gstin": "09AAMFE9616Q1ZH",
            },
            "invoice_details": {
                "invoice_number": f"INV-{order.id}",
                "date": formatted_invoice_date,      
                "order_date": formatted_order_date,
                "order_id": f"EP-{order.id}",
                "payment_mode": "Prepaid" if order.payment_status == "PAID" else "COD",
            },
            "customer_info": {
                "name": order.consignee_name or request.user.username,
                "address": order.drop_location or "N/A",
                "city": order.drop_city or "N/A",
                "state": order.drop_state or "N/A",
                "country": "India", 
                "pincode": order.drop_pincode or "N/A",
                "phone": order.consignee_phone or getattr(request.user, "mobile", "N/A"),
            },
            "items": items_data,
            "totals": {
                "total_mrp": round(sum_of_all_items, 2),
                "taxable_amount": round(total_taxable_amount, 2),
                "total_tax_amount": round(total_tax_amount, 2),
                "discount": round(global_discount, 2),
                "grand_total": round(grand_total, 2),
                "amount_in_words": amount_in_words,
            },
        }

        return Response(
            response_data,
            status=status.HTTP_200_OK,
        )