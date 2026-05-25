# core/views/dashboard_views.py

from django.db.models import Count, Q

from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from blog.models import Blog, BlogBlock, BlogComment, BlogReaction
from messaging.models import GoogleFormResponse
from inventory.models import (
    Product,
    ProductCategory,
    ProductMedia,
    ProductProfile,
    ProductSize,
    ProductStatus,
    ProductTag,
)


# ===========================================================================
# Blog Serializers
# ===========================================================================

class BlogBlockSerializer(serializers.ModelSerializer):
    class Meta:
        model = BlogBlock
        exclude = ["is_deleted", "deleted_at", "created_by_ip", "updated_by_ip"]


class BlogReactionSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = BlogReaction
        exclude = ["is_deleted", "deleted_at", "created_by_ip", "updated_by_ip"]


class BlogCommentSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    replies = serializers.SerializerMethodField()

    class Meta:
        model = BlogComment
        exclude = ["is_deleted", "deleted_at", "created_by_ip", "updated_by_ip"]

    def get_replies(self, obj):
        # Only top-level comments carry nested replies (avoids infinite recursion)
        if obj.parent_id is not None:
            return []
        qs = obj.replies.filter(is_deleted=False).order_by("created_at")
        return BlogCommentSerializer(qs, many=True).data


class TopBlogSerializer(serializers.ModelSerializer):
    blocks = serializers.SerializerMethodField()
    reactions = serializers.SerializerMethodField()
    comments = serializers.SerializerMethodField()
    author_username = serializers.CharField(source="author.username", read_only=True)
    likes_count = serializers.IntegerField(source="like_count", read_only=True)
    dislikes_count = serializers.SerializerMethodField()
    comments_count = serializers.SerializerMethodField()
    display_author = serializers.SerializerMethodField()

    class Meta:
        model = Blog
        exclude = ["is_deleted", "deleted_at", "created_by_ip", "updated_by_ip"]

    def get_blocks(self, obj):
        qs = obj.blocks.filter(is_deleted=False).order_by("order")
        return BlogBlockSerializer(qs, many=True).data

    def get_reactions(self, obj):
        qs = obj.reactions.filter(is_deleted=False)
        return BlogReactionSerializer(qs, many=True).data

    def get_comments(self, obj):
        # Only top-level comments; replies are nested inside each comment
        qs = obj.comments.filter(is_deleted=False, parent__isnull=True).order_by("created_at")
        return BlogCommentSerializer(qs, many=True).data

    def get_dislikes_count(self, obj):
        return obj.reactions.filter(reaction_type="dislike", is_deleted=False).count()

    def get_comments_count(self, obj):
        return obj.comments.filter(is_deleted=False).count()

    def get_display_author(self, obj):
        if obj.author:
            return obj.author.username
        return obj.guest_name or "Anonymous Guest"


# ===========================================================================
# Inventory Serializers
# ===========================================================================

class ProductCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductCategory
        exclude = ["is_deleted", "deleted_at", "created_by_ip", "updated_by_ip"]


class ProductStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductStatus
        exclude = ["is_deleted", "deleted_at", "created_by_ip", "updated_by_ip"]


class ProductSizeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductSize
        exclude = ["is_deleted", "deleted_at", "created_by_ip", "updated_by_ip"]


class ProductProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductProfile
        exclude = ["is_deleted", "deleted_at", "created_by_ip", "updated_by_ip"]


class ProductMediaSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductMedia
        exclude = ["is_deleted", "deleted_at", "created_by_ip", "updated_by_ip"]


class ProductTagSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductTag
        exclude = ["is_deleted", "deleted_at", "created_by_ip", "updated_by_ip"]


class TrendingProductSerializer(serializers.ModelSerializer):
    category = ProductCategorySerializer(read_only=True)
    status = ProductStatusSerializer(read_only=True)
    size = ProductSizeSerializer(read_only=True)
    profile = ProductProfileSerializer(read_only=True)
    media = serializers.SerializerMethodField()
    tags = serializers.SerializerMethodField()

    class Meta:
        model = Product
        exclude = ["is_deleted", "deleted_at", "created_by_ip", "updated_by_ip"]

    def get_media(self, obj):
        qs = obj.media.filter(is_deleted=False)
        return ProductMediaSerializer(qs, many=True).data

    def get_tags(self, obj):
        qs = obj.tags.filter(is_deleted=False)
        return ProductTagSerializer(qs, many=True).data


class TrendingByCategorySerializer(serializers.Serializer):
    category = ProductCategorySerializer(read_only=True)
    products = TrendingProductSerializer(many=True, read_only=True)

# ===========================================================================
# Google Form Response Serializers
# ===========================================================================

class GoogleFormResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = GoogleFormResponse
        exclude = ["is_deleted", "deleted_at", "created_by_ip", "updated_by_ip"]

# ===========================================================================
# Dashboard View
# ===========================================================================

class HomepageDashboardView(APIView):
    """
    GET /api/dashboard/
    Public endpoint. Returns:
      - top_blogs        : top 3 published blogs ordered by like count (all nested)
      - trending_by_category : trending products (is_trending=True) grouped by category
      - google_form_responses : recent Google Form responses
    """

    permission_classes = [AllowAny]

    def get(self, request):
        # ---------------------------------------------------------------
        # Top 3 Blogs — annotate like_count for DB-level ordering
        # ---------------------------------------------------------------
        top_blogs_qs = (
            Blog.objects.filter(is_deleted=False, is_published=True)
            .annotate(
                like_count=Count(
                    "reactions",
                    filter=Q(reactions__reaction_type="like", reactions__is_deleted=False),
                )
            )
            .order_by("-like_count", "-published_at")
            .select_related("author")
            .prefetch_related("blocks", "reactions", "comments__replies")[:3]
        )

        top_blogs_data = TopBlogSerializer(top_blogs_qs, many=True, context={"request": request}).data

        # ---------------------------------------------------------------
        # Trending Products — grouped by category
        # ---------------------------------------------------------------
        trending_categories = (
            ProductCategory.objects.filter(
                is_deleted=False,
                products__is_trending=True,
                products__is_deleted=False,
            )
            .distinct()
            .order_by("name")
        )

        trending_by_category = []
        for category in trending_categories:
            products_qs = (
                category.products.filter(is_deleted=False, is_trending=True)
                .select_related("category", "status", "size", "profile")
                .prefetch_related("media", "tags")
                .order_by("name")
            )
            trending_by_category.append(
                TrendingByCategorySerializer(
                    {"category": category, "products": products_qs}
                ).data
            )

        return Response(
            {
                "top_blogs": top_blogs_data,
                "trending_by_category": trending_by_category,
                "google_form_responses": GoogleFormResponseSerializer(GoogleFormResponse.objects.all().order_by("-created_at"), many=True).data,
            }
        )