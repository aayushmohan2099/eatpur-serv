"""
shop/models.py
==============
Order management, coupon engine, and payment transaction system.

Table Map
---------
CouponStatus        → ONGOING / EXPIRED / DRAFT
Coupon              → discount codes with validity windows
SaleOrder           → customer order tied to a session
OrderProduct        → line items per order (product × quantity × price)
TransactionProcessor→ payment gateways (GPay, Stripe, etc.)
TransactionStatus   → payment lifecycle states
OrderTransaction    → payment attempt record with external tx ID and response

Design Notes
------------
* price_at_purchase on OrderProduct captures the price at order time,
  decoupling order history from future product price changes.
* OrderTransaction stores the full JSON response from the payment gateway
  for audit, dispute resolution, and reconciliation.
* session_id on both SaleOrder and OrderTransaction enables full
  traceability from a user action through to payment.
"""

from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal

from core.mixins import SoftDeleteMixin
from user.models import Session
from inventory.models import Product


# ===========================================================================
# LOOKUP: CouponStatus
# ===========================================================================

class CouponStatus(SoftDeleteMixin):
    """
    Lifecycle state of a coupon.
    Examples: ONGOING, EXPIRED, DRAFT
    """

    STATUS_CHOICES = [
        ("ONGOING", "Ongoing"),
        ("EXPIRED", "Expired"),
        ("DRAFT", "Draft"),
    ]

    status_name = models.CharField(
        max_length=20,
        unique=True,
        choices=STATUS_CHOICES,
        verbose_name="Status Name",
    )

    class Meta:
        db_table = "coupon_status"
        verbose_name = "Coupon Status"
        verbose_name_plural = "Coupon Statuses"

    def __str__(self):
        return self.status_name


# ===========================================================================
# Coupon
# ===========================================================================

class Coupon(SoftDeleteMixin):
    """
    Promotional discount code.

    discount_type:
        PERCENT — reduce price by X%
        FLAT    — reduce price by a fixed currency amount

    discount_value is always stored as a positive Decimal:
        PERCENT → 0.00–100.00
        FLAT    → absolute amount in the store currency
    """

    DISCOUNT_TYPE_CHOICES = [
        ("PERCENT", "Percentage Discount"),
        ("FLAT", "Flat Amount Discount"),
    ]

    coupon_code = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        verbose_name="Coupon Code",
    )
    description = models.TextField(blank=True, verbose_name="Description")

    status = models.ForeignKey(
        CouponStatus,
        on_delete=models.SET_NULL,
        null=True,
        related_name="coupons",
        db_index=True,
        verbose_name="Status",
    )

    start_date = models.DateTimeField(db_index=True, verbose_name="Valid From")
    end_date = models.DateTimeField(db_index=True, verbose_name="Valid Until")

    discount_type = models.CharField(
        max_length=10,
        choices=DISCOUNT_TYPE_CHOICES,
        verbose_name="Discount Type",
    )
    discount_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
        verbose_name="Discount Value",
    )

    class Meta:
        db_table = "coupon"
        verbose_name = "Coupon"
        verbose_name_plural = "Coupons"
        indexes = [
            models.Index(fields=["coupon_code"]),
            models.Index(fields=["start_date", "end_date"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.coupon_code} ({self.discount_type}: {self.discount_value})"


# ===========================================================================
# SaleOrder — Customer order
# ===========================================================================

class SaleOrder(SoftDeleteMixin):
    """
    A single customer order.

    * coupon: optional; NULL if no discount applied.
    * session: the request session at the time of order placement.
    * total_amount: final amount after discount, stored for financial record integrity.
    """

    order_date = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Order Date")
    total_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
        verbose_name="Total Amount",
    )

    coupon = models.ForeignKey(
        Coupon,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
        db_index=True,
        verbose_name="Applied Coupon",
    )
    session = models.ForeignKey(
        Session,
        on_delete=models.SET_NULL,
        null=True,
        related_name="orders",
        db_index=True,
        verbose_name="Session",
    )

    class Meta:
        db_table = "sale_order"
        verbose_name = "Sale Order"
        verbose_name_plural = "Sale Orders"
        indexes = [
            models.Index(fields=["order_date"]),
            models.Index(fields=["session"]),
        ]

    def __str__(self):
        return f"Order#{self.pk} — ₹{self.total_amount} on {self.order_date:%Y-%m-%d}"


# ===========================================================================
# OrderProduct — Line items
# ===========================================================================

class OrderProduct(SoftDeleteMixin):
    """
    Each row represents one product line in a SaleOrder.

    price_at_purchase is snapshot of the product price when the order was placed.
    This is critical: product prices change, but historical orders must
    reflect what the customer actually paid.

    subtotal = quantity × price_at_purchase (stored to avoid recalculation).
    """

    sale_order = models.ForeignKey(
        SaleOrder,
        on_delete=models.CASCADE,
        related_name="order_products",
        db_index=True,
        verbose_name="Sale Order",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.SET_NULL,
        null=True,
        related_name="order_products",
        db_index=True,
        verbose_name="Product",
    )

    quantity = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        verbose_name="Quantity",
    )

    # Snapshot prices — never read from Product after order is placed
    price_at_purchase = models.DecimalField(
        max_digits=12, decimal_places=2, verbose_name="Price at Purchase"
    )
    subtotal = models.DecimalField(
        max_digits=14, decimal_places=2, verbose_name="Subtotal"
    )

    class Meta:
        db_table = "order_products"
        verbose_name = "Order Product"
        verbose_name_plural = "Order Products"
        indexes = [
            models.Index(fields=["sale_order"]),
            models.Index(fields=["product"]),
        ]

    def save(self, *args, **kwargs):
        # Automatically compute subtotal before saving
        self.subtotal = self.price_at_purchase * self.quantity
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Order#{self.sale_order_id} × {self.product} × {self.quantity}"


