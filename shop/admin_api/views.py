from django.db.models import Q, Count, Sum
from django.shortcuts import get_object_or_404
from rest_framework.generics import ListAPIView
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
from datetime import datetime, time
from django.utils import timezone
from shop.models import SaleOrder
from .serializers import AdminSaleOrderListSerializer

class AdminOrderListView(ListAPIView):
    """
    GET /api/shop/admin/orders/
    
    1) ALL ORDERS with dynamic filters.
    2) Active (Paid): ?payment_status=PAID&fulfillment_status=UNFULFILLED
    3) Processing: ?fulfillment_status=PROCESSING
    4) Delivered: ?fulfillment_status=DELIVERED
    5) Returned: ?is_returned=true
    """
    permission_classes = [permissions.IsAdminUser]
    serializer_class = AdminSaleOrderListSerializer

    def get_queryset(self):
        # YAHAN UPDATE HUA HAI: 'order_products__product__media' add kiya gaya hai fast image loading ke liye
        qs = SaleOrder.objects.filter(is_deleted=False).select_related('session__user').prefetch_related(
            'order_products__product__media', 
            'logistics_shipments'
        )

        # Core Filters
        payment_status = self.request.query_params.get('payment_status')
        fulfillment_status = self.request.query_params.get('fulfillment_status')
        is_returned = self.request.query_params.get('is_returned')
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')        
        search = self.request.query_params.get('search')

        # Date Filters
        if date_from:
            try:
                date_from_obj = datetime.strptime(date_from, "%Y-%m-%d").date()
                qs = qs.filter(order_date__date__gte=date_from_obj)
            except ValueError:
                pass

        if date_to:
            try:
                date_to_obj = datetime.strptime(date_to, "%Y-%m-%d").date()
                qs = qs.filter(order_date__date__lte=date_to_obj)
            except ValueError:
                pass

        if payment_status:
            qs = qs.filter(payment_status=payment_status.upper())
        
        if fulfillment_status:
            qs = qs.filter(fulfillment_status=fulfillment_status.upper())

        if is_returned and is_returned.lower() == 'true':
            # Matches Ekart shipments marked as RTO or Returned
            qs = qs.filter(logistics_shipments__current_status__icontains="RTO")

        if search:
            qs = qs.filter(
                Q(id__icontains=search) |
                Q(session__user__username__icontains=search) |
                Q(session__user__email__icontains=search) |
                Q(session__user__mobile__icontains=search)
            )

        return qs.order_by('-order_date').distinct()


class AdminOrderTimelineView(APIView):
    """
    GET /api/shop/admin/orders/<order_id>/timeline/
    
    Constructs the entire chronological pipeline of an order.
    """
    permission_classes = [permissions.IsAdminUser]

    def get(self, request, order_id):
        order = get_object_or_404(SaleOrder, id=order_id, is_deleted=False)
        timeline = []

        # 1. Order Placed
        timeline.append({
            "stage": "ORDER_PLACED",
            "timestamp": order.order_date,
            "title": "Order Placed",
            "details": f"Total: ₹{order.total_amount}"
        })

        # 2. Payment Events
        for tx in order.transactions.select_related('status', 'processor').all():
            timeline.append({
                "stage": f"PAYMENT_{tx.status.status_name}",
                "timestamp": tx.transaction_date,
                "title": f"Payment {tx.status.status_name}",
                "details": f"Gateway: {tx.processor.processor_name} | ID: {tx.transaction_id}"
            })

        # 3. Logistics Pipeline
        for shipment in order.logistics_shipments.filter(is_deleted=False):
            timeline.append({
                "stage": "SHIPMENT_CREATED",
                "timestamp": shipment.created_at,
                "title": "Shipment Created",
                "details": f"Tracking ID: {shipment.tracking_id or 'Pending'}"
            })
            
            # Ekart Node Events
            for event in shipment.tracking_events.all():
                timeline.append({
                    "stage": "TRANSIT_EVENT",
                    "timestamp": event.event_timestamp,
                    "title": event.status,
                    "details": f"Location: {event.location or 'N/A'} | {event.description or ''}"
                })

        # Sort chronologically
        timeline.sort(key=lambda x: x['timestamp'])

        return Response(timeline, status=status.HTTP_200_OK)


class AdminOrderStatsView(APIView):
    """
    GET /api/shop/admin/orders/stats/
    
    Aggregates order amounts and counts grouped by statuses.
    """
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        # Base grouping by Payment and Fulfillment statuses
        stats = SaleOrder.objects.filter(is_deleted=False).values(
            'payment_status', 'fulfillment_status'
        ).annotate(
            count=Count('id'),
            total_revenue=Sum('total_amount')
        ).order_by('payment_status', 'fulfillment_status')

        # Restructure for frontend consumption
        summary = {}
        total_revenue_all = 0
        total_orders_all = 0

        for item in stats:
            p_status = item['payment_status']
            f_status = item['fulfillment_status']
            count = item['count']
            revenue = item['total_revenue'] or 0

            total_revenue_all += revenue
            total_orders_all += count

            if p_status not in summary:
                summary[p_status] = {"total_count": 0, "total_revenue": 0, "fulfillment_breakdown": {}}
            
            summary[p_status]["total_count"] += count
            summary[p_status]["total_revenue"] += revenue
            summary[p_status]["fulfillment_breakdown"][f_status] = {
                "count": count,
                "revenue": revenue
            }

        return Response({
            "global_totals": {
                "orders": total_orders_all,
                "revenue": total_revenue_all
            },
            "status_matrix": summary
        }, status=status.HTTP_200_OK)