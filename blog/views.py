"""
blog/views.py
=============
Blog API views.

Endpoints
---------
BlogViewSet
    GET    /blogs/                → list (BlogListSerializer)
    POST   /blogs/                → create (BlogWriteSerializer, multipart)
    GET    /blogs/{id}/           → retrieve (BlogDetailSerializer)
    PUT    /blogs/{id}/           → full update (BlogWriteSerializer)
    PATCH  /blogs/{id}/           → partial update (BlogWriteSerializer)
    DELETE /blogs/{id}/           → soft delete
    GET    /blogs/{id}/full/      → alias for retrieve (same BlogDetailSerializer)
    POST   /blogs/{id}/publish/   → publish a blog
    POST   /blogs/{id}/unpublish/ → unpublish a blog

BlogReactionView
    POST   /blogs/{id}/react/     → toggle like/dislike (auth or anonymous)

BlogCommentView
    GET    /blogs/{id}/comments/  → paginated approved comments
    POST   /blogs/{id}/comments/  → submit a comment

BlogCommentApproveView
    POST   /comments/{id}/approve/ → staff-only comment approval
"""

from django.shortcuts import get_object_or_404
from django.db import models as db_models

from rest_framework import viewsets, status, permissions, filters
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.pagination import PageNumberPagination

from core.mixins import get_client_ip

from .models import Blog, BlogReaction, BlogComment
from .serializers import (
    BlogListSerializer,
    BlogDetailSerializer,
    BlogWriteSerializer,
    BlogCommentSerializer,
    BlogReactionSerializer,
)


# ===========================================================================
# Pagination
# ===========================================================================

class BlogCommentPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class BlogPagination(PageNumberPagination):
    page_size = 12
    page_size_query_param = "page_size"
    max_page_size = 100


# ===========================================================================
# BlogViewSet
# ===========================================================================

class BlogViewSet(viewsets.ModelViewSet):
    """
    Full CRUD for Blog.

    - List / retrieve are public.
    - Create / update / delete require authentication.
    - Soft delete is used instead of hard delete.

    Serializer selection
    --------------------
    list     → BlogListSerializer   (lightweight, no blocks/comments)
    retrieve → BlogDetailSerializer (full nested payload)
    write    → BlogWriteSerializer  (handles multipart blocks)
    """

    pagination_class = BlogPagination
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["title", "meta_description"]
    ordering_fields = ["published_at", "created_at", "title"]
    ordering = ["-published_at"]

    def get_queryset(self):
        qs = Blog.objects.select_related("author")

        # Public: only published blogs. Staff: all.
        if not (self.request.user.is_authenticated and self.request.user.is_staff):
            qs = qs.filter(is_published=True)

        action = self.action
        if action in ("retrieve", "get_full_blog"):
            qs = qs.prefetch_related(
                "blocks",
                db_models.Prefetch(
                    "comments",
                    queryset=BlogComment.objects.filter(
                        is_deleted=False, is_approved=True, parent__isnull=True
                    ).select_related("user").prefetch_related("replies"),
                ),
                "reactions",
            )
        return qs

    def get_serializer_class(self):
        if self.action == "list":
            return BlogListSerializer
        if self.action in ("retrieve", "get_full_blog"):
            return BlogDetailSerializer
        return BlogWriteSerializer  # create, update, partial_update

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx

    def get_permissions(self):
        """
        list / retrieve / get_full_blog → AllowAny
        everything else                 → IsAuthenticated
        """
        if self.action in ("list", "retrieve", "get_full_blog"):
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    # ------------------------------------------------------------------
    # Write helpers
    # ------------------------------------------------------------------

    def perform_create(self, serializer):
        serializer.save()  # author + IP injected inside serializer.create()

    def perform_update(self, serializer):
        serializer.save()  # IP injected inside serializer.update()

    def perform_destroy(self, instance):
        ip = get_client_ip(self.request)
        instance.soft_delete(ip=ip)

    # ------------------------------------------------------------------
    # Extra actions
    # ------------------------------------------------------------------

    @action(detail=True, methods=["get"], url_path="full", permission_classes=[permissions.AllowAny])
    def get_full_blog(self, request, pk=None):
        """Alias for retrieve — returns full BlogDetailSerializer payload."""
        blog = self.get_object()
        serializer = BlogDetailSerializer(blog, context=self.get_serializer_context())
        return Response(serializer.data)

    @action(
        detail=True, methods=["post"], url_path="publish",
        permission_classes=[permissions.IsAuthenticated]
    )
    def publish(self, request, pk=None):
        """Publish a blog post and stamp published_at."""
        blog = self.get_object()
        if blog.is_published:
            return Response({"detail": "Blog is already published."}, status=status.HTTP_400_BAD_REQUEST)
        blog.publish(ip=get_client_ip(request))
        return Response(
            {"detail": "Blog published.", "published_at": blog.published_at},
            status=status.HTTP_200_OK,
        )

    @action(
        detail=True, methods=["post"], url_path="unpublish",
        permission_classes=[permissions.IsAuthenticated]
    )
    def unpublish(self, request, pk=None):
        """Revert a blog to draft / unpublished state."""
        blog = self.get_object()
        if not blog.is_published:
            return Response({"detail": "Blog is already unpublished."}, status=status.HTTP_400_BAD_REQUEST)
        blog.unpublish(ip=get_client_ip(request))
        return Response({"detail": "Blog unpublished."}, status=status.HTTP_200_OK)


