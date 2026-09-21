"""
logistics/api/webhooks/views.py
===============================
Webhook receiver for automated Ekart status updates.
"""

import hmac
import hashlib
import json
import logging
from datetime import datetime
from django.utils.timezone import make_aware
from django.conf import settings
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
    """
    # Webhooks must be publicly accessible, security relies on HMAC signatures
    permission_classes = [permissions.AllowAny]

    def _verify_signature(self, request):
        """
        Verifies the Ekart webhook HMAC signature.
        Ekart usually passes this in the 'X-Ekart-Signature' or similar header.
        """
        secret = "EatPurEkartSecret2026!"
        if not secret:
            # If no secret is configured, bypass check (Not recommended for prod)
            return True
            
        received_signature = request.headers.get("X-Ekart-Signature")
        if not received_signature:
            return False
            
        # Calculate expected HMAC SHA256 of the raw body
        expected_signature = hmac.new(
            secret, 
            request.body, 
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(expected_signature, received_signature)

    def post(self, request):
        # 1. Security Check
        if not self._verify_signature(request):
            logger.warning("Ekart Webhook: Invalid or missing HMAC signature.")
            return Response({"error": "Unauthorized webhook signature."}, status=status.HTTP_401_UNAUTHORIZED)

        payload = request.data
        
        # Determine the event type from payload structure
        # (Ekart payload for track_updated includes "ctime" and "status")
        is_tracking_update = "status" in payload and "ctime" in payload
        tracking_id = payload.get("id")

        if not tracking_id:
            logger.error(f"Ekart Webhook Error: Payload missing tracking 'id'. Payload: {payload}")
            return Response({"error": "Missing tracking ID."}, status=status.HTTP_400_BAD_REQUEST)

        # 2. Find Associated Shipment
        try:
            shipment = EkartShipment.objects.get(tracking_id=tracking_id, is_deleted=False)
        except EkartShipment.DoesNotExist:
            logger.warning(f"Ekart Webhook: Received update for unknown shipment ID: {tracking_id}")
            # Return 200 so Ekart doesn't retry infinitely for a shipment we don't have
            return Response({"status": "ignored", "reason": "Shipment not found."}, status=status.HTTP_200_OK)

        # 3. Process Tracking Update
        if is_tracking_update:
            ekart_status = payload.get("status", "Unknown")
            ekart_ctime_ms = payload.get("ctime", 0)
            
            # Convert Ekart millisecond epoch to Aware Datetime
            if ekart_ctime_ms:
                event_time = make_aware(datetime.fromtimestamp(ekart_ctime_ms / 1000.0))
            else:
                from django.utils import timezone
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

            logger.info(f"Ekart Webhook: Shipment {tracking_id} updated to {ekart_status}.")
            return Response({"status": "success"}, status=status.HTTP_200_OK)
            
        else:
            # Handle shipment_created / shipment_recreated event
            # Currently we create shipments from our end, but if recreated by Ekart:
            logger.info(f"Ekart Webhook: Received non-tracking event for {tracking_id}. Payload: {payload}")
            return Response({"status": "acknowledged"}, status=status.HTTP_200_OK)