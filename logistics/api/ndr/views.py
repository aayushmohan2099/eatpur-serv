"""
logistics/api/ndr/views.py
==========================
Admin endpoints to manage failed deliveries via Ekart NDR API.
"""

import time
from datetime import datetime
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status

from logistics.models import EkartShipment, EkartNDRAction
from logistics.utils.ekart_client import EkartClient, EkartAPIException
from .serializers import NDRActionSerializer

class NDRActionView(APIView):
    """
    POST /api/logistics/ndr/action/
    
    Submits an NDR action (Re-Attempt or RTO) to Ekart and logs it locally.
    """
    permission_classes = [permissions.IsAdminUser]

    def post(self, request):
        serializer = NDRActionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        valid_data = serializer.validated_data
        tracking_id = valid_data["tracking_id"]
        action = valid_data["action"]
        
        shipment = EkartShipment.objects.get(tracking_id=tracking_id, is_deleted=False)
        client = EkartClient()
        
        # Build Ekart Payload
        payload = {
            "action": action,
            "wbn": tracking_id,
        }
        
        # Ekart requires the date in milliseconds since Unix Epoch
        if action == "Re-Attempt" and valid_data.get("reattempt_date"):
            date_obj = datetime.combine(valid_data["reattempt_date"], datetime.min.time())
            payload["date"] = int(time.mktime(date_obj.timetuple()) * 1000)
            
        if valid_data.get("updated_phone"):
            payload["phone"] = valid_data["updated_phone"]
        if valid_data.get("updated_address"):
            payload["address"] = valid_data["updated_address"]
        if valid_data.get("instructions"):
            payload["instructions"] = valid_data["instructions"]

        try:
            response = client.request("POST", "/api/v2/package/ndr", payload=payload)
            data = response.get("data", {})
            
            if response["status_code"] == 200 and data.get("status") is True:
                # Log the action in our database
                EkartNDRAction.objects.create(
                    shipment=shipment,
                    action=action,
                    reattempt_date=valid_data.get("reattempt_date"),
                    updated_phone=valid_data.get("updated_phone", ""),
                    updated_address=valid_data.get("updated_address", ""),
                    instructions=valid_data.get("instructions", ""),
                    is_processed=True
                )
                
                # Clear the NDR status flag locally since we took action
                shipment.ndr_status = f"Action Taken: {action}"
                shipment.save(update_fields=["ndr_status", "updated_at"])
                
                return Response({
                    "message": f"NDR Action '{action}' successfully submitted for {tracking_id}."
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    "error": "Failed to submit NDR action.",
                    "details": data
                }, status=status.HTTP_400_BAD_REQUEST)

        except EkartAPIException as e:
            return Response({"error": str(e)}, status=status.HTTP_502_BAD_GATEWAY)