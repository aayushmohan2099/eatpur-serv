"""
logistics/api/tracking/views.py
===============================
Endpoints for querying shipment tracking status.
"""

from datetime import datetime
from django.utils.timezone import make_aware
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status

from logistics.models import EkartShipment, EkartTrackingEvent
from logistics.utils.ekart_client import EkartClient, EkartAPIException
from .serializers import CustomerShipmentTrackingSerializer

class CustomerTrackingView(APIView):
    """
    GET /api/logistics/tracking/customer/<tracking_id>/
    
    Lightweight, read-only endpoint for the customer dashboard.
    Queries the local DB so it loads instantly without hitting Ekart rate limits.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, tracking_id):
        try:
            # Ensure the requesting user actually owns this shipment
            shipment = EkartShipment.objects.prefetch_related('tracking_events').get(
                tracking_id=tracking_id, 
                user=request.user,
                is_deleted=False
            )
            serializer = CustomerShipmentTrackingSerializer(shipment)
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except EkartShipment.DoesNotExist:
            return Response(
                {"error": "Shipment not found or access denied."}, 
                status=status.HTTP_404_NOT_FOUND
            )


class LiveEkartTrackingSyncView(APIView):
    """
    GET /api/logistics/tracking/sync/<tracking_id>/
    
    Admin-only endpoint. Forces a live sync from Ekart's /api/v1/track/{id} endpoint
    and updates our local database. Used if webhooks fail or get delayed.
    """
    permission_classes = [permissions.IsAdminUser]

    def get(self, request, tracking_id):
        try:
            shipment = EkartShipment.objects.get(tracking_id=tracking_id, is_deleted=False)
        except EkartShipment.DoesNotExist:
            return Response({"error": "Shipment not found in local database."}, status=status.HTTP_404_NOT_FOUND)

        client = EkartClient()
        endpoint = f"/api/v1/track/{tracking_id}"
        
        try:
            response = client.request("GET", endpoint)
            track_data = response.get("data", {}).get("track", {})
            
            if response["status_code"] == 200 and track_data:
                # Ekart timestamps are in milliseconds (Unix Epoch)
                ekart_ctime_ms = track_data.get("ctime", 0)
                if ekart_ctime_ms:
                    event_time = make_aware(datetime.fromtimestamp(ekart_ctime_ms / 1000.0))
                else:
                    from django.utils import timezone
                    event_time = timezone.now()

                ekart_status = track_data.get("status", "Unknown")
                
                # Check if this exact event is already recorded to avoid duplicates
                event_exists = EkartTrackingEvent.objects.filter(
                    shipment=shipment,
                    status=ekart_status,
                    event_timestamp=event_time
                ).exists()

                if not event_exists:
                    # 1. Create the Tracking Event
                    EkartTrackingEvent.objects.create(
                        shipment=shipment,
                        status=ekart_status,
                        description=track_data.get("desc", ""),
                        location=track_data.get("location", ""),
                        event_timestamp=event_time,
                        ndr_status=track_data.get("ndrStatus", ""),
                        attempts=int(track_data.get("attempts", 0)),
                        raw_payload=track_data
                    )
                    
                    # 2. Update the main Shipment record
                    shipment.current_status = ekart_status
                    if ekart_status.lower() == "delivered":
                        shipment.is_delivered = True
                    shipment.save(update_fields=["current_status", "is_delivered", "updated_at"])

                return Response({
                    "message": "Tracking synced successfully.",
                    "current_status": shipment.current_status,
                    "is_delivered": shipment.is_delivered
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    "error": "Failed to fetch tracking from Ekart.",
                    "details": response.get("data")
                }, status=status.HTTP_400_BAD_REQUEST)

        except EkartAPIException as e:
            return Response({"error": str(e)}, status=status.HTTP_502_BAD_GATEWAY)