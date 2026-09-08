from rest_framework import serializers
from shop.models import OrderTransaction, TransactionProcessor, TransactionStatus

class TransactionProcessorSerializer(serializers.ModelSerializer):
    class Meta:
        model = TransactionProcessor
        fields = ["id", "processor_name", "processor_type"]


class TransactionStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = TransactionStatus
        fields = ["id", "status_name"]


class AdminOrderTransactionListSerializer(serializers.ModelSerializer):
    """
    Serializes OrderTransaction records alongside associated SaleOrder 
    and customer identification metadata for admin listing.
    """
    processor_name = serializers.CharField(source="processor.processor_name", read_only=True)
    processor_type = serializers.CharField(source="processor.processor_type", read_only=True)
    status_name = serializers.CharField(source="status.status_name", read_only=True)
    
    # Associated SaleOrder details
    order_id = serializers.IntegerField(source="sale_order.id", read_only=True)
    order_total_amount = serializers.DecimalField(
        source="sale_order.total_amount", max_digits=14, decimal_places=2, read_only=True
    )
    order_date = serializers.DateTimeField(source="sale_order.order_date", read_only=True)
    order_payment_status = serializers.CharField(source="sale_order.payment_status", read_only=True)
    order_fulfillment_status = serializers.CharField(source="sale_order.fulfillment_status", read_only=True)
    
    # Customer Details
    customer_name = serializers.SerializerMethodField()
    customer_email = serializers.SerializerMethodField()
    customer_phone = serializers.SerializerMethodField()

    class Meta:
        model = OrderTransaction
        fields = [
            "id",
            "transaction_id",
            "transaction_date",
            "processor_name",
            "processor_type",
            "status_name",
            "order_id",
            "order_total_amount",
            "order_date",
            "order_payment_status",
            "order_fulfillment_status",
            "customer_name",
            "customer_email",
            "customer_phone",
            "response",
        ]

    def get_customer_name(self, obj):
        if obj.sale_order and obj.sale_order.consignee_name:
            return obj.sale_order.consignee_name
        if obj.session and obj.session.user:
            return obj.session.user.username
        return "Guest"

    def get_customer_email(self, obj):
        if obj.session and obj.session.user:
            return obj.session.user.email
        return None

    def get_customer_phone(self, obj):
        if obj.sale_order and obj.sale_order.consignee_phone:
            return obj.sale_order.consignee_phone
        if obj.sale_order and obj.sale_order.consignee_alternate_phone:
            return obj.sale_order.consignee_alternate_phone
        if obj.session and obj.session.user:
            return obj.session.user.mobile
        return None