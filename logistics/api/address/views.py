"""
logistics/api/address/views.py
==============================
Admin endpoints to sync, fetch, and create Pickup/Return locations in Ekart.
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status

from logistics.models import EkartAddress
from logistics.utils.ekart_client import EkartClient, EkartAPIException
from .serializers import EkartAddressSerializer

class EkartAddressView(APIView):
    """
    GET /api/logistics/address/
    POST /api/logistics/address/
    """
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        """
        Fetches all registered addresses from Ekart's servers and syncs 
        them with our local database to ensure data integrity.
        """
        client = EkartClient()
        try:
            response = client.request("GET", "/api/v2/addresses")
            data = response.get("data", [])
            
            # Sync live Ekart data to local DB
            if response["status_code"] == 200 and isinstance(data, list):
                for addr in data:
                    geo = addr.get("geo", {}) or {}
                    EkartAddress.objects.update_or_create(
                        alias=addr.get("alias"),
                        defaults={
                            "phone": str(addr.get("phone", "")),
                            "address_line1": addr.get("address_line1", ""),
                            "address_line2": addr.get("address_line2", ""),
                            "pincode": addr.get("pincode", 0),
                            "city": addr.get("city", ""),
                            "state": addr.get("state", ""),
                            "country": addr.get("country", "India"),
                            "latitude": geo.get("lat") if geo.get("lat") else None,
                            "longitude": geo.get("lon") if geo.get("lon") else None,
                            "is_deleted": False
                        }
                    )
            
            # Return our local synced data
            addresses = EkartAddress.objects.filter(is_deleted=False).order_by('alias')
            serializer = EkartAddressSerializer(addresses, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except EkartAPIException as e:
            return Response({"error": str(e)}, status=status.HTTP_502_BAD_GATEWAY)

    def post(self, request):
        """
        Registers a new address with Ekart. If successful, saves to local DB.
        """
        serializer = EkartAddressSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        
        valid_data = serializer.validated_data
        client = EkartClient()
        
        # Construct Ekart API Payload (Requires strict typings)
        payload = {
            "alias": valid_data["alias"],
            "phone": int(valid_data["phone"]),
            "address_line1": valid_data["address_line1"],
            "address_line2": valid_data.get("address_line2", ""),
            "pincode": int(valid_data["pincode"]),
            "city": valid_data.get("city", ""),
            "state": valid_data["state"],
            "country": valid_data.get("country", "India")
        }
        
        if valid_data.get("latitude") and valid_data.get("longitude"):
            payload["geo"] = {
                "lat": float(valid_data["latitude"]),
                "lon": float(valid_data["longitude"])
            }
        
        try:
            response = client.request("POST", "/api/v2/address", payload=payload)
            data = response.get("data", {})
            
            if response["status_code"] == 200 and data.get("status") is True:
                # Save locally now that Ekart has accepted it
                serializer.save()
                return Response({
                    "message": "Address successfully registered with Ekart.",
                    "address": serializer.data
                }, status=status.HTTP_201_CREATED)
            else:
                return Response({
                    "error": "Failed to register address with Ekart.",
                    "details": data
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except EkartAPIException as e:
            return Response({"error": str(e)}, status=status.HTTP_502_BAD_GATEWAY)