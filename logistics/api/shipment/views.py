"""
logistics/api/shipment/views.py
===============================
Admin endpoints for creating, cancelling, and managing Ekart shipments.
"""

import uuid
from decimal import Decimal
from django.utils import timezone
from django.db import transaction
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status

from shop.models import SaleOrder
from logistics.models import EkartShipment, EkartAddress
from logistics.utils.ekart_client import EkartClient, EkartAPIException

from .serializers import (
    CreateShipmentSerializer, 
    TrackingIdListSerializer, 
    CancelShipmentSerializer
)

class CreateShipmentView(APIView):
    """
    POST /api/logistics/shipment/create/
    Maps SaleOrder to Ekart, handles Single/Multi package logic, and fetches Tracking ID.
    Exact replica of VerifyPaymentView's DB logic, but allows dimension overrides.
    """
    permission_classes = [permissions.IsAdminUser]

    @transaction.atomic
    def post(self, request):
        serializer = CreateShipmentSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        valid_data = serializer.validated_data
        sale_order_id = valid_data["sale_order_id"]
        
        # Extract Optional Priority Overrides
        req_weight = valid_data.get("weight")
        req_length = valid_data.get("length")
        req_height = valid_data.get("height")
        req_width = valid_data.get("width")
        items_dimensions = valid_data.get("items_dimensions") or {}
        
        # 1. Retrieve the SaleOrder and its OrderProducts
        try:
            # Lock the order row to prevent race conditions
            order = SaleOrder.objects.select_related('session__user').select_for_update().get(pk=sale_order_id)
        except SaleOrder.DoesNotExist:
            return Response({"error": "SaleOrder not found."}, status=status.HTTP_404_NOT_FOUND)

        if order.payment_status != "PAID":
            return Response({"error": "Order must be PAID before dispatching Prepaid shipments."}, status=status.HTTP_400_BAD_REQUEST)

        if EkartShipment.objects.filter(sale_order=order, is_deleted=False).exclude(current_status="Cancelled").exists():
            return Response({"error": "An active shipment already exists for this order."}, status=status.HTTP_400_BAD_REQUEST)

        order_products = list(order.order_products.select_related('product__category', 'product__shipping_dimension').all())
        if not order_products:
            return Response({"error": "No products found in this order to ship."}, status=status.HTTP_400_BAD_REQUEST)

        is_mps = len(order_products) > 1

        # 2. Extract Financials
        total_amount = float(order.total_amount)
        taxable_amount = round(total_amount / 1.05, 2)  # Assuming 5% flat GST
        tax_value = round(total_amount - taxable_amount, 2)

        order_number = f"EP-{order.pk}-{uuid.uuid4().hex[:6].upper()}"

        # 3. Base Ekart Payload (Directly from SaleOrder DB)
        payload = {
            "seller_name": "Eatpur Naturals LLP",
            "seller_address": "5/77 vikas nagar, lucknow, UP, Lucknow, UP, 226022",
            "seller_gst_tin": "09ABCDE1234F1Z5", 
            "seller_gst_amount": 0,
            "consignee_gst_amount": 0,
            "integrated_gst_amount": 0,                    
            "order_number": order_number,
            "invoice_number": f"INV-{order.pk}",
            "invoice_date": timezone.now().strftime("%Y-%m-%d"),
            "consignee_name": order.consignee_name,
            "consignee_alternate_phone": order.consignee_alternate_phone,
            "payment_mode": "Prepaid",
            "total_amount": taxable_amount,
            "taxable_amount": taxable_amount,
            "tax_value": tax_value,
            "commodity_value": str(taxable_amount),
            "cod_amount": 0,
            "delayed_dispatch": False,
            "obd_shipment": False,
            "mps": is_mps,
            "pickup_location": {
                "name": order.pickup_location_alias or "Primary Warehouse"
            },
            "drop_location": {
                "name": order.consignee_name,
                "phone": int(order.consignee_phone) if str(order.consignee_phone).isdigit() else 9999999999,
                "address": order.drop_location,
                "city": order.drop_city,
                "state": order.drop_state,
                "country": "India",
                "pin": int(order.drop_pincode) if str(order.drop_pincode).isdigit() else 226022
            }
        }

        if order.preferred_dispatch_date:
            payload["preferred_dispatch_date"] = order.preferred_dispatch_date.strftime("%Y-%m-%d")

        # 4. Handle Single Product vs Multiple Products (MPS) with PRIORITY OVERRIDES
        if not is_mps:
            op = order_products[0]
            prod = op.product
            dim = getattr(prod, 'shipping_dimension', None)
            item_override = items_dimensions.get(str(prod.id), {})

            payload["products_desc"] = prod.description or "Eatpur Product"
            payload["category_of_goods"] = prod.category.name if prod.category else "Grocery"
            payload["quantity"] = op.quantity
            
            # Priority Fallback: Global Override -> Item Override -> Database -> Default
            payload["weight"] = req_weight or item_override.get("weight") or (dim.weight * op.quantity if dim else 500)
            payload["length"] = req_length or item_override.get("length") or (dim.length if dim else 10)
            payload["height"] = req_height or item_override.get("height") or (dim.height if dim else 10)
            payload["width"]  = req_width or item_override.get("width") or (dim.width if dim else 10)

        else:
            payload["products_desc"] = "Multiple Products"
            payload["category_of_goods"] = "Grocery"
            
            total_qty, total_weight, total_length, total_height, total_width = 0, 0, 0, 0, 0
            items_array = []

            for op in order_products:
                prod = op.product
                dim = getattr(prod, 'shipping_dimension', None)
                item_override = items_dimensions.get(str(prod.id), {})

                # Priority Fallback: Item Override -> Database -> Default
                w = item_override.get("weight") or (dim.weight if dim else 500)
                l = item_override.get("length") or (dim.length if dim else 10)
                h = item_override.get("height") or (dim.height if dim else 10)
                wd = item_override.get("width") or (dim.width if dim else 10)

                total_qty += op.quantity
                total_weight += (int(w) * op.quantity)
                total_length += int(l)
                total_height += int(h)
                total_width += int(wd)

                items_array.append({
                    "product_name": prod.name,
                    "sku": prod.pid,
                    "description": prod.description or "Eatpur Product",
                    "quantity": op.quantity,
                    "weight": int(w),
                    "length": int(l),
                    "height": int(h),
                    "breadth": int(wd),
                    "taxable_value": float(op.price_at_purchase)
                })

            # Priority Fallback for Grand Totals: Global Override -> Aggregated Calculations
            payload.update({
                "quantity": total_qty, 
                "weight": req_weight or total_weight,
                "length": req_length or total_length, 
                "height": req_height or total_height, 
                "width": req_width or total_width,
                "items": items_array
            })

        # 5. Call Ekart API
        try:
            client = EkartClient()
            response = client.request("PUT", "/api/v1/package/create", payload=payload)
            data = response.get("data", {})
            
            if response["status_code"] == 200 and data.get("status") is True:
                pickup_addr = EkartAddress.objects.filter(alias=order.pickup_location_alias, is_deleted=False).first()
                
                # 6. Save Shipment Record
                shipment = EkartShipment.objects.create(
                    sale_order=order,
                    user=order.session.user if order.session else None,
                    tracking_id=data.get("tracking_id"),
                    order_number=order_number,
                    invoice_number=payload["invoice_number"],
                    invoice_date=timezone.now().date(),
                    consignee_name=payload["drop_location"]["name"],
                    consignee_phone=payload["drop_location"]["phone"],
                    payment_mode="Prepaid",
                    service_type=order.service_type,
                    products_desc=payload["products_desc"],
                    pickup_location_alias=pickup_addr,
                    drop_location_json=payload["drop_location"],
                    total_amount=payload["total_amount"],
                    taxable_amount=payload["taxable_amount"],
                    tax_value=payload["tax_value"],
                    cod_amount=0.00,
                    quantity=payload["quantity"],
                    weight=payload["weight"],
                    length=payload["length"],
                    height=payload["height"],
                    width=payload["width"],
                    delayed_dispatch=False,
                    obd_shipment=False,
                    mps=is_mps,
                    current_status="Shipment Created",
                    barcodes_json=data.get("barcodes", {})
                )
                
                # 7. Update SaleOrder Fulfillment Status
                order.fulfillment_status = "PROCESSING"
                order.save(update_fields=["fulfillment_status", "updated_at"])
                
                return Response({
                    "message": "Shipment successfully created.",
                    "tracking_id": shipment.tracking_id,
                    "barcodes": shipment.barcodes_json
                }, status=status.HTTP_201_CREATED)
            else:
                return Response({
                    "error": "Failed to create shipment in Ekart.",
                    "details": data
                }, status=status.HTTP_400_BAD_REQUEST)

        except EkartAPIException as e:
            return Response({"error": str(e)}, status=status.HTTP_502_BAD_GATEWAY)


