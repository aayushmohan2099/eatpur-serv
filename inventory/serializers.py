from rest_framework import serializers
from .models import (
    ProductCategory, ProductStatus, ProductSize, ProductProfile,
    Product, ProductMedia, ProductTag
)

class ProductCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductCategory
        fields = ["id", "name", "description"]

class ProductStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductStatus
        fields = ["id", "status_name"]

class ProductSizeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductSize
        fields = ["id", "size_name", "weight", "unit"]

class ProductProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductProfile
        fields = [
            "id", "calories", "protein", "carbohydrates", 
            "fibre", "fats", "additional_info"
        ]

class ProductMediaSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductMedia
        fields = ["id", "image", "image_description"]

class ProductTagSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductTag
        fields = ["id", "tag_name", "tag_description"]

# ---------------------------------------------------------------------------
# Shallow List Serializer (Optimized for list views)
# ---------------------------------------------------------------------------
class ProductListSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    status_name = serializers.CharField(source="status.status_name", read_only=True)
    size_display = serializers.SerializerMethodField()
    cover_image = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id", "pid", "name", "category_name", "status_name", 
            "size_display", "fixed_price", "discounted_price", 
            "quantity", "is_trending", "cover_image"
        ]

    def get_size_display(self, obj):
        return f"{obj.size.size_name} - {obj.size.weight}{obj.size.unit}"

    def get_cover_image(self, obj):
        first_media = obj.media.filter(is_deleted=False).first()
        if first_media and first_media.image:
            request = self.context.get("request")
            return request.build_absolute_uri(first_media.image.url) if request else first_media.image.url
        return None

# ---------------------------------------------------------------------------
# Deep Detail Serializer (Fully Nested)
# ---------------------------------------------------------------------------
class ProductDetailSerializer(serializers.ModelSerializer):
    category = ProductCategorySerializer(read_only=True)
    status = ProductStatusSerializer(read_only=True)
    size = ProductSizeSerializer(read_only=True)
    profile = ProductProfileSerializer(read_only=True)
    media = ProductMediaSerializer(many=True, read_only=True)
    tags = ProductTagSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = [
            "id", "pid", "name", "description", "category", "status", 
            "size", "profile", "fixed_price", "discounted_price", 
            "quantity", "is_trending", "media", "tags", 
            "created_at", "updated_at"
        ]

# ===========================================================================
# SUPERFAST PUBLIC FLAT SERIALIZER
# ===========================================================================
class PublicProductFlatSerializer(serializers.ModelSerializer):
    """
    100% Flat JSON response. No nested objects.
    Optimized for the public catalog browsing page.
    """
    category_name = serializers.CharField(source='category.name', read_only=True)
    status_name = serializers.CharField(source='status.status_name', read_only=True)
    
    size_name = serializers.CharField(source='size.size_name', read_only=True)
    weight = serializers.DecimalField(source='size.weight', max_digits=10, decimal_places=3, read_only=True)
    unit = serializers.CharField(source='size.unit', read_only=True)
    
    calories = serializers.DecimalField(source='profile.calories', max_digits=8, decimal_places=2, read_only=True)
    protein = serializers.DecimalField(source='profile.protein', max_digits=7, decimal_places=2, read_only=True)
    carbohydrates = serializers.DecimalField(source='profile.carbohydrates', max_digits=7, decimal_places=2, read_only=True)
    fibre = serializers.DecimalField(source='profile.fibre', max_digits=7, decimal_places=2, read_only=True)
    fats = serializers.DecimalField(source='profile.fats', max_digits=7, decimal_places=2, read_only=True)
    
    tags = serializers.SerializerMethodField()
    cover_image = serializers.SerializerMethodField()
    discount_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True) # Annotated in View
    discount_percentage = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            'id', 'pid', 'name', 'description', 'fixed_price', 'discounted_price', 
            'quantity', 'is_trending', 'category_name', 'status_name', 
            'size_name', 'weight', 'unit', 'calories', 'protein', 'carbohydrates', 
            'fibre', 'fats', 'tags', 'cover_image', 'discount_amount', 'discount_percentage'
        ]

    def get_tags(self, obj):
        # Extremely fast due to prefetch_related in the View
        return ", ".join(tag.tag_name for tag in obj.tags.all() if not tag.is_deleted)

    def get_cover_image(self, obj):
        # Returns ALL product images
        media_list = [m for m in obj.media.all() if not m.is_deleted]

        request = self.context.get('request')

        return [
            request.build_absolute_uri(m.image.url) if request else m.image.url
            for m in media_list
            if m.image
        ]
        
    def get_discount_percentage(self, obj):
        if obj.fixed_price and obj.fixed_price > 0:
            diff = obj.fixed_price - obj.discounted_price
            return round((diff / obj.fixed_price) * 100, 1)
        return 0        