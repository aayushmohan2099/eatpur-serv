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

    ingredients = models.TextField(blank=True, verbose_name="Ingredients")
    cooking_instructions = models.TextField(blank=True, verbose_name="Instructions for Cooking")
    highlights = models.TextField(blank=True, verbose_name="Product Highlights")

    is_trending = models.BooleanField(default=False, db_index=True, verbose_name="Is Trending")

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

# ===========================================================================
# ProductLike — Public / Anonymous
# ===========================================================================

class ProductLike(SoftDeleteMixin):
    """
    Tracks likes on a product.
    Can be liked by authenticated users OR anonymous users (tracked via IP).
    """
    product = models.ForeignKey(
        Product, 
        on_delete=models.CASCADE, 
        related_name="likes", 
        db_index=True
    )
    user = models.ForeignKey(
        "user.CustomUser", 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True, 
        db_index=True,
        help_text="Null if liked by an anonymous user."
    )
    ip_address = models.GenericIPAddressField(db_index=True)

    class Meta:
        db_table = "product_like"
        verbose_name = "Product Like"
        verbose_name_plural = "Product Likes"
        indexes = [
            models.Index(fields=["product", "ip_address"]),
            models.Index(fields=["product", "user"]),
        ]

    def __str__(self):
        return f"Like on {self.product.pid} by {self.user.username if self.user else self.ip_address}"


# ===========================================================================
# ProductComment — Authenticated Reviews
# ===========================================================================

class ProductComment(SoftDeleteMixin):
    """
    User reviews/comments on a product. Strictly for authenticated users.
    """
    product = models.ForeignKey(
        Product, 
        on_delete=models.CASCADE, 
        related_name="comments", 
        db_index=True
    )
    user = models.ForeignKey(
        "user.CustomUser", 
        on_delete=models.CASCADE, 
        related_name="product_comments",
        db_index=True
    )
    rating = models.PositiveSmallIntegerField(
        null=True, blank=True, 
        help_text="1 to 5 star rating (Optional)"
    )
    content = models.TextField(verbose_name="Review Content")
    
    is_approved = models.BooleanField(
        default=True, 
        db_index=True, 
        help_text="Set to False if you want manual moderation."
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        db_table = "product_comment"
        verbose_name = "Product Comment"
        verbose_name_plural = "Product Comments"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["product", "is_approved"]),
        ]

    def __str__(self):
        return f"Comment by {self.user.username} on {self.product.pid}"


# ===========================================================================
# ProductCommentImage — Max 3 per comment
# ===========================================================================

class ProductCommentImage(SoftDeleteMixin):
    """
    Images attached to a ProductComment. Enforced max 3 at API level.
    """
    comment = models.ForeignKey(
        ProductComment, 
        on_delete=models.CASCADE, 
        related_name="images"
    )
    image = models.ImageField(upload_to="products/reviews/%Y/%m/")

    class Meta:
        db_table = "product_comment_image"
        verbose_name = "Product Comment Image"
        verbose_name_plural = "Product Comment Images"

    def __str__(self):
        return f"Image for Comment #{self.comment_id}"

# ===========================================================================
# ProductShippingDimension — Shipment/package dimensions
# ===========================================================================

class ProductShippingDimension(SoftDeleteMixin):
    """
    Stores the standard shipping/package dimensions for a product.

    These values are intended for courier/shipping APIs such as Ekart.

    Ekart requirements:
        weight : integer, in grams
        length : integer, in centimeters
        height : integer, in centimeters
        width  : integer, in centimeters
    """

    product = models.OneToOneField(
        Product,
        on_delete=models.CASCADE,
        related_name="shipping_dimension",
        db_index=True,
        verbose_name="Product",
    )

    weight = models.PositiveIntegerField(
        verbose_name="Package Weight (grams)",
        help_text="Shipping package weight in grams.",
    )

    length = models.PositiveIntegerField(
        verbose_name="Package Length (cm)",
        help_text="Shipping package length in centimeters.",
    )

    height = models.PositiveIntegerField(
        verbose_name="Package Height (cm)",
        help_text="Shipping package height in centimeters.",
    )

    width = models.PositiveIntegerField(
        verbose_name="Package Width (cm)",
        help_text="Shipping package width in centimeters.",
    )

    class Meta:
        db_table = "product_shipping_dimension"
        verbose_name = "Product Shipping Dimension"
        verbose_name_plural = "Product Shipping Dimensions"

    def __str__(self):
        return (
            f"{self.product.pid} — "
            f"{self.length} × {self.width} × {self.height} cm, "
            f"{self.weight} g"
        )        