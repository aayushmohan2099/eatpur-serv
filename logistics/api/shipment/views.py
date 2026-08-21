"""
logistics/api/shipment/views.py
===============================
Admin endpoints for creating, cancelling, and managing Ekart shipments.
"""

from decimal import Decimal
from django.utils import timezone
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
    
    Creates a new Ekart shipment for a specific SaleOrder and saves it to the DB.
    """
    permission_classes = [permissions.IsAdminUser]

    def post(self, request):
        serializer = CreateShipmentSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        valid_data = serializer.validated_data
        
        # 1. Retrieve the SaleOrder
        try:
            order = SaleOrder.objects.select_related('session__user').get(pk=valid_data["sale_order_id"])
        except SaleOrder.DoesNotExist:
            return Response({"error": "SaleOrder not found."}, status=status.HTTP_404_NOT_FOUND)

        # Prevent duplicate fulfillment
        if EkartShipment.objects.filter(sale_order=order, is_deleted=False).exclude(current_status="Cancelled").exists():
            return Response({"error": "An active shipment already exists for this order."}, status=status.HTTP_400_BAD_REQUEST)

        # 2. Extract Customer Data (Assuming address is stored in session geo_location or a related profile)
        # Note: Map these to your exact customer address fields
        user = order.session.user if order.session else None
        consignee_name = user.username if user else "Guest Customer"
        consignee_phone = user.mobile if user else "0000000000"
        
        # 3. Calculate Financials
        total_amount = order.total_amount
        # Simplified taxation math for the payload (Assuming 5% GST included)
        taxable_amount = round(total_amount / Decimal('1.05'), 2)
        tax_value = round(total_amount - taxable_amount, 2)
        cod_amount = total_amount if valid_data["payment_mode"] == "COD" else Decimal('0.00')

        # 4. Build Ekart Payload
        order_number = f"EP-{order.pk}-{timezone.now().strftime('%Y%m%d%H%M')}"
        
        payload = {
            "seller_name": "EatPur Naturals LLP",
            "seller_address": "EatPur Warehouse", # Update to your registered billing address
            "seller_gst_tin": "YOUR_GST_NUMBER",  # Update to your GSTIN
            "order_number": order_number,
            "invoice_number": f"INV-{order.pk}",
            "invoice_date": timezone.now().strftime("%Y-%m-%d"),
            "consignee_name": consignee_name,
            "consignee_alternate_phone": consignee_phone,
            "products_desc": "EatPur Nutritional Products",
            "payment_mode": valid_data["payment_mode"],
            "category_of_goods": "Grocery",
            "total_amount": float(total_amount),
            "taxable_amount": float(taxable_amount),
            "tax_value": float(tax_value),
            "commodity_value": str(float(taxable_amount)),
            "cod_amount": float(cod_amount),
            "quantity": 1, # Base package quantity
            "weight": valid_data["weight"],
            "length": valid_data["length"],
            "height": valid_data["height"],
            "width": valid_data["width"],
            "delayed_dispatch": valid_data["delayed_dispatch"],
            "obd_shipment": valid_data["obd_shipment"],
            
            # The exact alias registered with Ekart
            "pickup_location": {
                "name": valid_data["pickup_location_alias"]
            },
            
            # Customer Drop Location
            "drop_location": {
                "name": consignee_name,
                "phone": consignee_phone,
                "address": "Customer Address Line 1", # Map from your DB
                "city": "Lucknow",                    # Map from your DB
                "state": "UP",                        # Map from your DB
                "pincode": 226010                     # Map from your DB
            }
        }

        # 5. Call Ekart API
        client = EkartClient()
        try:
            response = client.request("PUT", "/api/v1/package/create", payload=payload)
            data = response.get("data", {})
            
            if response["status_code"] == 200 and data.get("status") is True:
                # 6. Save to our Database
                pickup_addr = EkartAddress.objects.get(alias=valid_data["pickup_location_alias"])
                
                shipment = EkartShipment.objects.create(
                    sale_order=order,
                    user=user,
                    tracking_id=data.get("tracking_id"),
                    order_number=order_number,
                    invoice_number=payload["invoice_number"],
                    invoice_date=timezone.now().date(),
                    consignee_name=consignee_name,
                    consignee_phone=consignee_phone,
                    payment_mode=valid_data["payment_mode"],
                    service_type=valid_data["service_type"],
                    products_desc=payload["products_desc"],
                    pickup_location_alias=pickup_addr,
                    drop_location_json=payload["drop_location"],
                    total_amount=total_amount,
                    taxable_amount=taxable_amount,
                    tax_value=tax_value,
                    cod_amount=cod_amount,
                    quantity=payload["quantity"],
                    weight=payload["weight"],
                    length=payload["length"],
                    height=payload["height"],
                    width=payload["width"],
                    delayed_dispatch=payload["delayed_dispatch"],
                    obd_shipment=payload["obd_shipment"],
                    current_status="Shipment Created",
                    barcodes_json=data.get("barcodes", {})
                )
                
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