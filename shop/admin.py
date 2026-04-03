"""
shop/admin.py
=============

Admin for Orders, Coupons, and Payments
Optimized for:
- Financial safety (read-only where needed)
- Order inspection (line items inline)
- Payment debugging
- Coupon management
"""

from django.contrib import admin
from django.utils.html import format_html

from .models import (
    CouponStatus,
    Coupon,
    SaleOrder,
    OrderProduct,
    TransactionProcessor,
    TransactionStatus,
    OrderTransaction,
)


# ============================================================================
# Inline: Order Products (Line Items)
# ============================================================================

class OrderProductInline(admin.TabularInline):
    model = OrderProduct
    extra = 0
    fields = (
        "product",
        "quantity",
        "price_at_purchase",
        "subtotal",
    )
    readonly_fields = ("subtotal",)

    autocomplete_fields = ("product",)


# ============================================================================
# Inline: Transactions (Payments)
# ============================================================================

class OrderTransactionInline(admin.TabularInline):
    model = OrderTransaction
    extra = 0
    fields = (
        "transaction_id",
        "processor",
        "status",
        "transaction_date",
    )
    readonly_fields = (
        "transaction_id",
        "processor",
        "status",
        "transaction_date",
    )

    can_delete = False


# ============================================================================
# SaleOrder (MAIN ORDER VIEW)
# ============================================================================

@admin.register(SaleOrder)
class SaleOrderAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "order_date",
        "total_amount",
        "coupon",
        "session",
        "payment_status",
        "item_count",
    )

    list_filter = (
        "order_date",
        "coupon",
    )

    search_fields = ("id", "session__id")

    readonly_fields = (
        "order_date",
        "total_amount",
    )

    autocomplete_fields = ("coupon", "session")

    inlines = [OrderProductInline, OrderTransactionInline]

    ordering = ("-order_date",)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def payment_status(self, obj):
        tx = obj.transactions.order_by("-transaction_date").first()
        return tx.status if tx else "—"
    payment_status.short_description = "Payment"

    def item_count(self, obj):
        return obj.order_products.count()
    item_count.short_description = "Items"


# ============================================================================
# OrderProduct (Standalone)
# ============================================================================

@admin.register(OrderProduct)
class OrderProductAdmin(admin.ModelAdmin):
    list_display = (
        "sale_order",
        "product",
        "quantity",
        "price_at_purchase",
        "subtotal",
    )

    autocomplete_fields = ("sale_order", "product")

    readonly_fields = ("subtotal",)


# ============================================================================
# Coupon
# ============================================================================

@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = (
        "coupon_code",
        "discount_type",
        "discount_value",
        "status",
        "start_date",
        "end_date",
        "is_active",
    )

    list_filter = (
        "discount_type",
        "status",
        "start_date",
        "end_date",
    )

    search_fields = ("coupon_code",)

    autocomplete_fields = ("status",)

    ordering = ("-start_date",)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def is_active(self, obj):
        from django.utils import timezone
        now = timezone.now()
        return obj.start_date <= now <= obj.end_date
    is_active.boolean = True
    is_active.short_description = "Active"


# ============================================================================
# Coupon Status
# ============================================================================

@admin.register(CouponStatus)
class CouponStatusAdmin(admin.ModelAdmin):
    list_display = ("status_name",)
    search_fields = ("status_name",)


# ============================================================================
# Transaction Processor
# ============================================================================

@admin.register(TransactionProcessor)
class TransactionProcessorAdmin(admin.ModelAdmin):
    list_display = ("processor_name", "processor_type")
    list_filter = ("processor_type",)
    search_fields = ("processor_name",)


# ============================================================================
# Transaction Status
# ============================================================================

@admin.register(TransactionStatus)
class TransactionStatusAdmin(admin.ModelAdmin):
    list_display = ("status_name",)
    search_fields = ("status_name",)


# ============================================================================
# OrderTransaction (PAYMENT DEBUG PANEL)
# ============================================================================

@admin.register(OrderTransaction)
class OrderTransactionAdmin(admin.ModelAdmin):
    list_display = (
        "transaction_id",
        "sale_order",
        "processor",
        "status",
        "transaction_date",
        "short_response",
    )

    list_filter = (
        "status",
        "processor",
        "transaction_date",
    )

    search_fields = (
        "transaction_id",
        "sale_order__id",
    )

    autocomplete_fields = ("sale_order", "processor", "status", "session")

    readonly_fields = (
        "transaction_id",
        "transaction_date",
        "response",
    )

    ordering = ("-transaction_date",)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def short_response(self, obj):
        if obj.response:
            return str(obj.response)[:80] + "..."
        return "-"
    short_response.short_description = "Gateway Response"