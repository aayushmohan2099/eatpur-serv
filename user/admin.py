from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import CustomUser, Role, Session


# =========================
# ROLE ADMIN
# =========================
@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("role_name", "is_deleted", "created_at")
    search_fields = ("role_name",)
    list_filter = ("is_deleted",)
    ordering = ("role_name",)


# =========================
# SESSION ADMIN
# =========================
@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ("user", "ip_address", "created_at", "is_deleted")
    search_fields = ("user__username", "ip_address")
    list_filter = ("is_deleted", "created_at")
    readonly_fields = ("created_at", "updated_at")

    def has_add_permission(self, request):
        return False  # sessions should not be manually added


# =========================
# CUSTOM USER ADMIN
# =========================
@admin.register(CustomUser)
class CustomUserAdmin(BaseUserAdmin):
    model = CustomUser

    list_display = (
        "username",
        "email",
        "mobile",
        "role",
        "is_active",
        "is_staff",
        "is_deleted",
        "created_at",
    )

    list_filter = (
        "is_active",
        "is_staff",
        "is_superuser",
        "is_deleted",
        "role",
    )

    search_fields = ("username", "email", "mobile")
    ordering = ("-created_at",)

    readonly_fields = ("created_at", "updated_at", "deleted_at")

    fieldsets = (
        ("Basic Info", {
            "fields": ("username", "email", "mobile", "password")
        }),
        ("Profile", {
            "fields": ("avatar", "role")
        }),
        ("Permissions", {
            "fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")
        }),
        ("Soft Delete", {
            "fields": ("is_deleted", "deleted_at")
        }),
        ("Tracking", {
            "fields": ("created_at", "updated_at", "created_by_ip", "updated_by_ip")
        }),
    )

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("username", "email", "mobile", "password1", "password2"),
        }),
    )

    filter_horizontal = ("groups", "user_permissions")