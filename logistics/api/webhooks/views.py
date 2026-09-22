"""
logistics/api/webhooks/views.py
===============================
Webhook receiver for automated Ekart status updates.
"""

import logging
from datetime import datetime
from django.utils.timezone import make_aware
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status

from logistics.models import EkartShipment, EkartTrackingEvent

logger = logging.getLogger("logistics")

class EkartWebhookReceiverView(APIView):
    """
    POST /api/logistics/webhooks/ekart/
    
    Listens for 'track_updated', 'shipment_created', and 'shipment_recreated' 
    events pushed by Ekart servers.
    
    SECURITY: Public webhook receiver. No signature verification applied.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        payload = request.data
        
        # Determine the event type from payload structure
        # (Ekart payload for track_updated includes "ctime" and "status")
        is_tracking_update = "status" in payload and "ctime" in payload
        tracking_id = payload.get("id")

        if not tracking_id:
            logger.error(f"Ekart Webhook Error: Payload missing tracking 'id'. Payload: {payload}")
            return Response({"error": "Missing tracking ID."}, status=status.HTTP_400_BAD_REQUEST)

        # 1. Find Associated Shipment
        try:
            shipment = EkartShipment.objects.get(tracking_id=tracking_id, is_deleted=False)
        except EkartShipment.DoesNotExist:
            logger.warning(f"Ekart Webhook: Received update for unknown shipment ID: {tracking_id}")
            # Return 200 so Ekart doesn't retry infinitely for a shipment we don't have
            return Response({"status": "ignored", "reason": "Shipment not found."}, status=status.HTTP_200_OK)

        # 2. Process Tracking Update
        if is_tracking_update:
            ekart_status = payload.get("status", "Unknown")
            ekart_ctime_ms = payload.get("ctime", 0)
            
            # Convert Ekart millisecond epoch to Aware Datetime
            if ekart_ctime_ms:
                event_time = make_aware(datetime.fromtimestamp(ekart_ctime_ms / 1000.0))
            else:
                event_time = timezone.now()

            # Create event log
            EkartTrackingEvent.objects.create(
                shipment=shipment,
                status=ekart_status,
                description=payload.get("desc", ""),
                location=payload.get("location", ""),
                event_timestamp=event_time,
                attempts=int(payload.get("attempts", 0)),
                raw_payload=payload
            )

            # Update master shipment status
            shipment.current_status = ekart_status
            if ekart_status.lower() == "delivered":
                shipment.is_delivered = True
            shipment.save(update_fields=["current_status", "is_delivered", "updated_at"])

            # 3. Synchronize Status with Customer's SaleOrder
            if shipment.sale_order:
                order = shipment.sale_order
                status_lower = ekart_status.lower()
                
                # Map Ekart statuses to native FULFILLMENT_STATUS_CHOICES
                if status_lower == "delivered":
                    order.fulfillment_status = "DELIVERED"
                elif "cancel" in status_lower or "rto" in status_lower or "return" in status_lower:
                    order.fulfillment_status = "CANCELLED"
                elif status_lower not in ["created", "pending", "processing", "shipment created"]:
                    # Any transit event (picked up, in transit, out for delivery) marks it SHIPPED
                    order.fulfillment_status = "SHIPPED"
                    
                order.save(update_fields=["fulfillment_status", "updated_at"])

            logger.info(f"Ekart Webhook: Shipment {tracking_id} updated to {ekart_status}.")
            return Response({"status": "success"}, status=status.HTTP_200_OK)
            
        else:
            # Handle shipment_created / shipment_recreated event
            logger.info(f"Ekart Webhook: Received non-tracking event for {tracking_id}. Payload: {payload}")
            return Response({"status": "acknowledged"}, status=status.HTTP_200_OK)