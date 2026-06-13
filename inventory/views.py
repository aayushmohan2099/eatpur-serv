import json
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q

from .models import *
from .serializers import *
from rest_framework.decorators import action

# Helper to capture IP for soft_delete mixins
def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    return x_forwarded_for.split(',')[0] if x_forwarded_for else request.META.get('REMOTE_ADDR')

class ProductPagination(PageNumberPagination):
    page_size = 15
    page_size_query_param = "page_size"
    max_page_size = 50

class ProductViewSet(viewsets.ModelViewSet):
    """
    Handles List, Retrieve, Create (One-Shot), Update, and Destroy operations for Products.
    """
    pagination_class = ProductPagination
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    permission_classes = [IsAuthenticated]

    # -----------------------------------------------------------------------
    # 1. PRODUCTS LISTING
    # -----------------------------------------------------------------------

    def get_queryset(self):
        qs = Product.objects.filter(is_deleted=False).select_related(
            "category", "status", "size", "profile"
        ).prefetch_related("media", "tags")

        # 1. Filters
        category_id = self.request.query_params.get("category")
        size_id = self.request.query_params.get("size")
        tags_query = self.request.query_params.get("tags")

        if category_id:
            qs = qs.filter(category_id=category_id)
        if size_id:
            qs = qs.filter(size_id=size_id)
        if tags_query:
            qs = qs.filter(tags__tag_name__icontains=tags_query)

        return qs.distinct()

    def get_serializer_class(self):
        if self.action == "retrieve":
            return ProductDetailSerializer
        return ProductListSerializer

    # -----------------------------------------------------------------------
    # 2. ONE-SHOT CREATE API
    # -----------------------------------------------------------------------
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        role_id = getattr(request.user, "role_id", None)
        
        # Role-based status assignment
        if role_id == 5:
            target_status_code = "OUT_OF_STOCK"
        elif role_id == 1:
            target_status_code = "REVIEW"
        else:
            raise PermissionDenied("You do not have permission to create products.")

        status_obj, _ = ProductStatus.objects.get_or_create(status_name=target_status_code)
        
        # Extract core fields
        name = request.data.get("name")
        description = request.data.get("description", "")
        category_id = request.data.get("category_id")

        try:
            category_obj = ProductCategory.objects.get(id=category_id, is_deleted=False)
        except ProductCategory.DoesNotExist:
            return Response({"error": "Valid Category ID is required."}, status=status.HTTP_400_BAD_REQUEST)

        # Extract parsed JSON Strings
        variants_data = json.loads(request.data.get("variants", "[]"))
        tags_data = json.loads(request.data.get("tags", "[]"))
        images = request.FILES.getlist("images")

        if not variants_data:
            return Response({"error": "At least one variant (size) must be provided."}, status=status.HTTP_400_BAD_REQUEST)

        created_products = []

        # Iterate over multiple sizes (variants)
        for variant in variants_data:
            # 1. Size
            size_info = variant.get("size", {})
            size_obj, _ = ProductSize.objects.get_or_create(
                size_name=size_info.get("size_name", "MEDIUM"),
                weight=size_info.get("weight", 0),
                unit=size_info.get("unit", "g")
            )

            # 2. Profile
            profile_info = variant.get("profile", {})
            profile_obj = ProductProfile.objects.create(
                calories=profile_info.get("calories"),
                protein=profile_info.get("protein"),
                carbohydrates=profile_info.get("carbohydrates"),
                fibre=profile_info.get("fibre"),
                fats=profile_info.get("fats"),
                additional_info=profile_info.get("additional_info", {})
            )

            # 3. Create Product Variant
            product = Product.objects.create(
                name=name,
                description=description,
                category=category_obj,
                status=status_obj,
                size=size_obj,
                profile=profile_obj,
                fixed_price=variant.get("fixed_price", 0),
                discounted_price=variant.get("discounted_price", 0),
                quantity=variant.get("quantity", 0),
                is_trending=False
            )

            # 4. Attach Tags (Shared across variants)
            for tag in tags_data:
                ProductTag.objects.create(
                    product=product,
                    tag_name=tag.get("tag_name"),
                    tag_description=tag.get("tag_description", "")
                )

            # 5. Attach Media (Shared across variants)
            for img in images:
                ProductMedia.objects.create(product=product, image=img)

            created_products.append(product)

        return Response(
            {"message": f"Successfully created {len(created_products)} product variants."}, 
            status=status.HTTP_201_CREATED
        )

    # -----------------------------------------------------------------------
    # 3. UPDATE API (Updates single product variant, nested dicts, and media)
    # -----------------------------------------------------------------------
    @transaction.atomic
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', True)
        instance = self.get_object()

        # Update core fields
        if "name" in request.data: instance.name = request.data["name"]
        if "description" in request.data: instance.description = request.data["description"]
        if "category_id" in request.data: instance.category_id = request.data["category_id"]
        if "fixed_price" in request.data: instance.fixed_price = request.data["fixed_price"]
        if "discounted_price" in request.data: instance.discounted_price = request.data["discounted_price"]
        if "quantity" in request.data: instance.quantity = request.data["quantity"]
        if "is_trending" in request.data: instance.is_trending = str(request.data["is_trending"]).lower() == 'true'

        instance.save()

        # Update Nested Profile (if passed as JSON string)
        if "profile" in request.data:
            profile_data = json.loads(request.data["profile"])
            if instance.profile:
                for key, value in profile_data.items():
                    setattr(instance.profile, key, value)
                instance.profile.save()

        # Handle Nested Deletions (Tags and Media)
        delete_tag_ids = json.loads(request.data.get("delete_tag_ids", "[]"))
        if delete_tag_ids:
            ProductTag.objects.filter(id__in=delete_tag_ids, product=instance).update(is_deleted=True)

        delete_media_ids = json.loads(request.data.get("delete_media_ids", "[]"))
        if delete_media_ids:
            ProductMedia.objects.filter(id__in=delete_media_ids, product=instance).update(is_deleted=True)

        # Add New Tags
        new_tags = json.loads(request.data.get("new_tags", "[]"))
        for tag in new_tags:
            ProductTag.objects.create(
                product=instance,
                tag_name=tag.get("tag_name"),
                tag_description=tag.get("tag_description", "")
            )

        # Add New Media
        new_images = request.FILES.getlist("new_images")
        for img in new_images:
            ProductMedia.objects.create(product=instance, image=img)

        serializer = ProductDetailSerializer(instance, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    # -----------------------------------------------------------------------
    # 4. COMPLETE SOFT DELETE API
    # -----------------------------------------------------------------------
    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        client_ip = get_client_ip(request)

        # Soft Delete the core product
        instance.soft_delete(ip=client_ip)
        
        # Soft delete associated Profile
        if instance.profile:
            instance.profile.soft_delete(ip=client_ip)

        # Soft delete associated Media & Tags
        for media in instance.media.all():
            media.soft_delete(ip=client_ip)
            
        for tag in instance.tags.all():
            tag.soft_delete(ip=client_ip)

        return Response({"message": "Product and all related entities deleted."}, status=status.HTTP_204_NO_CONTENT)
    
    # -----------------------------------------------------------------------
    # 5. TOGGLE IS_TRENDING
    # -----------------------------------------------------------------------
    @action(detail=True, methods=["post"], url_path="toggle-trending")
    def toggle_trending(self, request, pk=None):
        product = self.get_object()
        product.is_trending = not product.is_trending
        product.save(update_fields=["is_trending", "updated_at"])
        
        return Response({
            "message": f"Trending status flipped to {product.is_trending}",
            "is_trending": product.is_trending
        }, status=status.HTTP_200_OK)

    # -----------------------------------------------------------------------
    # 6. GET ALL SIZES/VARIANTS FOR A PRODUCT
    # -----------------------------------------------------------------------
    @action(detail=True, methods=["get"], url_path="variants")
    def get_variants(self, request, pk=None):
        product = self.get_object()
        
        # Variants share the exact same name and category
        variants = Product.objects.filter(
            name=product.name, 
            category=product.category, 
            is_deleted=False
        ).select_related(
            "category", "status", "size", "profile"
        ).prefetch_related("media", "tags")

        serializer = ProductDetailSerializer(variants, many=True, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    # -----------------------------------------------------------------------
    # 7. BULK STATUS UPDATE (REVIEW -> OUT_OF_STOCK / REJECTED)
    # -----------------------------------------------------------------------
    @action(detail=False, methods=["post"], url_path="bulk-review-action")
    def bulk_review_action(self, request):
        # Strict Role Check
        if getattr(request.user, "role_id", None) != 5:
            raise PermissionDenied("Only users with role_id 5 are permitted to perform this action.")

        product_ids = request.data.get("product_ids", [])
        new_status_code = request.data.get("status")

        if not isinstance(product_ids, list) or len(product_ids) == 0:
            return Response({"error": "Please provide a valid list of 'product_ids'."}, status=status.HTTP_400_BAD_REQUEST)

        if new_status_code not in ["OUT_OF_STOCK", "REJECTED"]:
            return Response({"error": "Status must be OUT_OF_STOCK or REJECTED."}, status=status.HTTP_400_BAD_REQUEST)

        target_status, _ = ProductStatus.objects.get_or_create(status_name=new_status_code)

        # Update ONLY products that are currently in 'REVIEW' status
        updated_count = Product.objects.filter(
            id__in=product_ids,
            status__status_name="REVIEW",
            is_deleted=False
        ).update(status=target_status)

        return Response({
            "message": f"Successfully updated {updated_count} products from REVIEW to {new_status_code}."
        }, status=status.HTTP_200_OK)

    # -----------------------------------------------------------------------
    # 8. UPDATE QUANTITY & AUTO-CALCULATE STATUS
    # -----------------------------------------------------------------------
    @action(detail=True, methods=["post"], url_path="update-quantity")
    def update_quantity(self, request, pk=None):
        product = self.get_object()
        
        try:
            new_qty = int(request.data.get("quantity", product.quantity))
        except ValueError:
            return Response({"error": "Quantity must be an integer."}, status=status.HTTP_400_BAD_REQUEST)

        if new_qty < 0:
            return Response({"error": "Quantity cannot be negative."}, status=status.HTTP_400_BAD_REQUEST)

        product.quantity = new_qty

        # Status rules logic
        if new_qty == 0:
            status_name = "OUT_OF_STOCK"
        elif new_qty < 50:
            status_name = "LOW"
        else:
            status_name = "IN_STOCK"

        status_obj, _ = ProductStatus.objects.get_or_create(status_name=status_name)
        product.status = status_obj
        product.save(update_fields=["quantity", "status", "updated_at"])

        return Response({
            "message": "Quantity updated successfully.",
            "new_quantity": product.quantity,
            "new_status": status_name
        }, status=status.HTTP_200_OK)    
    
# ---------------------------------------------------------------------------
# 9. PRODUCT CATEGORY CRUD
# ---------------------------------------------------------------------------
class ProductCategoryViewSet(viewsets.ModelViewSet):
    """
    Standard List, Create, Update, and Delete for Product Categories.
    """
    serializer_class = ProductCategorySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return ProductCategory.objects.filter(is_deleted=False).order_by("name")

    def perform_destroy(self, instance):
        # Soft delete execution
        client_ip = get_client_ip(self.request)
        instance.soft_delete(ip=client_ip)    