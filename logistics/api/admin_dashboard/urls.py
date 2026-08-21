"""
logistics/api/admin_dashboard/urls.py
"""
from django.urls import path
from .views import LogisticsOverviewStatsView, ShippingCostAnalyticsView, APIAuditLogView

urlpatterns = [
    path('overview/', LogisticsOverviewStatsView.as_view(), name='dashboard-overview'),
    path('financials/', ShippingCostAnalyticsView.as_view(), name='dashboard-financials'),
    path('audit-logs/', APIAuditLogView.as_view(), name='dashboard-audit-logs'),
]