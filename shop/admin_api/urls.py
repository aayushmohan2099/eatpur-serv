"""
shop/admin_api/urls.py
"""
from django.urls import path, include
from .views import AdminOrderListView, AdminOrderTimelineView, AdminOrderStatsView

urlpatterns = [
    path('', AdminOrderListView.as_view(), name='admin-order-list'),
    path('stats/', AdminOrderStatsView.as_view(), name='admin-order-stats'),
    path('<int:order_id>/timeline/', AdminOrderTimelineView.as_view(), name='admin-order-timeline'),
    path("transactions/", include("shop.admin_api.transactions.urls")),
]