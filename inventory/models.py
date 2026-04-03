"""
inventory/models.py
===================
Highly normalised product management system.

Table Map
---------
ProductCategory   → product classification
ProductStatus     → IN_STOCK / LOW / OUT_OF_STOCK / PROCESSING / REVIEW / REJECTED
ProductSize       → SMALL / MEDIUM / LARGE + weight metadata
ProductProfile    → nutritional / metadata details (separate to keep Product lean)
Product           → core product entity with auto-generated PID
ProductMedia      → images per product
ProductTag        → flexible tagging per product

PID format: {FIRST3(name)}-{FIRST4(category)}-{RANDOM_ALPHANUM(6)}
Example   : MIL-BEVR-A92KX1
"""

import random
import string
import re

from django.db import models, transaction

from core.mixins import SoftDeleteMixin


# ---------------------------------------------------------------------------
# PID generation helper
# ---------------------------------------------------------------------------

def _slug(text: str, length: int) -> str:
    """Return first `length` uppercase alphanumeric characters from `text`."""
    clean = re.sub(r"[^A-Z0-9]", "", text.upper())
    return clean[:length].ljust(length, "X")  # pad with X if too short


def _random_alphanum(length: int = 6) -> str:
    chars = string.ascii_uppercase + string.digits
    return "".join(random.choices(chars, k=length))


def generate_pid(product_name: str, category_name: str) -> str:
    """
    Generate a unique PID.
    Format: FIRST3(name)-FIRST4(category)-RANDOM6
    Collision chance is negligible but callers should retry if needed.
    """
    prefix = _slug(product_name, 3)
    cat = _slug(category_name, 4)
    suffix = _random_alphanum(6)
    return f"{prefix}-{cat}-{suffix}"


# ===========================================================================
# LOOKUP: ProductCategory
# ===========================================================================

class ProductCategory(SoftDeleteMixin):
    """Top-level product classification (e.g., Beverages, Snacks, Dairy)."""

    name = models.CharField(
        max_length=120, unique=True, db_index=True, verbose_name="Category Name"
    )
    description = models.TextField(blank=True, verbose_name="Description")

    class Meta:
        db_table = "product_category"
        verbose_name = "Product Category"
        verbose_name_plural = "Product Categories"
        ordering = ["name"]

    def __str__(self):
        return self.name


# ===========================================================================
# LOOKUP: ProductStatus
# ===========================================================================

class ProductStatus(SoftDeleteMixin):
    """
    Represents the lifecycle / availability state of a product.
    Examples: IN_STOCK, LOW, OUT_OF_STOCK, PROCESSING, REVIEW, REJECTED
    """

    STATUS_CHOICES = [
        ("IN_STOCK", "In Stock"),
        ("LOW", "Low Stock"),
        ("OUT_OF_STOCK", "Out of Stock"),
        ("PROCESSING", "Processing"),
        ("REVIEW", "Under Review"),
        ("REJECTED", "Rejected"),
    ]

    status_name = models.CharField(
        max_length=30,
        unique=True,
        choices=STATUS_CHOICES,
        verbose_name="Status Name",
    )

    class Meta:
        db_table = "product_status"
        verbose_name = "Product Status"
        verbose_name_plural = "Product Statuses"

    def __str__(self):
        return self.status_name


# ===========================================================================
# LOOKUP: ProductSize
# ===========================================================================

class ProductSize(SoftDeleteMixin):
    """
    Describes a product's physical size and weight.

    size_name : SMALL / MEDIUM / LARGE
    weight    : numeric weight value
    unit      : g, kg, ml, l, etc.
    """

    SIZE_CHOICES = [
        ("SMALL", "Small"),
        ("MEDIUM", "Medium"),
        ("LARGE", "Large"),
    ]

    UNIT_CHOICES = [
        ("g", "Grams"),
        ("kg", "Kilograms"),
        ("ml", "Millilitres"),
        ("l", "Litres"),
        ("oz", "Ounces"),
        ("lb", "Pounds"),
        ("pcs", "Pieces"),
    ]

    size_name = models.CharField(
        max_length=10,
        choices=SIZE_CHOICES,
        db_index=True,
        verbose_name="Size Name",
    )
    weight = models.DecimalField(
        max_digits=10, decimal_places=3, verbose_name="Weight"
    )
    unit = models.CharField(
        max_length=5, choices=UNIT_CHOICES, verbose_name="Unit"
    )

    class Meta:
        db_table = "product_size"
        verbose_name = "Product Size"
        verbose_name_plural = "Product Sizes"
        unique_together = [("size_name", "weight", "unit")]

    def __str__(self):
        return f"{self.size_name} — {self.weight}{self.unit}"


# ===========================================================================
# ProductProfile — Nutritional / metadata
# ===========================================================================

