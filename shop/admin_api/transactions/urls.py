from django.urls import path
from .views import AdminTransactionOverviewStatsView, AdminTransactionListView

urlpatterns = [
    path("", AdminTransactionListView.as_view(), name="admin-transaction-list"),
    path("overview/", AdminTransactionOverviewStatsView.as_view(), name="admin-transaction-overview"),
]