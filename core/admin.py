# core/admin.py

from django.contrib import admin
from django.urls import path, NoReverseMatch
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.http import HttpResponse
from django.contrib.auth import logout as auth_logout

# ---------------------------------------------------------
# View Imports (Isolated to prevent one missing file from breaking others)
# ---------------------------------------------------------

# 1. STAFF VIEWS
try:
    from core.views.staff_views import (
        staff_dashboard_view, staff_messages_view, staff_user_messages_view,
        staff_coupons_view, staff_orders_view, staff_send_message,
        staff_thread_view, staff_customer_thread_view, staff_mark_read,
        api_coupon_detail, api_order_detail, api_coupon_toggle # <-- ADDED HERE
    )
except ImportError as e:
    print(f"Staff views error: {e}")
    staff_dashboard_view = staff_messages_view = staff_user_messages_view = None
    staff_coupons_view = staff_orders_view = staff_send_message = None
    staff_thread_view = staff_customer_thread_view = staff_mark_read = None
    api_coupon_detail = api_order_detail = api_coupon_toggle = None

# 2. INVENTORY VIEWS
try:
    from core.views.inventory_views import (
        inventory_dashboard_view, inventory_categories_view, inventory_products_view,
        inventory_status_view, inventory_blog_view, inventory_messages_view
    )
except ImportError as e:
    inventory_dashboard_view = inventory_categories_view = inventory_products_view = None
    inventory_status_view = inventory_blog_view = inventory_messages_view = None

# 3. SUPERVISOR VIEWS
try:
    from core.views.supervisor_views import (
        supervisor_dashboard_view, supervisor_approval_view, supervisor_categories_view,
        supervisor_products_view, supervisor_status_view, supervisor_blog_view,
        supervisor_messages_view, supervisor_coupons_view, supervisor_orders_view,
        api_product_approve, api_product_reject
        # <-- REMOVED api_coupon_toggle from here
    )
except ImportError as e:
    supervisor_dashboard_view = supervisor_approval_view = supervisor_categories_view = None
    supervisor_products_view = supervisor_status_view = supervisor_blog_view = None
    supervisor_messages_view = supervisor_coupons_view = supervisor_orders_view = None
    api_product_approve = api_product_reject = None

# 4. ADMIN VIEWS
try:
    from core.views.admin_views import (
        admin_dashboard_view, admin_users_view, admin_orders_view, admin_coupons_view,
        admin_approval_view, admin_categories_view, admin_products_view,
        admin_product_status_view, admin_blog_view, admin_messages_view,
        api_message_send
    )
except ImportError as e:
    admin_dashboard_view = admin_users_view = admin_orders_view = admin_coupons_view = None
    admin_approval_view = admin_categories_view = admin_products_view = None
    admin_product_status_view = admin_blog_view = admin_messages_view = None
    api_message_send = None