class ProductProfile(SoftDeleteMixin):
    """
    Stores nutritional information for a product (per serving / per 100 g).

    Kept separate from Product to:
    * Keep the Product table lean for high-frequency reads.
    * Allow re-use if multiple SKUs share a nutritional profile.
    * Make partial updates cheap.

    additional_info is a flexible JSON field for future attributes
    (e.g., allergens, certifications, country of origin).
    """

    calories = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True, verbose_name="Calories (kcal)"
    )
    protein = models.DecimalField(
        max_digits=7, decimal_places=2, null=True, blank=True, verbose_name="Protein (g)"
    )
    carbohydrates = models.DecimalField(
        max_digits=7, decimal_places=2, null=True, blank=True, verbose_name="Carbohydrates (g)"
    )
    fibre = models.DecimalField(
        max_digits=7, decimal_places=2, null=True, blank=True, verbose_name="Dietary Fibre (g)"
    )
    fats = models.DecimalField(
        max_digits=7, decimal_places=2, null=True, blank=True, verbose_name="Total Fats (g)"
    )

    # Flexible bucket for additional nutritional / metadata fields
    additional_info = models.JSONField(
        null=True, blank=True, verbose_name="Additional Info (JSON)"
    )

    class Meta:
        db_table = "product_profile"
        verbose_name = "Product Profile"
        verbose_name_plural = "Product Profiles"

    def __str__(self):
        return f"Profile#{self.pk} — {self.calories} kcal"


# ===========================================================================
# Product — Core entity
# ===========================================================================

class Product(SoftDeleteMixin):
    """
    Central product record.

    PID is auto-generated on first save using the helper:
        generate_pid(product_name, category_name)

    fixed_price    : original / RRP price
    discounted_price: current selling price (may equal fixed_price)
    quantity       : current stock count — updated by inventory operations
    """

    name = models.CharField(
        max_length=255, db_index=True, verbose_name="Product Name"
    )
    description = models.TextField(blank=True, verbose_name="Description")

    category = models.ForeignKey(
        ProductCategory,
        on_delete=models.SET_NULL,
        null=True,
        related_name="products",
        db_index=True,
        verbose_name="Category",
    )
    status = models.ForeignKey(
        ProductStatus,
        on_delete=models.SET_NULL,
        null=True,
        related_name="products",
        db_index=True,
        verbose_name="Status",
    )
    size = models.ForeignKey(
        ProductSize,
        on_delete=models.SET_NULL,
        null=True,
        related_name="products",
        db_index=True,
        verbose_name="Size",
    )
    profile = models.ForeignKey(
        ProductProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="products",
        db_index=True,
        verbose_name="Nutritional Profile",
    )

    # Pricing
    fixed_price = models.DecimalField(
        max_digits=12, decimal_places=2, verbose_name="Fixed Price"
    )
    discounted_price = models.DecimalField(
        max_digits=12, decimal_places=2, verbose_name="Discounted Price"
    )

    # Inventory
    quantity = models.PositiveIntegerField(default=0, verbose_name="Stock Quantity")

    # Auto-generated unique product identifier
    pid = models.CharField(
        max_length=20,
        unique=True,
        db_index=True,
        editable=False,
        verbose_name="Product ID (PID)",
    )

    class Meta:
        db_table = "product"
        verbose_name = "Product"
        verbose_name_plural = "Products"
        indexes = [
            models.Index(fields=["pid"]),
            models.Index(fields=["name"]),
            models.Index(fields=["category"]),
            models.Index(fields=["status"]),
        ]

    # ------------------------------------------------------------------
    # PID auto-generation
    # ------------------------------------------------------------------

    def _generate_unique_pid(self) -> str:
        """Generate a PID and retry until a unique one is found."""
        for _ in range(10):
            candidate = generate_pid(
                self.name,
                self.category.name if self.category else "UNKN",
            )
            if not Product.all_objects.filter(pid=candidate).exists():
                return candidate
        raise RuntimeError("Could not generate unique PID after 10 attempts.")

    def save(self, *args, **kwargs):
        if not self.pid:
            self.pid = self._generate_unique_pid()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"[{self.pid}] {self.name}"


# ===========================================================================
# ProductMedia — Product images
# ===========================================================================

class ProductMedia(SoftDeleteMixin):
    """
    Supports multiple images per product.
    `image` stores the file; `image_description` is alt-text / caption.
    """

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="media",
        db_index=True,
        verbose_name="Product",
    )
    image = models.ImageField(
        upload_to="products/media/%Y/%m/", verbose_name="Image"
    )
    image_description = models.CharField(
        max_length=500, blank=True, verbose_name="Image Description"
    )

    class Meta:
        db_table = "product_media"
        verbose_name = "Product Media"
        verbose_name_plural = "Product Media"

    def __str__(self):
        return f"Media for {self.product.pid}"


# ===========================================================================
# ProductTag — Flexible tagging
# ===========================================================================

class ProductTag(SoftDeleteMixin):
    """
    Free-form tags per product (e.g., "vegan", "gluten-free", "bestseller").
    Allows rich filtering and discovery without schema changes.
    """

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="tags",
        db_index=True,
        verbose_name="Product",
    )
    tag_name = models.CharField(
        max_length=100, db_index=True, verbose_name="Tag Name"
    )
    tag_description = models.CharField(
        max_length=255, blank=True, verbose_name="Tag Description"
    )

    class Meta:
        db_table = "product_tags"
        verbose_name = "Product Tag"
        verbose_name_plural = "Product Tags"
        unique_together = [("product", "tag_name")]
        indexes = [
            models.Index(fields=["tag_name"]),
        ]

    def __str__(self):
        return f"{self.tag_name} → {self.product.pid}"
