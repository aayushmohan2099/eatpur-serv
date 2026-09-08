from rest_framework import serializers
from shop.models import SaleOrder, OrderProduct
from logistics.models import EkartShipment

class CustomerOrderProductSerializer(serializers.ModelSerializer):
    """Serializes individual items within a customer's order."""
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_image = serializers.SerializerMethodField()
    
    class Meta:
        model = OrderProduct
        fields = ['id', 'product_name', 'product_image', 'quantity', 'price_at_purchase', 'subtotal']

    def get_product_image(self, obj):
        # Gracefully fetch the first product image for the order history thumbnail
        first_media = obj.product.media.filter(is_deleted=False).first()
        if first_media and first_media.image:
            return first_media.image.url
        return None

class CustomerOrderListSerializer(serializers.ModelSerializer):
    """Serializes the full order history with logistics tracking info."""
    items = CustomerOrderProductSerializer(source='order_products', many=True, read_only=True)
    tracking_info = serializers.SerializerMethodField()

    class Meta:
        model = SaleOrder
        fields = [
            'id', 'order_date', 'total_amount', 'payment_status', 
            'fulfillment_status', 'items', 'tracking_info',
            'consignee_name', 'drop_location', 'drop_city', 'drop_state', 'drop_pincode'
        ]

    def get_tracking_info(self, obj):
        # Fetch the latest active shipment for this order
        shipment = obj.logistics_shipments.filter(is_deleted=False).order_by('-created_at').first()
        if shipment:
            return {
                "tracking_id": shipment.tracking_id,
                "status": shipment.current_status,
                "vendor": "Ekart Logistics",
                "tracking_url": f"https://app.elite.ekartlogistics.in/track/{shipment.tracking_id}" if shipment.tracking_id else None
            }
        return None

class CustomerInvoiceListSerializer(serializers.ModelSerializer):
    """Lightweight serializer specifically for the Invoices table."""
    invoice_number = serializers.SerializerMethodField()
    invoice_date = serializers.SerializerMethodField()

    class Meta:
        model = SaleOrder
        fields = ['id', 'order_date', 'total_amount', 'payment_status', 'invoice_number', 'invoice_date']

    def get_invoice_number(self, obj):
        shipment = obj.logistics_shipments.filter(is_deleted=False).first()
        # If Ekart hasn't generated an invoice yet, use a Proforma pattern
        return shipment.invoice_number if shipment and shipment.invoice_number else f"PROFORMA-{obj.id}"

    def get_invoice_date(self, obj):
        shipment = obj.logistics_shipments.filter(is_deleted=False).first()
        return shipment.invoice_date if shipment and shipment.invoice_date else obj.order_date.date()