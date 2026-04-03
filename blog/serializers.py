"""
blog/serializers.py
===================
Serializers for Blog, BlogBlock, BlogReaction, and BlogComment.

Design decisions
----------------
* BlogListSerializer  — lightweight, no blocks/comments, for list endpoints
* BlogDetailSerializer— full nested output with blocks, counts, threaded comments
* BlogWriteSerializer — handles multipart form data for create/update
* BlogBlockSerializer — read-only nested output; separate write path via BlogWriteSerializer
* BlogCommentSerializer — recursive replies (2-level safe for most use cases)
* BlogReactionSerializer — minimal; reactions are managed via a dedicated view
"""

from rest_framework import serializers
from django.utils.text import slugify
from .models import Blog, BlogBlock, BlogReaction, BlogComment


# ===========================================================================
# BlogBlock
# ===========================================================================

class BlogBlockReadSerializer(serializers.ModelSerializer):
    """Lightweight block serializer used inside BlogDetailSerializer."""

    class Meta:
        model = BlogBlock
        fields = ["id", "type", "order", "content", "image", "meta"]
        read_only_fields = fields


class BlogBlockWriteSerializer(serializers.ModelSerializer):
    """
    Used internally when creating/updating blocks from BlogWriteSerializer.
    `blog` is injected by the parent — not exposed to the client.
    """

    class Meta:
        model = BlogBlock
        fields = ["type", "order", "content", "image", "meta"]

    def validate(self, attrs):
        block_type = attrs.get("type")
        content = attrs.get("content")
        image = attrs.get("image")

        if block_type == "image" and not image:
            raise serializers.ValidationError(
                {"image": "An image file is required for blocks of type 'image'."}
            )
        if block_type in ("text", "video", "quote", "code") and not content:
            raise serializers.ValidationError(
                {"content": f"Content is required for blocks of type '{block_type}'."}
            )
        return attrs


# ===========================================================================
# BlogComment
# ===========================================================================

class BlogCommentReplySerializer(serializers.ModelSerializer):
    """
    Flat serializer for replies (one level deep).
    Using a flat serializer here (not recursive) avoids N+1 hell.
    """
    display_name = serializers.CharField(read_only=True)
    is_reply = serializers.BooleanField(read_only=True)

    class Meta:
        model = BlogComment
        fields = [
            "id", "display_name", "name", "email",
            "content", "is_approved", "created_at", "is_reply",
        ]
        read_only_fields = [
            "id", "display_name", "is_approved", "created_at", "is_reply",
        ]


