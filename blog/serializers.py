"""
blog/serializers.py
"""

from rest_framework import serializers
from django.utils.text import slugify
from .models import *
from user.models import CustomUser

# ===========================================================================
# BlogBlock
# ===========================================================================

class BlogBlockReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = BlogBlock
        fields = ["id", "type", "order", "content", "image", "meta"]
        read_only_fields = fields


class BlogBlockWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = BlogBlock
        fields = ["type", "order", "content", "image", "meta"]

    def validate(self, attrs):
        block_type = attrs.get("type")
        content = attrs.get("content")
        image = attrs.get("image")

        if block_type == "image" and not image:
            raise serializers.ValidationError({"image": "An image file is required for image blocks."})
        if block_type in ("text", "video", "quote", "code") and not content:
            raise serializers.ValidationError({"content": f"Content is required for '{block_type}' blocks."})
        return attrs


# ===========================================================================
# BlogComment
# ===========================================================================

class BlogCommentReplySerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(read_only=True)
    is_reply = serializers.BooleanField(read_only=True)

    class Meta:
        model = BlogComment
        fields = [
            "id", "display_name", "content", "is_approved", "created_at", "is_reply",
        ]
        read_only_fields = fields


class BlogCommentSerializer(serializers.ModelSerializer):
    replies = serializers.SerializerMethodField()
    display_name = serializers.CharField(read_only=True)
    is_reply = serializers.BooleanField(read_only=True)

    class Meta:
        model = BlogComment
        fields = [
            "id", "blog", "user", "display_name", "content", "ip_address",
            "is_approved", "approved_at", "parent", "replies", "is_reply", "created_at",
        ]
        read_only_fields = [
            "id", "user", "display_name", "ip_address", "is_approved",
            "approved_at", "replies", "is_reply", "created_at",
        ]

    def get_replies(self, obj):
        qs = obj.replies.filter(is_deleted=False, is_approved=True).order_by("created_at")
        return BlogCommentReplySerializer(qs, many=True).data

    def validate_parent(self, parent):
        if parent and parent.parent_id is not None:
            raise serializers.ValidationError("Replies to replies are not supported.")
        return parent


# ===========================================================================
# BlogReaction
# ===========================================================================

class BlogReactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = BlogReaction
        fields = ["id", "blog", "reaction_type", "created_at"]
        read_only_fields = fields


# ===========================================================================
# Blog — List (lightweight)
# ===========================================================================

class BlogListSerializer(serializers.ModelSerializer):
    display_author = serializers.SerializerMethodField()
    approval_status = serializers.SerializerMethodField()
    likes_count = serializers.IntegerField(read_only=True)
    dislikes_count = serializers.IntegerField(read_only=True)
    comments_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Blog
        fields = [
            "id", "urid", "title", "slug", "display_author", "approval_status", "cover_image",
            "meta_description", "read_time_minutes", "is_published", "published_at",
            "likes_count", "dislikes_count", "comments_count", "created_at", "updated_at",
        ]
        read_only_fields = list(fields)

    def get_display_author(self, obj):
        if obj.author:
            return obj.author.username
        return obj.guest_name or "Anonymous"
    
    def get_approval_status(self, obj):
        latest_approval = obj.approval.all().last()
        if latest_approval:
            return latest_approval.status
        return "DRAFT"


# ===========================================================================
# Blog — Detail (full nested read)
# ===========================================================================

class BlogDetailSerializer(serializers.ModelSerializer):
    blocks = BlogBlockReadSerializer(many=True, read_only=True)
    comments = serializers.SerializerMethodField()
    display_author = serializers.SerializerMethodField()
    likes_count = serializers.IntegerField(read_only=True)
    dislikes_count = serializers.IntegerField(read_only=True)
    comments_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Blog
        fields = [
            "id", "urid", "title", "slug", "display_author", "cover_image",
            "meta_description", "read_time_minutes", "is_published", "published_at",
            "likes_count", "dislikes_count", "comments_count", "blocks", "comments",
            "created_at", "updated_at",
        ]
        read_only_fields = fields

    def get_display_author(self, obj):
        if obj.author:
            return obj.author.username
        return obj.guest_name or "Anonymous"

    def get_comments(self, obj):
        qs = (
            obj.comments
            .filter(is_deleted=False, is_approved=True, parent__isnull=True)
            .select_related("user")
            .prefetch_related("replies")
            .order_by("created_at")
        )
        return BlogCommentSerializer(qs, many=True).data


# ===========================================================================
# Blog — Write (create / update via multipart)
# ===========================================================================

class BlogWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Blog
        fields = [
            "title", "slug", "author", "guest_name", "cover_image",
            "meta_description", "read_time_minutes", "is_published",
        ]
        extra_kwargs = {
            "slug": {"required": False},
            "author": {"required": False},
        }

    def validate_title(self, value):
        if len(value.strip()) < 3:
            raise serializers.ValidationError("Title must be at least 3 characters.")
        return value.strip()

    def validate(self, attrs):
        if not attrs.get("slug") and attrs.get("title"):
            attrs["slug"] = slugify(attrs["title"])
        return attrs

    @staticmethod
    def _parse_blocks(request) -> list[dict]:
        import json
        blocks = []
        i = 0
        while True:
            prefix = f"blocks[{i}]"
            if f"{prefix}[type]" not in request.data:
                break

            block_type = request.data.get(f"{prefix}[type]")
            order_raw = request.data.get(f"{prefix}[order]", i)
            content = request.data.get(f"{prefix}[content]") or None
            image = request.FILES.get(f"{prefix}[image]") or None
            meta_raw = request.data.get(f"{prefix}[meta]")

            meta = None
            if meta_raw:
                try:
                    meta = json.loads(meta_raw)
                except (ValueError, TypeError):
                    pass 

            blocks.append({
                "type": block_type, "order": int(order_raw), "content": content,
                "image": image, "meta": meta,
            })
            i += 1
        return blocks

    @staticmethod
    def _validate_and_create_blocks(blog, raw_blocks: list[dict]):
        serializers_list = [BlogBlockWriteSerializer(data=b) for b in raw_blocks]
        errors = {}
        for idx, s in enumerate(serializers_list):
            if not s.is_valid():
                errors[f"blocks[{idx}]"] = s.errors

        if errors:
            raise serializers.ValidationError(errors)

        BlogBlock.objects.bulk_create([
            BlogBlock(blog=blog, **s.validated_data)
            for s in serializers_list
        ])

    def create(self, validated_data):
        request = self.context["request"]

        # Handle Anonymous vs Authenticated Authors
        if request.user.is_authenticated:
            validated_data["author"] = request.user
        else:
            validated_data["author"] = None
            # If front-end doesn't supply a guest_name, we set a fallback
            if "guest_name" not in validated_data:
                validated_data["guest_name"] = "Anonymous Guest"

        from core.mixins import get_client_ip
        ip = get_client_ip(request)
        validated_data["created_by_ip"] = ip
        validated_data["updated_by_ip"] = ip

        blog = Blog.objects.create(**validated_data)

        raw_blocks = self._parse_blocks(request)
        if raw_blocks:
            self._validate_and_create_blocks(blog, raw_blocks)

        return blog

    def update(self, instance, validated_data):
        request = self.context["request"]
        from core.mixins import get_client_ip
        validated_data["updated_by_ip"] = get_client_ip(request)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        raw_blocks = self._parse_blocks(request)
        if raw_blocks:
            instance.blocks.filter(is_deleted=False).update(is_deleted=True)
            self._validate_and_create_blocks(instance, raw_blocks)

        return instance
    
# ===========================================================================
# Blog — Approval Serializer
# ===========================================================================    

class BlogReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = BlogApproval
        fields = ['blog', 'status', 'rejection_reason']

    def validate(self, data):
        approval_status = data.get('status')
        rejection_reason = data.get('rejection_reason')

        # 1. Enforce correct status choices for this endpoint
        if approval_status not in ['APPROVED', 'REJECTED']:
            raise serializers.ValidationError({
                "status": "You can only submit 'APPROVED' or 'REJECTED' via this endpoint."
            })

        # 2. Enforce rejection reason
        if approval_status == 'REJECTED' and not rejection_reason:
            raise serializers.ValidationError({
                "rejection_reason": "A rejection reason must be provided when rejecting a blog."
            })

        # 3. Clean up rejection reason if they accidentally send one while approving
        if approval_status == 'APPROVED' and rejection_reason:
            data['rejection_reason'] = None

        return data
    
# ===========================================================================
# Blog — Author Analytics
# ===========================================================================    

class BlogAuthorAnalyticsSerializer(serializers.ModelSerializer):
    total_blogs = serializers.IntegerField(read_only=True)
    total_views = serializers.IntegerField(read_only=True)
    total_likes = serializers.IntegerField(read_only=True)
    total_comments = serializers.IntegerField(read_only=True)
    
    # Calculated Fields
    avg_views = serializers.SerializerMethodField()
    avg_likes = serializers.SerializerMethodField()
    avg_comments = serializers.SerializerMethodField()

    class Meta:
        model = CustomUser
        fields = [
            "id", "urid", "username", "email", "avatar",
            "total_blogs", "total_views", "total_likes", "total_comments",
            "avg_views", "avg_likes", "avg_comments"
        ]

    def get_avg_views(self, obj):
        if obj.total_blogs:
            return round(obj.total_views / obj.total_blogs, 1)
        return 0

    def get_avg_likes(self, obj):
        if obj.total_blogs:
            return round(obj.total_likes / obj.total_blogs, 1)
        return 0

    def get_avg_comments(self, obj):
        if obj.total_blogs:
            return round(obj.total_comments / obj.total_blogs, 1)
        return 0