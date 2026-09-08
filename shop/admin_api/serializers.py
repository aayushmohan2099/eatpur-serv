from rest_framework import serializers
from shop.models import SaleOrder, OrderProduct
from logistics.models import EkartShipment

class AdminOrderProductSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    pid = serializers.CharField(source='product.pid', read_only=True)

    class Meta:
        model = OrderProduct
        fields = ['id', 'pid', 'product_name', 'quantity', 'price_at_purchase', 'subtotal']

class AdminSaleOrderListSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='session.user.username', read_only=True, default="Guest")
    customer_email = serializers.CharField(source='session.user.email', read_only=True, default="N/A")
    customer_phone = serializers.CharField(source='session.user.mobile', read_only=True, default="N/A")
    items = AdminOrderProductSerializer(source='order_products', many=True, read_only=True)
    tracking_ids = serializers.SerializerMethodField()
    ekart_statuses = serializers.SerializerMethodField()

    class Meta:
        model = SaleOrder
        fields = [
            'id', 'order_date', 'customer_name', 'customer_email', 'customer_phone',
            'total_amount', 'payment_status', 'fulfillment_status',
            'items', 'tracking_ids', 'ekart_statuses'
        ]

    def get_tracking_ids(self, obj):
        return list(obj.logistics_shipments.filter(is_deleted=False).values_list('tracking_id', flat=True))

    def get_ekart_statuses(self, obj):
        return list(obj.logistics_shipments.filter(is_deleted=False).values_list('current_status', flat=True))