class BlogCommentSerializer(serializers.ModelSerializer):
    """
    Top-level comment serializer with nested replies.

    Write fields  : blog (injected), name, email, content, parent
    Read-only     : replies, display_name, is_approved, is_reply, created_at

    `user` is injected from the request in BlogCommentView — not writable
    by the client directly to prevent impersonation.
    """

    replies = serializers.SerializerMethodField()
    display_name = serializers.CharField(read_only=True)
    is_reply = serializers.BooleanField(read_only=True)

    class Meta:
        model = BlogComment
        fields = [
            "id",
            "blog",
            "user",
            "display_name",
            "name",
            "email",
            "content",
            "ip_address",
            "is_approved",
            "approved_at",
            "parent",
            "replies",
            "is_reply",
            "created_at",
        ]
        read_only_fields = [
            "id", "user", "display_name", "ip_address",
            "is_approved", "approved_at", "replies",
            "is_reply", "created_at",
        ]

    def get_replies(self, obj):
        """Return approved, non-deleted direct replies only."""
        qs = obj.replies.filter(is_deleted=False, is_approved=True).order_by("created_at")
        return BlogCommentReplySerializer(qs, many=True).data

    def validate_parent(self, parent):
        """Replies can only be one level deep — no nested replies to replies."""
        if parent and parent.parent_id is not None:
            raise serializers.ValidationError(
                "Replies to replies are not supported. Please reply to the top-level comment."
            )
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
    """
    Used on list endpoints — no blocks, no comments, just card-level data.
    Includes live counts via model @property.
    """
    author_username = serializers.CharField(source="author.username", read_only=True, default=None)
    likes_count = serializers.IntegerField(read_only=True)
    dislikes_count = serializers.IntegerField(read_only=True)
    comments_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Blog
        fields = [
            "id",
            "urid",
            "title",
            "slug",
            "author",
            "author_username",
            "cover_image",
            "meta_description",
            "read_time_minutes",
            "is_published",
            "published_at",
            "likes_count",
            "dislikes_count",
            "comments_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


# ===========================================================================
# Blog — Detail (full nested read)
# ===========================================================================

class BlogDetailSerializer(serializers.ModelSerializer):
    """
    Full blog payload returned on retrieve / get_full_blog.
    Includes ordered blocks and approved top-level comments with replies.
    """
    blocks = BlogBlockReadSerializer(many=True, read_only=True)
    comments = serializers.SerializerMethodField()
    author_username = serializers.CharField(source="author.username", read_only=True, default=None)
    likes_count = serializers.IntegerField(read_only=True)
    dislikes_count = serializers.IntegerField(read_only=True)
    comments_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Blog
        fields = [
            "id",
            "urid",
            "title",
            "slug",
            "author",
            "author_username",
            "cover_image",
            "meta_description",
            "read_time_minutes",
            "is_published",
            "published_at",
            "likes_count",
            "dislikes_count",
            "comments_count",
            "blocks",
            "comments",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_comments(self, obj):
        """
        Return only approved, non-deleted, top-level comments.
        Replies are nested inside each comment by BlogCommentSerializer.
        """
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
    """
    Handles Blog creation and updates including multipart block data.

    Block data is passed as indexed form fields:
        blocks[0][type]    = text
        blocks[0][order]   = 1
        blocks[0][content] = Hello world
        blocks[1][type]    = image
        blocks[1][order]   = 2
        blocks[1][image]   = <file>

    On update, all existing blocks are replaced (full-replace strategy).
    Partial block updates are handled at the application layer if needed.
    """

    class Meta:
        model = Blog
        fields = [
            "title",
            "slug",
            "author",
            "cover_image",
            "meta_description",
            "read_time_minutes",
            "is_published",
        ]
        extra_kwargs = {
            "slug": {"required": False},  # auto-generated from title if not provided
            "author": {"required": False},
        }

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate_title(self, value):
        if len(value.strip()) < 3:
            raise serializers.ValidationError("Title must be at least 3 characters.")
        return value.strip()

    def validate(self, attrs):
        # Auto-generate slug from title if not provided
        if not attrs.get("slug") and attrs.get("title"):
            attrs["slug"] = slugify(attrs["title"])
        return attrs

    # ------------------------------------------------------------------
    # Block parsing from raw request.data (multipart indexed fields)
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_blocks(request) -> list[dict]:
        """
        Parse indexed block fields from multipart request.data / request.FILES.

        Expected format:
            blocks[0][type]    = "text"
            blocks[0][order]   = "1"
            blocks[0][content] = "..."
            blocks[1][type]    = "image"
            blocks[1][image]   = <InMemoryUploadedFile>
            blocks[1][meta]    = '{"alt": "Hero shot"}'   (optional JSON string)
        """
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
                    pass  # ignore malformed meta silently

            blocks.append({
                "type": block_type,
                "order": int(order_raw),
                "content": content,
                "image": image,
                "meta": meta,
            })
            i += 1
        return blocks

    @staticmethod
    def _validate_and_create_blocks(blog, raw_blocks: list[dict]):
        """Validate each block dict and bulk-create."""
        serializers_list = [
            BlogBlockWriteSerializer(data=b) for b in raw_blocks
        ]
        # Validate all before writing any (atomic)
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

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    def create(self, validated_data):
        request = self.context["request"]

        # Inject author from authenticated user if not explicitly set
        if not validated_data.get("author") and request.user.is_authenticated:
            validated_data["author"] = request.user

        # Inject IP
        from core.mixins import get_client_ip
        ip = get_client_ip(request)
        validated_data["created_by_ip"] = ip
        validated_data["updated_by_ip"] = ip

        blog = Blog.objects.create(**validated_data)

        raw_blocks = self._parse_blocks(request)
        if raw_blocks:
            self._validate_and_create_blocks(blog, raw_blocks)

        return blog

    # ------------------------------------------------------------------
    # Update (full block replacement)
    # ------------------------------------------------------------------

    def update(self, instance, validated_data):
        request = self.context["request"]

        from core.mixins import get_client_ip
        validated_data["updated_by_ip"] = get_client_ip(request)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        raw_blocks = self._parse_blocks(request)
        if raw_blocks:
            # Full replacement — soft-delete existing, create new
            instance.blocks.filter(is_deleted=False).update(is_deleted=True)
            self._validate_and_create_blocks(instance, raw_blocks)

        return instance
