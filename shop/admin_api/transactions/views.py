from datetime import datetime
from decimal import Decimal
from django.db.models import Sum, Count, Q, Value, DecimalField
from django.db.models.functions import Coalesce
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from rest_framework import permissions, status

from shop.models import OrderTransaction, TransactionProcessor, TransactionStatus
from .serializers import AdminOrderTransactionListSerializer


class TransactionPagination(PageNumberPagination):
    page_size = 15
    page_size_query_param = "page_size"
    max_page_size = 100


class AdminTransactionOverviewStatsView(APIView):
    """
    GET /api/shop/admin/transactions/overview/
    
    Returns aggregated transaction analytics:
    - Total Volume & Count
    - Volume & Count split across all TransactionStatuses
    - Volume & Count grouped by Payment Processor
    Supports optional date filtering (?date_from=YYYY-MM-DD&date_to=YYYY-MM-DD).
    """
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        qs = OrderTransaction.objects.filter(is_deleted=False).select_related("sale_order", "processor", "status")

        # Date range filtering
        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")

        if date_from:
            try:
                date_from_obj = datetime.strptime(date_from, "%Y-%m-%d").date()
                qs = qs.filter(transaction_date__date__gte=date_from_obj)
            except ValueError:
                pass

        if date_to:
            try:
                date_to_obj = datetime.strptime(date_to, "%Y-%m-%d").date()
                qs = qs.filter(transaction_date__date__lte=date_to_obj)
            except ValueError:
                pass

        # 1. Global Metrics
        total_tx = qs.count()
        total_amount = qs.aggregate(
            total=Coalesce(Sum("sale_order__total_amount"), Value(0, output_field=DecimalField()))
        )["total"]

        success_tx = qs.filter(status__status_name="SUCCESS").count()
        success_amount = qs.filter(status__status_name="SUCCESS").aggregate(
            total=Coalesce(Sum("sale_order__total_amount"), Value(0, output_field=DecimalField()))
        )["total"]

        success_rate = round((success_tx / total_tx * 100), 2) if total_tx > 0 else 0.00

        # 2. Strict Status Breakdown (All 7 defined system statuses)
        system_statuses = [
            "INITIATED", "PENDING", "SUCCESS", "FAILED",
            "CANCELLED", "REFUNDED", "TIMEOUT"
        ]

        status_aggregates = (
            qs.values("status__status_name")
            .annotate(
                count=Count("id"),
                volume=Coalesce(Sum("sale_order__total_amount"), Value(0, output_field=DecimalField())),
            )
        )

        status_dict = {item["status__status_name"]: item for item in status_aggregates if item["status__status_name"]}

        status_breakdown = {}
        for status_code in system_statuses:
            item = status_dict.get(status_code, {"count": 0, "volume": Decimal("0.00")})
            status_breakdown[status_code] = {
                "count": item["count"],
                "volume": item["volume"]
            }

        # 3. Processor Breakdown
        processor_aggregates = (
            qs.values("processor__id", "processor__processor_name", "processor__processor_type")
            .annotate(
                total_count=Count("id"),
                total_volume=Coalesce(Sum("sale_order__total_amount"), Value(0, output_field=DecimalField())),
                successful_count=Count("id", filter=Q(status__status_name="SUCCESS")),
                successful_volume=Coalesce(
                    Sum("sale_order__total_amount", filter=Q(status__status_name="SUCCESS")),
                    Value(0, output_field=DecimalField()),
                ),
            )
            .order_by("-total_volume")
        )

        processor_breakdown = []
        for p in processor_aggregates:
            if p["processor__processor_name"]:
                processor_breakdown.append({
                    "processor_id": p["processor__id"],
                    "processor_name": p["processor__processor_name"],
                    "processor_type": p["processor__processor_type"],
                    "total_count": p["total_count"],
                    "total_volume": p["total_volume"],
                    "successful_count": p["successful_count"],
                    "successful_volume": p["successful_volume"],
                })

        return Response({
            "global_totals": {
                "total_transactions": total_tx,
                "total_volume": total_amount,
                "successful_transactions": success_tx,
                "successful_volume": success_amount,
                "success_rate_percentage": success_rate,
            },
            "status_breakdown": status_breakdown,
            "processor_breakdown": processor_breakdown,
        }, status=status.HTTP_200_OK)


class AdminTransactionListView(ListAPIView):
    """
    GET /api/shop/admin/transactions/
    
    Paginated and highly filtered listing of all OrderTransaction entities.
    Filters:
    - status: Exact status code (e.g., SUCCESS, FAILED, TIMEOUT)
    - processor: Processor Name (e.g., RAZORPAY)
    - processor_type: UPI, CARD, WALLET, NETBANKING, BNPL, QR
    - date_from, date_to: Date range on transaction_date
    - min_amount, max_amount: Numeric bounds on sale_order.total_amount
    - order_id: Exact SaleOrder primary key
    - search: Case-insensitive query against transaction_id, user email, username, phone, or name
    """
    permission_classes = [permissions.IsAdminUser]
    serializer_class = AdminOrderTransactionListSerializer
    pagination_class = TransactionPagination

    def get_queryset(self):
        qs = OrderTransaction.objects.filter(is_deleted=False).select_related(
            "sale_order",
            "processor",
            "status",
            "session__user",
            "sale_order__session__user",
        ).order_by("-transaction_date")

        params = self.request.query_params

        status_param = params.get("status")
        processor_param = params.get("processor")
        processor_type_param = params.get("processor_type")
        order_id_param = params.get("order_id")
        date_from = params.get("date_from")
        date_to = params.get("date_to")
        min_amount = params.get("min_amount")
        max_amount = params.get("max_amount")
        search = params.get("search")

        if status_param:
            qs = qs.filter(status__status_name__iexact=status_param)

        if processor_param:
            qs = qs.filter(processor__processor_name__iexact=processor_param)

        if processor_type_param:
            qs = qs.filter(processor__processor_type__iexact=processor_type_param)

        if order_id_param:
            qs = qs.filter(sale_order_id=order_id_param)

        if date_from:
            try:
                date_from_obj = datetime.strptime(date_from, "%Y-%m-%d").date()
                qs = qs.filter(transaction_date__date__gte=date_from_obj)
            except ValueError:
                pass

        if date_to:
            try:
                date_to_obj = datetime.strptime(date_to, "%Y-%m-%d").date()
                qs = qs.filter(transaction_date__date__lte=date_to_obj)
            except ValueError:
                pass

        if min_amount:
            try:
                qs = qs.filter(sale_order__total_amount__gte=Decimal(min_amount))
            except ValueError:
                pass

        if max_amount:
            try:
                qs = qs.filter(sale_order__total_amount__lte=Decimal(max_amount))
            except ValueError:
                pass

        if search:
            qs = qs.filter(
                Q(transaction_id__icontains=search)
                | Q(sale_order__id__icontains=search)
                | Q(sale_order__consignee_name__icontains=search)
                | Q(sale_order__consignee_phone__icontains=search)
                | Q(sale_order__consignee_alternate_phone__icontains=search)
                | Q(session__user__username__icontains=search)
                | Q(session__user__email__icontains=search)
                | Q(session__user__mobile__icontains=search)
            )

        return qs.distinct()