class CancelShipmentView(APIView):
    """
    DELETE /api/logistics/shipment/cancel/
    
    Cancels a shipment via Ekart API and updates the local status.
    """
    permission_classes = [permissions.IsAdminUser]

    def delete(self, request):
        serializer = CancelShipmentSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        tracking_id = serializer.validated_data["tracking_id"]
        
        try:
            shipment = EkartShipment.objects.get(tracking_id=tracking_id, is_deleted=False)
        except EkartShipment.DoesNotExist:
            return Response({"error": "Shipment not found in database."}, status=status.HTTP_404_NOT_FOUND)

        client = EkartClient()
        try:
            response = client.request("DELETE", "/api/v1/package/cancel", params={"tracking_id": tracking_id})
            
            if response["status_code"] == 200:
                shipment.current_status = "Cancelled"
                shipment.save(update_fields=["current_status", "updated_at"])
                return Response({"message": f"Shipment {tracking_id} successfully cancelled."}, status=status.HTTP_200_OK)
            else:
                return Response({"error": "Failed to cancel shipment.", "details": response.get("data")}, status=status.HTTP_400_BAD_REQUEST)
                
        except EkartAPIException as e:
            return Response({"error": str(e)}, status=status.HTTP_502_BAD_GATEWAY)


class GenerateLabelView(APIView):
    """
    POST /api/logistics/shipment/labels/
    
    Fetches JSON data containing the PDF labels for the requested tracking IDs.
    """
    permission_classes = [permissions.IsAdminUser]

    def post(self, request):
        serializer = TrackingIdListSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        client = EkartClient()
        payload = {"ids": serializer.validated_data["tracking_ids"]}
        
        try:
            # We request json_only=true so the API returns clean JSON instead of a raw PDF binary
            response = client.request("POST", "/api/v1/package/label", payload=payload, params={"json_only": "true"})
            
            if response["status_code"] == 200:
                return Response(response["data"], status=status.HTTP_200_OK)
            else:
                return Response({"error": "Failed to fetch labels.", "details": response.get("data")}, status=status.HTTP_400_BAD_REQUEST)

        except EkartAPIException as e:
            return Response({"error": str(e)}, status=status.HTTP_502_BAD_GATEWAY)


class GenerateManifestView(APIView):
    """
    POST /api/logistics/shipment/manifest/
    
    Generates a pickup manifest URL for the courier boy.
    """
    permission_classes = [permissions.IsAdminUser]

    def post(self, request):
        serializer = TrackingIdListSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        client = EkartClient()
        payload = {"ids": serializer.validated_data["tracking_ids"]}
        
        try:
            response = client.request("POST", "/data/v2/generate/manifest", payload=payload)
            data = response.get("data", {})
            
            if response["status_code"] == 200 and "manifestDownloadUrl" in data:
                return Response({
                    "manifest_number": data.get("manifestNumber"),
                    "download_url": data.get("manifestDownloadUrl")
                }, status=status.HTTP_200_OK)
            else:
                return Response({"error": "Failed to generate manifest.", "details": data}, status=status.HTTP_400_BAD_REQUEST)

        except EkartAPIException as e:
            return Response({"error": str(e)}, status=status.HTTP_502_BAD_GATEWAY)