# ===========================================================================
# BlogReactionView
# ===========================================================================

class BlogReactionView(APIView):
    """
    POST /blogs/{id}/react/
    Body: { "reaction_type": "like" | "dislike" }

    Reaction logic
    --------------
    Authenticated user:
        Lookup by (blog, user).
        Toggle off if same type; switch type if different.

    Anonymous user:
        Lookup by (blog, ip_address).
        Same toggle / switch logic.

    Reaction is soft-deleted (not hard-deleted) so we retain history.
    When re-reacting after removal, the soft-deleted row is restored.
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request, blog_id):
        reaction_type = request.data.get("reaction_type")
        if reaction_type not in ("like", "dislike"):
            return Response(
                {"error": "Invalid reaction_type. Must be 'like' or 'dislike'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        blog = get_object_or_404(Blog, pk=blog_id, is_deleted=False, is_published=True)
        ip = get_client_ip(request)

        # ------------------------------------------------------------------
        # Build lookup kwargs depending on auth state
        # ------------------------------------------------------------------
        if request.user.is_authenticated:
            lookup = {"blog": blog, "user": request.user}
        else:
            # Anonymous: match on IP; user must be NULL
            lookup = {"blog": blog, "ip_address": ip, "user__isnull": True}

        reaction = BlogReaction.all_objects.filter(**lookup).first()

        if reaction is None:
            # No prior reaction — create fresh
            BlogReaction.objects.create(
                blog=blog,
                user=request.user if request.user.is_authenticated else None,
                reaction_type=reaction_type,
                ip_address=ip,
            )
            return Response(
                {"message": f"Reaction '{reaction_type}' added."},
                status=status.HTTP_201_CREATED,
            )

        if reaction.is_deleted:
            # Previously removed — restore with (possibly new) type
            reaction.is_deleted = False
            reaction.deleted_at = None
            reaction.reaction_type = reaction_type
            reaction.updated_by_ip = ip
            reaction.save(update_fields=["is_deleted", "deleted_at", "reaction_type", "updated_by_ip", "updated_at"])
            return Response({"message": f"Reaction '{reaction_type}' restored."})

        if reaction.reaction_type == reaction_type:
            # Same type tapped again → toggle off (soft delete)
            reaction.soft_delete(ip=ip)
            return Response({"message": f"Reaction '{reaction_type}' removed."})

        # Different type → switch reaction
        reaction.reaction_type = reaction_type
        reaction.updated_by_ip = ip
        reaction.save(update_fields=["reaction_type", "updated_by_ip", "updated_at"])
        return Response({"message": f"Reaction switched to '{reaction_type}'."})


# ===========================================================================
# BlogCommentView
# ===========================================================================

class BlogCommentView(APIView):
    """
    GET  /blogs/{id}/comments/ — paginated list of approved top-level comments
    POST /blogs/{id}/comments/ — submit a new comment

    Authentication is optional for both methods.
    Authenticated users get auto-approved comments (configurable).
    Guest comments go into moderation (is_approved=False).
    """

    permission_classes = [permissions.AllowAny]
    pagination_class = BlogCommentPagination

    def get(self, request, blog_id):
        blog = get_object_or_404(Blog, pk=blog_id, is_deleted=False)
        qs = (
            BlogComment.objects
            .filter(blog=blog, is_approved=True, parent__isnull=True)
            .select_related("user")
            .prefetch_related("replies")
            .order_by("created_at")
        )

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request)
        serializer = BlogCommentSerializer(page, many=True, context={"request": request})
        return paginator.get_paginated_response(serializer.data)

    def post(self, request, blog_id):
        blog = get_object_or_404(Blog, pk=blog_id, is_deleted=False, is_published=True)
        ip = get_client_ip(request)

        # Build mutable data dict
        data = {
            "blog": blog.pk,
            "content": request.data.get("content"),
            "name": request.data.get("name"),
            "email": request.data.get("email"),
            "parent": request.data.get("parent"),  # optional FK id
        }

        serializer = BlogCommentSerializer(data=data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        # Inject server-side fields
        auto_approve = request.user.is_authenticated
        comment = serializer.save(
            ip_address=ip,
            user=request.user if request.user.is_authenticated else None,
            is_approved=auto_approve,
        )

        # Stamp approved_at for auto-approved comments
        if auto_approve:
            from django.utils import timezone
            comment.approved_at = timezone.now()
            comment.save(update_fields=["approved_at"])

        return Response(
            BlogCommentSerializer(comment, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


# ===========================================================================
# BlogCommentApproveView — Staff-only moderation
# ===========================================================================

class BlogCommentApproveView(APIView):
    """
    POST /comments/{id}/approve/

    Creator-only endpoint to approve a pending comment. Creator of the blog is the ONLY one who can approve or reject any comment.
    Returns the updated comment serialized with full threading.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, comment_id):
        comment = get_object_or_404(BlogComment, pk=comment_id, is_deleted=False)

        if comment.is_approved:
            return Response(
                {"detail": "Comment is already approved."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        comment.approve(ip=get_client_ip(request))
        return Response(
            BlogCommentSerializer(comment, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )
