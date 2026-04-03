"""
inventory/admin.py
==================

Admin for Inventory System
Optimized for:
- Fast product management
- Inline editing (media, tags)
- Stock visibility
- Clean UX for large datasets
"""

from django.contrib import admin
from django.utils.html import format_html

from .models import (
    Product,
    ProductCategory,
    ProductStatus,
    ProductSize,
    ProductProfile,
    ProductMedia,
    ProductTag,
)


# ============================================================================
# Inline: Product Media (Images)
# ============================================================================

class ProductMediaInline(admin.TabularInline):
    model = ProductMedia
    extra = 1
    fields = ("image_preview", "image", "image_description")
    readonly_fields = ("image_preview",)

    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" width="60" style="border-radius:6px;" />',
                obj.image.url
            )
        return "-"
    image_preview.short_description = "Preview"


# ============================================================================
# Inline: Product Tags
# ============================================================================

class ProductTagInline(admin.TabularInline):
    model = ProductTag
    extra = 1
    fields = ("tag_name", "tag_description")


# ============================================================================
# Product Admin (MAIN)
# ============================================================================

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "pid",
        "name",
        "category",
        "status",
        "size",
        "price_display",
        "quantity",
        "stock_status",
        "created_at",
    )

    list_filter = (
        "category",
        "status",
        "size",
        "created_at",
    )

    search_fields = ("name", "pid", "description")

    readonly_fields = ("pid", "created_at", "updated_at")

    autocomplete_fields = ("category", "status", "size", "profile")

    inlines = [ProductMediaInline, ProductTagInline]

    list_select_related = ("category", "status", "size", "profile")

    ordering = ("-created_at",)

    # ------------------------------------------------------------------
    # Custom UI fields
    # ------------------------------------------------------------------

    def price_display(self, obj):
        return f"₹{obj.discounted_price} / ₹{obj.fixed_price}"
    price_display.short_description = "Price"

    def stock_status(self, obj):
        if obj.quantity == 0:
            return "❌ Out"
        elif obj.quantity < 10:
            return "⚠️ Low"
        return "✅ OK"
    stock_status.short_description = "Stock"

    # ------------------------------------------------------------------
    # Bulk Actions
    # ------------------------------------------------------------------

    actions = ["mark_out_of_stock", "mark_in_stock"]

    def mark_out_of_stock(self, request, queryset):
        queryset.update(quantity=0)
    mark_out_of_stock.short_description = "Mark selected as OUT OF STOCK"

    def mark_in_stock(self, request, queryset):
        queryset.update(quantity=100)
    mark_in_stock.short_description = "Restock (set qty = 100)"


# ============================================================================
# Product Category
# ============================================================================

@admin.register(ProductCategory)
class ProductCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "description")
    search_fields = ("name",)


# ============================================================================
# Product Status
# ============================================================================

@admin.register(ProductStatus)
class ProductStatusAdmin(admin.ModelAdmin):
    list_display = ("status_name",)
    search_fields = ("status_name",)


# ============================================================================
# Product Size
# ============================================================================

@admin.register(ProductSize)
class ProductSizeAdmin(admin.ModelAdmin):
    list_display = ("size_name", "weight", "unit")
    list_filter = ("size_name", "unit")
    search_fields = ("size_name",)


# ============================================================================
# Product Profile (Nutrition)
# ============================================================================

@admin.register(ProductProfile)
class ProductProfileAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "calories",
        "protein",
        "carbohydrates",
        "fats",
    )

    search_fields = ("id",)

    readonly_fields = ("created_at", "updated_at")


# ============================================================================
# Product Media (Standalone)
# ============================================================================

@admin.register(ProductMedia)
class ProductMediaAdmin(admin.ModelAdmin):
    list_display = ("product", "image_preview", "image_description")
    autocomplete_fields = ("product",)

    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="80" />', obj.image.url)
        return "-"
    image_preview.short_description = "Preview"


# ============================================================================
# Product Tags (Standalone)
# ============================================================================

@admin.register(ProductTag)
class ProductTagAdmin(admin.ModelAdmin):
    list_display = ("tag_name", "product")
    search_fields = ("tag_name", "product__name")
    autocomplete_fields = ("product",)