class CustomAdminSite(admin.AdminSite):
    site_header = "EatPur Admin"
    site_title = "EatPur Admin Panel"
    index_title = "Dashboard"

    def logout(self, request, extra_context=None):
        """Log out the user and instantly redirect to login."""
        auth_logout(request)
        return redirect('custom_admin:login')

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = []

        # Safely add URLs only if the view has been created/imported successfully
        def add_url(route, view_func, name):
            if view_func is not None:
                custom_urls.append(path(route, self.admin_view(view_func), name=name))

        # MAIN DASHBOARD ROUTER (Always loads)
        custom_urls.append(path("", self.admin_view(self.dashboard_router), name="dashboard"))

        # STAFF URLs 
        add_url("staff/", staff_dashboard_view, "staff_dashboard")
        add_url("staff/messages/", staff_messages_view, "staff_messages")
        add_url("staff/user-messages/", staff_user_messages_view, "staff_user_messages")
        add_url("staff/coupons/", staff_coupons_view, "staff_coupons")
        add_url("staff/orders/", staff_orders_view, "staff_orders")
        add_url("staff/messages/send/", staff_send_message, "staff_send_message")
        add_url("staff/messages/thread/", staff_thread_view, "staff_thread")
        add_url("staff/messages/customer-thread/", staff_customer_thread_view, "staff_customer_thread")
        add_url("staff/messages/mark-read/", staff_mark_read, "staff_mark_read")

        # INVENTORY MANAGER URLs 
        add_url("inventory/", inventory_dashboard_view, "inventory_dashboard")
        add_url("inventory/categories/", inventory_categories_view, "inventory_categories")
        add_url("inventory/products/", inventory_products_view, "inventory_products")
        add_url("inventory/status/", inventory_status_view, "inventory_status")
        add_url("inventory/blog/", inventory_blog_view, "inventory_blog")
        add_url("inventory/messages/", inventory_messages_view, "inventory_messages")

        # SUPERVISOR URLs 
        add_url("supervisor/", supervisor_dashboard_view, "supervisor_dashboard")
        add_url("supervisor/approval/", supervisor_approval_view, "supervisor_approval")
        add_url("supervisor/categories/", supervisor_categories_view, "supervisor_categories")
        add_url("supervisor/products/", supervisor_products_view, "supervisor_products")
        add_url("supervisor/status/", supervisor_status_view, "supervisor_status")
        add_url("supervisor/blog/", supervisor_blog_view, "supervisor_blog")
        add_url("supervisor/messages/", supervisor_messages_view, "supervisor_messages")
        add_url("supervisor/coupons/", supervisor_coupons_view, "supervisor_coupons")
        add_url("supervisor/orders/", supervisor_orders_view, "supervisor_orders")

        # ADMIN URLs 
        add_url("admin-panel/", admin_dashboard_view, "admin_dashboard")
        add_url("admin-panel/users/", admin_users_view, "admin_users")
        add_url("admin-panel/orders/", admin_orders_view, "admin_orders")
        add_url("admin-panel/coupons/", admin_coupons_view, "admin_coupons")
        add_url("admin-panel/approval/", admin_approval_view, "admin_approval")
        add_url("admin-panel/categories/", admin_categories_view, "admin_categories")
        add_url("admin-panel/products/", admin_products_view, "admin_products")
        add_url("admin-panel/status/", admin_product_status_view, "admin_product_status")
        add_url("admin-panel/blog/", admin_blog_view, "admin_blog")
        add_url("admin-panel/messages/", admin_messages_view, "admin_messages")

        # GENERIC CRUD API ENDPOINTS 
        add_url("api/product/<int:pk>/approve/", api_product_approve, "api_product_approve")
        add_url("api/product/<int:pk>/reject/", api_product_reject, "api_product_reject")
        add_url("api/coupon/<int:pk>/toggle/", api_coupon_toggle, "api_coupon_toggle")
        add_url("api/coupon/<int:pk>/", api_coupon_detail, "api_coupon_detail")
        add_url("api/message/send/", api_message_send, "api_message_send")
        add_url("api/order/<int:pk>/", api_order_detail, "api_order_detail")

        return custom_urls + urls

    # ---------------------------------------------------------
    # DYNAMIC DASHBOARD ROUTER 
    # ---------------------------------------------------------
    def dashboard_router(self, request):
        """
        Traffic Director: Redirects user to their specific dashboard on login.
        Catches missing endpoints gracefully.
        """
        if not request.user.is_authenticated:
            return redirect("custom_admin:login")
        
        role = getattr(request.user.role, "role_name", None) if hasattr(request.user, "role") else None
        
        try:
            if role == "STAFF":
                return redirect("custom_admin:staff_dashboard")
            elif role == "INVENTORY_MANAGER":
                return redirect("custom_admin:inventory_dashboard")
            elif role == "SUPERVISOR":
                return redirect("custom_admin:supervisor_dashboard")
            elif role == "ADMIN":
                return redirect("custom_admin:admin_dashboard")
        except NoReverseMatch:
            # Safety Net: If the view file is blank/broken, show this instead of crashing
            return HttpResponse(f"""
                <div style='font-family:sans-serif; padding:40px; text-align:center;'>
                    <h2>Dashboard Not Ready</h2>
                    <p>The backend views for the <b>{role}</b> role are not imported or implemented yet.</p>
                </div>
            """)
        
        # Fallback for standard Django superusers without a designated panel role
        return TemplateResponse(request, "admin/dashboard.html", self.each_context(request))

admin_site = CustomAdminSite(name="custom_admin")