# ===========================================================================
# LOOKUP: TransactionProcessor
# ===========================================================================

class TransactionProcessor(SoftDeleteMixin):
    """
    Registered payment gateway / processor.
    Examples: GPAY, PHONEPE, PAYTM, STRIPE

    processor_type indicates the payment rail:
        UPI    — GPay, PhonePe, Paytm UPI
        CARD   — Stripe, Razorpay card
        WALLET — Paytm Wallet, Amazon Pay
    """

    PROCESSOR_TYPE_CHOICES = [
        ("UPI", "UPI"),
        ("CARD", "Card"),
        ("WALLET", "Wallet"),
        ("NETBANKING", "Net Banking"),
        ("BNPL", "Buy Now Pay Later"),
        ("QR", "Scanning QR Code"),
    ]

    processor_name = models.CharField(
        max_length=100, unique=True, db_index=True, verbose_name="Processor Name"
    )
    processor_type = models.CharField(
        max_length=20,
        choices=PROCESSOR_TYPE_CHOICES,
        db_index=True,
        verbose_name="Processor Type",
    )

    class Meta:
        db_table = "transaction_processor"
        verbose_name = "Transaction Processor"
        verbose_name_plural = "Transaction Processors"

    def __str__(self):
        return f"{self.processor_name} [{self.processor_type}]"


# ===========================================================================
# LOOKUP: TransactionStatus
# ===========================================================================

class TransactionStatus(SoftDeleteMixin):
    """
    Lifecycle state of a payment transaction.
    Examples: INITIATED, PENDING, SUCCESS, FAILED, CANCELLED, REFUNDED, TIMEOUT
    """

    STATUS_CHOICES = [
        ("INITIATED", "Initiated"),
        ("PENDING", "Pending"),
        ("SUCCESS", "Success"),
        ("FAILED", "Failed"),
        ("CANCELLED", "Cancelled"),
        ("REFUNDED", "Refunded"),
        ("TIMEOUT", "Timeout"),
    ]

    status_name = models.CharField(
        max_length=20,
        unique=True,
        choices=STATUS_CHOICES,
        verbose_name="Status Name",
    )

    class Meta:
        db_table = "transaction_status"
        verbose_name = "Transaction Status"
        verbose_name_plural = "Transaction Statuses"

    def __str__(self):
        return self.status_name


# ===========================================================================
# OrderTransaction — Payment record
# ===========================================================================

class OrderTransaction(SoftDeleteMixin):
    """
    One row per payment attempt against a SaleOrder.

    An order may have multiple attempts (e.g., user retries after FAILED).
    Only one should reach SUCCESS.

    transaction_id : external ID returned by the payment gateway.
    response       : full raw JSON response from the gateway for audit/disputes.
    session        : session at the time of payment (may differ from order session
                     if user switches device between cart and checkout).
    """

    sale_order = models.ForeignKey(
        SaleOrder,
        on_delete=models.CASCADE,
        related_name="transactions",
        db_index=True,
        verbose_name="Sale Order",
    )

    # External transaction ID from the payment gateway
    transaction_id = models.CharField(
        max_length=255,
        db_index=True,
        verbose_name="External Transaction ID",
    )

    transaction_date = models.DateTimeField(
        db_index=True, verbose_name="Transaction Date"
    )

    processor = models.ForeignKey(
        TransactionProcessor,
        on_delete=models.SET_NULL,
        null=True,
        related_name="transactions",
        db_index=True,
        verbose_name="Processor",
    )
    session = models.ForeignKey(
        Session,
        on_delete=models.SET_NULL,
        null=True,
        related_name="transactions",
        db_index=True,
        verbose_name="Session",
    )
    status = models.ForeignKey(
        TransactionStatus,
        on_delete=models.SET_NULL,
        null=True,
        related_name="transactions",
        db_index=True,
        verbose_name="Status",
    )

    # Full gateway response for reconciliation and dispute resolution
    response = models.JSONField(
        default=dict, blank=True, verbose_name="Gateway Response (JSON)"
    )

    class Meta:
        db_table = "order_transaction"
        verbose_name = "Order Transaction"
        verbose_name_plural = "Order Transactions"
        indexes = [
            models.Index(fields=["sale_order"]),
            models.Index(fields=["transaction_id"]),
            models.Index(fields=["transaction_date"]),
            models.Index(fields=["status"]),
            models.Index(fields=["processor"]),
            # Composite: find all transactions for an order by status
            models.Index(fields=["sale_order", "status"]),
        ]

    def __str__(self):
        return f"Tx[{self.transaction_id}] Order#{self.sale_order_id} — {self.status}"
