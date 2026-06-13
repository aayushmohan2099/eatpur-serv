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