"""
logistics/api/serviceability/views.py
=====================================
Endpoints for checking pincode serviceability and estimating shipping rates.
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status

from logistics.utils.ekart_client import EkartClient, EkartAPIException
from .serializers import ShippingEstimateSerializer

class CheckPincodeServiceabilityView(APIView):
    """
    GET /api/logistics/serviceability/check/<pincode>/
    
    Checks if Ekart delivers to a specific pincode.
    Publicly accessible so guests can check delivery availability.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request, pincode):
        client = EkartClient()
        endpoint = f"/api/v2/serviceability/{pincode}"
        
        try:
            # Ekart returns a status boolean inside the response body
            response = client.request("GET", endpoint)
            data = response.get("data", {})
            
            if response["status_code"] == 200 and data.get("status") is True:
                return Response({
                    "is_serviceable": True,
                    "pincode": data.get("pincode"),
                    "details": data.get("details", {})
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    "is_serviceable": False,
                    "pincode": pincode,
                    "message": "Delivery is currently not available for this pincode."
                }, status=status.HTTP_200_OK)
                
        except EkartAPIException as e:
            return Response({"error": str(e)}, status=status.HTTP_502_BAD_GATEWAY)


class ShippingEstimateView(APIView):
    """
    POST /api/logistics/serviceability/estimate/
    
    Fetches real-time shipping rate estimates from Ekart based on 
    weight, dimensions, and distance (pickup vs drop pincode).
    """
    permission_classes = [permissions.AllowAny] # Allow guests in checkout

    def post(self, request):
        serializer = ShippingEstimateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        valid_data = serializer.validated_data
        client = EkartClient()
        endpoint = "/data/pricing/estimate"
        
        # Ekart Payload Mapping
        payload = {
            "pickupPincode": valid_data["pickupPincode"],
            "dropPincode": valid_data["dropPincode"],
            "invoiceAmount": valid_data["invoiceAmount"],
            "weight": valid_data["weight"],
            "length": valid_data["length"],
            "height": valid_data["height"],
            "width": valid_data["width"],
            "serviceType": valid_data["serviceType"],
            "codAmount": valid_data["codAmount"]
        }

        try:
            response = client.request("POST", endpoint, payload=payload)
            data = response.get("data", {})
            
            if response["status_code"] == 200 and "total" in data:
                return Response({
                    "success": True,
                    "pricing": {
                        "shipping_charge": data.get("shippingCharge"),
                        "rto_charge": data.get("rtoCharge"),
                        "cod_charge": data.get("codCharge"),
                        "fuel_surcharge": data.get("fuelSurcharge"),
                        "taxes": data.get("taxes"),
                        "total_estimated_cost": data.get("total"),
                        "billing_weight": data.get("billingWeight"),
                        "zone": data.get("zone")
                    }
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    "success": False,
                    "message": "Failed to calculate shipping estimate.",
                    "ekart_response": data
                }, status=status.HTTP_400_BAD_REQUEST)

        except EkartAPIException as e:
            return Response({"error": str(e)}, status=status.HTTP_502_BAD_GATEWAY)