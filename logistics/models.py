"""
logistics/models.py
===================
Comprehensive logistics and tracking models integrating the Ekart API (v3.8.9).

These models cover:
1. API Audit Logging
2. Ekart Authentication Token Caching
3. Saved Warehouse/Pickup Addresses
4. Core Shipments (Forward & Reverse)
5. Shipment Items (for Multi-Package & Quality Check Returns)
6. Tracking Events & Webhooks
7. Non-Delivery Report (NDR) Actions
"""

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone

from core.mixins import SoftDeleteMixin


# ===========================================================================
# 1. API AUDIT LOGS
# ===========================================================================

class LogisticsAPILog(SoftDeleteMixin):
    """
    Detailed audit trail for EVERY request sent to the Ekart API.
    Crucial for debugging, reconciliation, and monitoring rate limits.
    """
    endpoint = models.CharField(max_length=255, db_index=True, verbose_name="API Endpoint")
    method = models.CharField(max_length=10, verbose_name="HTTP Method")
    
    request_payload = models.JSONField(null=True, blank=True, verbose_name="Request Payload")
    response_payload = models.JSONField(null=True, blank=True, verbose_name="Response Payload")
    
    status_code = models.IntegerField(null=True, blank=True, verbose_name="HTTP Status Code")
    response_time_ms = models.PositiveIntegerField(null=True, blank=True, verbose_name="Response Time (ms)")
    
    class Meta:
        db_table = "logistics_api_log"
        verbose_name = "Logistics API Log"
        verbose_name_plural = "Logistics API Logs"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.method} {self.endpoint} - {self.status_code}"


# ===========================================================================
# 2. AUTH TOKEN CACHE
# ===========================================================================

class EkartAuthToken(SoftDeleteMixin):
    """
    Caches the Ekart Bearer token. 
    Ekart tokens are valid for 24 hours. The logistics service should query 
    the active token here before generating a new one.
    """
    access_token = models.TextField(verbose_name="Access Token")
    token_type = models.CharField(max_length=50, default="Bearer", verbose_name="Token Type")
    scope = models.CharField(max_length=255, default="core:all", verbose_name="Scope")
    expires_at = models.DateTimeField(db_index=True, verbose_name="Expires At")

    class Meta:
        db_table = "ekart_auth_token"
        verbose_name = "Ekart Auth Token"
        verbose_name_plural = "Ekart Auth Tokens"

    def is_valid(self) -> bool:
        # Buffer of 5 minutes to prevent edge-case expirations mid-request
        return timezone.now() < (self.expires_at - timezone.timedelta(minutes=5))

    def __str__(self):
        return f"Ekart Token (Expires: {self.expires_at})"


# ===========================================================================
# 3. SAVED ADDRESSES
# ===========================================================================

class EkartAddress(SoftDeleteMixin):
    """
    Pickup and Return locations registered with Ekart.
    If an alias is registered, only the alias name is sent in shipment creation.
    """
    alias = models.CharField(max_length=100, unique=True, db_index=True, verbose_name="Alias/Location Name")
    phone = models.CharField(max_length=15, verbose_name="Phone Number")
    
    address_line1 = models.CharField(max_length=255, verbose_name="Address Line 1")
    address_line2 = models.CharField(max_length=255, blank=True, null=True, verbose_name="Address Line 2")
    pincode = models.IntegerField(verbose_name="Pincode")
    city = models.CharField(max_length=100, blank=True, null=True, verbose_name="City")
    state = models.CharField(max_length=100, verbose_name="State")
    country = models.CharField(max_length=50, default="India", verbose_name="Country")
    
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, verbose_name="Latitude")
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, verbose_name="Longitude")

    class Meta:
        db_table = "ekart_address"
        verbose_name = "Ekart Address"
        verbose_name_plural = "Ekart Addresses"

    def __str__(self):
        return f"{self.alias} - {self.pincode}"


# ===========================================================================
# 4. SHIPMENTS
# ===========================================================================

