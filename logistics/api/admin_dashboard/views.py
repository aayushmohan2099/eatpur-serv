"""
logistics/api/admin_dashboard/views.py
======================================
Analytics, KPI metrics, and API Audit logs for the EatPur admin panel.
"""

from django.db.models import Sum, Count, Q
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework import permissions, status

from logistics.models import EkartShipment, LogisticsAPILog
from .serializers import LogisticsAPILogSerializer

class LogisticsOverviewStatsView(APIView):
    """
    GET /api/logistics/dashboard/overview/
    
    Returns high-level KPIs for active logistics operations.
    """
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        qs = EkartShipment.objects.filter(is_deleted=False)
        
        total_shipped = qs.count()
        delivered = qs.filter(is_delivered=True).count()
        
        # Approximate "In Transit" based on status strings mapped from Ekart
        in_transit = qs.filter(
            Q(current_status__icontains="Transit") | 
            Q(current_status__icontains="Dispatched") |
            Q(current_status__icontains="Out for Delivery")
        ).count()
        
        rtos = qs.filter(current_status__icontains="RTO").count()
        
        # Pending NDRs (Shipments that have an NDR status but aren't delivered/RTO'd yet)
        pending_ndrs = qs.filter(ndr_status__isnull=False).exclude(ndr_status="").exclude(is_delivered=True).count()

        return Response({
            "total_shipped": total_shipped,
            "delivered": delivered,
            "in_transit": in_transit,
            "rtos": rtos,
            "pending_ndrs": pending_ndrs,
            "success_rate": round((delivered / total_shipped * 100) if total_shipped > 0 else 0, 2)
        }, status=status.HTTP_200_OK)


class ShippingCostAnalyticsView(APIView):
    """
    GET /api/logistics/dashboard/financials/
    
    Aggregates order values and COD amounts processed through the logistics pipeline.
    """
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        qs = EkartShipment.objects.filter(is_deleted=False)
        
        metrics = qs.aggregate(
            total_gmv=Sum('total_amount'),
            total_cod_pending=Sum('cod_amount', filter=Q(payment_mode="COD", is_delivered=False)),
            total_cod_collected=Sum('cod_amount', filter=Q(payment_mode="COD", is_delivered=True)),
        )
        
        return Response({
            "gross_merchandise_value_shipped": metrics["total_gmv"] or 0.00,
            "cod_pending_collection": metrics["total_cod_pending"] or 0.00,
            "cod_successfully_collected": metrics["total_cod_collected"] or 0.00,
        }, status=status.HTTP_200_OK)


class APIAuditLogView(ListAPIView):
    """
    GET /api/logistics/dashboard/audit-logs/
    
    Paginated view of every API request made to Ekart. Essential for debugging.
    """
    permission_classes = [permissions.IsAdminUser]
    serializer_class = LogisticsAPILogSerializer
    
    def get_queryset(self):
        # Allow filtering by status_code (e.g., ?status=400 to find errors)
        qs = LogisticsAPILog.objects.all().order_by("-created_at")
        status_code = self.request.query_params.get("status")
        if status_code:
            qs = qs.filter(status_code=status_code)
        return qs