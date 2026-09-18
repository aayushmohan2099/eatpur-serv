"""
shop/urls.py
"""
from django.urls import path, include
from .views import CheckoutView, VerifyPaymentView, RazorpayWebhookView, AdminCustomerAddressHistoryView

urlpatterns = [
    path('checkout/', CheckoutView.as_view(), name='shop-checkout'),
    path('verify-payment/', VerifyPaymentView.as_view(), name='shop-verify-payment'),
    path('razorpay-webhook/', RazorpayWebhookView.as_view(), name='shop-razorpay-webhook'),
    path('admin/orders/', include('shop.admin_api.urls')),
    path('customer/', include('shop.cust_api.urls')),
    path('admin/customer-address-history/', AdminCustomerAddressHistoryView.as_view(), name='admin_customer_address_history'),
]