class EkartShipment(SoftDeleteMixin):
    """
    Central record for all shipments (Forward & Reverse).
    Ties the Ekart tracking lifecycle directly to our `shop.SaleOrder`.
    """
    PAYMENT_MODE_CHOICES = [
        ("COD", "Cash On Delivery"),
        ("Prepaid", "Prepaid"),
        ("Pickup", "Pickup (Reverse)"),
    ]

    # --- Relationships ---
    sale_order = models.ForeignKey(
        "shop.SaleOrder", 
        on_delete=models.SET_NULL, 
        null=True, blank=True, 
        related_name="logistics_shipments",
        db_index=True,
        verbose_name="Linked Sale Order"
    )
    user = models.ForeignKey(
        "user.CustomUser", 
        on_delete=models.SET_NULL, 
        null=True, blank=True, 
        related_name="shipments",
        db_index=True,
        verbose_name="Customer"
    )
    
    # --- Tracking & Identifiers ---
    tracking_id = models.CharField(max_length=100, null=True, blank=True, db_index=True, verbose_name="Ekart Tracking ID")
    ewbn = models.CharField(max_length=12, null=True, blank=True, verbose_name="EWBN")
    order_number = models.CharField(max_length=100, db_index=True, verbose_name="Ekart Payload Order Number")
    invoice_number = models.CharField(max_length=100, null=True, blank=True, verbose_name="Invoice Number")
    invoice_date = models.DateField(null=True, blank=True, verbose_name="Invoice Date")
    
    # --- Seller & Consignee Details ---
    seller_name = models.CharField(max_length=255, default="Eatpur Naturals LLP", verbose_name="Seller Name")
    seller_gst_tin = models.CharField(max_length=50, null=True, blank=True, verbose_name="Seller GST TIN")
    
    consignee_name = models.CharField(max_length=255, verbose_name="Consignee Name")
    consignee_phone = models.CharField(max_length=20, verbose_name="Consignee Phone")
    
    # --- Shipment Configuration ---
    payment_mode = models.CharField(max_length=20, choices=PAYMENT_MODE_CHOICES, verbose_name="Payment Mode")
    category_of_goods = models.CharField(max_length=100, default="Grocery", verbose_name="Category of Goods")
    products_desc = models.TextField(verbose_name="Products Description")
    return_reason = models.TextField(null=True, blank=True, verbose_name="Return Reason (For Pickup)")
    service_type = models.CharField(
        max_length=20, 
        choices=[("SURFACE", "Surface"), ("EXPRESS", "Express")], 
        default="SURFACE", 
        verbose_name="Service Type"
    )
    hsn_code = models.CharField(max_length=50, null=True, blank=True, verbose_name="HSN Code")
    what3words_address = models.CharField(max_length=255, null=True, blank=True, verbose_name="What3Words Address")    
    
    # --- Locations ---
    pickup_location_alias = models.ForeignKey(EkartAddress, on_delete=models.SET_NULL, null=True, related_name="pickup_shipments")
    return_location_alias = models.ForeignKey(EkartAddress, on_delete=models.SET_NULL, null=True, blank=True, related_name="return_shipments")
    drop_location_json = models.JSONField(verbose_name="Drop Location (Customer Address)")
    
    # --- Financials ---
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(1)], verbose_name="Total Amount")
    taxable_amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(1)], verbose_name="Taxable Amount")
    tax_value = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)], verbose_name="Tax Value")
    cod_amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0), MaxValueValidator(49999)], verbose_name="COD Amount")
    
    # --- Dimensions ---
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)], verbose_name="Quantity")
    weight = models.PositiveIntegerField(validators=[MinValueValidator(1)], verbose_name="Weight (grams)")
    length = models.PositiveIntegerField(validators=[MinValueValidator(1)], verbose_name="Length (cm)")
    height = models.PositiveIntegerField(validators=[MinValueValidator(1)], verbose_name="Height (cm)")
    width = models.PositiveIntegerField(validators=[MinValueValidator(1)], verbose_name="Width (cm)")
    
    # --- Ekart Flags ---
    delayed_dispatch = models.BooleanField(default=False, verbose_name="Delayed Dispatch")
    preferred_dispatch_date = models.DateField(null=True, blank=True, verbose_name="Preferred Dispatch Date")
    obd_shipment = models.BooleanField(default=False, verbose_name="Open Box Delivery")
    mps = models.BooleanField(default=False, verbose_name="Multi-package Shipment")
    qc_shipment = models.BooleanField(default=False, verbose_name="Quality Check (Reverse)")
    
    # --- Status Tracking ---
    current_status = models.CharField(max_length=100, default="Pending API Creation", db_index=True, verbose_name="Current Status")
    ndr_status = models.CharField(max_length=255, null=True, blank=True, verbose_name="NDR Status")
    is_delivered = models.BooleanField(default=False, db_index=True, verbose_name="Is Delivered")
    
    barcodes_json = models.JSONField(null=True, blank=True, verbose_name="Generated Barcodes")

    class Meta:
        db_table = "ekart_shipment"
        verbose_name = "Ekart Shipment"
        verbose_name_plural = "Ekart Shipments"
        indexes = [
            models.Index(fields=["tracking_id"]),
            models.Index(fields=["order_number"]),
            models.Index(fields=["current_status"]),
        ]

    def __str__(self):
        return f"Shipment {self.tracking_id or self.order_number} ({self.current_status})"


# ===========================================================================
# 5. SHIPMENT ITEMS (For MPS & Quality Check Returns)
# ===========================================================================

