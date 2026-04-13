from django.contrib import admin
from django.urls import path
from django.template.response import TemplateResponse
from django.db.models import Sum
from shop.models import SaleOrder
from user.models import CustomUser


class CustomAdminSite(admin.AdminSite):
    site_header = "Millet Admin"
    site_title = "Millet Admin Panel"
    index_title = "Dashboard"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path("", self.admin_view(self.dashboard_view), name="dashboard"),
        ]
        return custom_urls + urls

    def dashboard_view(self, request):
        total_revenue = SaleOrder.objects.aggregate(
            total=Sum("total_amount")
        )["total"] or 0

        total_orders = SaleOrder.objects.count()
        total_users = CustomUser.objects.count()

        context = dict(
            self.each_context(request),
            total_revenue=total_revenue,
            total_orders=total_orders,
            total_users=total_users,
        )

        return TemplateResponse(request, "admin/dashboard.html", context)


admin_site = CustomAdminSite(name="custom_admin")