"""
shop/urls.py
"""
from django.urls import path
from .views import CheckoutView, VerifyPaymentView, RazorpayWebhookView

urlpatterns = [
    path('checkout/', CheckoutView.as_view(), name='shop-checkout'),
    path('verify-payment/', VerifyPaymentView.as_view(), name='shop-verify-payment'),
    path('razorpay-webhook/', RazorpayWebhookView.as_view(), name='shop-razorpay-webhook'),
]