class EkartShipmentItem(SoftDeleteMixin):
    """
    Line items required specifically when mps=True (Multi-package) 
    or qc_shipment=True (Quality Check Return).
    """
    shipment = models.ForeignKey(EkartShipment, on_delete=models.CASCADE, related_name="items", verbose_name="Shipment")
    
    product_name = models.CharField(max_length=255, verbose_name="Product Name")
    product_desc = models.TextField(null=True, blank=True, verbose_name="Product Description")
    product_sku = models.CharField(max_length=100, null=True, blank=True, verbose_name="Product SKU")
    brand_name = models.CharField(max_length=100, default="EatPur Naturals", verbose_name="Brand Name")
    product_category = models.CharField(max_length=100, null=True, blank=True, verbose_name="Category")
    
    # For electronics/specific tracking (Optional for Food, but strictly mapped)
    ean_barcode = models.CharField(max_length=100, null=True, blank=True, verbose_name="EAN Barcode")
    
    # Store Array of Strings for QC images
    product_images_json = models.JSONField(default=list, blank=True, verbose_name="Product Images Array")

    class Meta:
        db_table = "ekart_shipment_item"
        verbose_name = "Ekart Shipment Item"
        verbose_name_plural = "Ekart Shipment Items"

    def __str__(self):
        return f"{self.product_name} - {self.shipment.tracking_id}"


# ===========================================================================
# 6. TRACKING EVENTS
# ===========================================================================

class EkartTrackingEvent(SoftDeleteMixin):
    """
    Chronological log of tracking updates.
    Populated automatically via the 'track_updated' webhook.
    """
    shipment = models.ForeignKey(EkartShipment, on_delete=models.CASCADE, related_name="tracking_events", verbose_name="Shipment")
    
    status = models.CharField(max_length=100, db_index=True, verbose_name="Status")
    description = models.TextField(null=True, blank=True, verbose_name="Status Description")
    location = models.CharField(max_length=255, null=True, blank=True, verbose_name="Location")
    
    # Unix Epoch mapped to DateTime
    event_timestamp = models.DateTimeField(db_index=True, verbose_name="Event Time")
    
    # In case of exceptions
    ndr_status = models.CharField(max_length=255, null=True, blank=True, verbose_name="NDR Status")
    attempts = models.IntegerField(default=0, verbose_name="Attempts")
    
    raw_payload = models.JSONField(null=True, blank=True, verbose_name="Raw Webhook Payload")

    class Meta:
        db_table = "ekart_tracking_event"
        verbose_name = "Tracking Event"
        verbose_name_plural = "Tracking Events"
        ordering = ["-event_timestamp"]

    def __str__(self):
        return f"[{self.event_timestamp:%Y-%m-%d %H:%M}] {self.shipment.tracking_id} - {self.status}"


# ===========================================================================
# 7. NON-DELIVERY REPORT (NDR) ACTIONS
# ===========================================================================

class EkartNDRAction(SoftDeleteMixin):
    """
    Stores actions taken by the seller when a shipment fails delivery.
    """
    ACTION_CHOICES = [
        ("Re-Attempt", "Re-Attempt Delivery"),
        ("RTO", "Return to Origin"),
    ]

    shipment = models.ForeignKey(EkartShipment, on_delete=models.CASCADE, related_name="ndr_actions", verbose_name="Shipment")
    action = models.CharField(max_length=20, choices=ACTION_CHOICES, verbose_name="Action Taken")
    
    # Required if Re-Attempt
    reattempt_date = models.DateField(null=True, blank=True, verbose_name="Re-Attempt Date")
    updated_phone = models.CharField(max_length=10, null=True, blank=True, verbose_name="Updated Phone")
    updated_address = models.TextField(null=True, blank=True, verbose_name="Updated Address")
    instructions = models.TextField(null=True, blank=True, verbose_name="Instructions")
    
    is_processed = models.BooleanField(default=False, verbose_name="Processed by API")

    class Meta:
        db_table = "ekart_ndr_action"
        verbose_name = "NDR Action"
        verbose_name_plural = "NDR Actions"

    def __str__(self):
        return f"{self.action} for {self.shipment.tracking_id}"


# ===========================================================================
# 8. WEBHOOK REGISTRY
# ===========================================================================

class EkartWebhook(SoftDeleteMixin):
    """
    Registry of active webhooks established with Ekart.
    """
    TOPIC_CHOICES = [
        ("track_updated", "Tracking Updated"),
        ("shipment_created", "Shipment Created"),
        ("shipment_recreated", "Shipment Recreated"),
    ]

    webhook_id = models.CharField(max_length=100, unique=True, db_index=True, verbose_name="Webhook ID")
    url = models.URLField(verbose_name="Webhook URL")
    topics_json = models.JSONField(verbose_name="Subscribed Topics")
    is_active = models.BooleanField(default=True, verbose_name="Is Active")

    class Meta:
        db_table = "ekart_webhook"
        verbose_name = "Ekart Webhook"
        verbose_name_plural = "Ekart Webhooks"

    def __str__(self):
        return f"Webhook: {self.url} ({'Active' if self.is_active else 'Inactive'})"