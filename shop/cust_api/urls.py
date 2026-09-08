from django.urls import path
from .views import CustomerOrderListView, CustomerInvoiceListView, CustomerInvoiceDownloadView

urlpatterns = [
    path('orders/', CustomerOrderListView.as_view(), name='customer-orders-list'),
    path('invoices/', CustomerInvoiceListView.as_view(), name='customer-invoices-list'),
    path('invoices/<int:order_id>/download/', CustomerInvoiceDownloadView.as_view(), name='customer-invoice-download'),
]