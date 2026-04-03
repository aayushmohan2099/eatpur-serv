"""
blog/admin.py
=============

Admin configuration for Blog system.
Optimized for:
- Content editing (blocks inline)
- Moderation (comments)
- Performance (query optimizations)
"""

from django.contrib import admin
from django.utils.html import format_html

from .models import Blog, BlogBlock, BlogReaction, BlogComment


# ============================================================================
# Inline: BlogBlock (Content Builder)
# ============================================================================

class BlogBlockInline(admin.TabularInline):
    model = BlogBlock
    extra = 1
    ordering = ("order",)
    fields = ("order", "type", "content", "image", "meta")
    show_change_link = True


# ============================================================================
# Inline: Comments (Moderation)
# ============================================================================

class BlogCommentInline(admin.TabularInline):
    model = BlogComment
    extra = 0
    fields = ("display_name", "content", "is_approved", "created_at")
    readonly_fields = ("display_name", "content", "created_at")
    can_delete = False
    show_change_link = True

    def display_name(self, obj):
        return obj.display_name


# ============================================================================
# Blog Admin
# ============================================================================

@admin.register(Blog)
class BlogAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "author",
        "is_published",
        "published_at",
        "read_time_minutes",
        "likes_count_display",
        "comments_count_display",
        "created_at",
    )

    list_filter = (
        "is_published",
        "published_at",
        "created_at",
        "author",
    )

    search_fields = ("title", "slug", "meta_description")

    prepopulated_fields = {"slug": ("title",)}

    readonly_fields = (
        "created_at",
        "updated_at",
        "likes_count_display",
        "comments_count_display",
    )

    autocomplete_fields = ("author",)

    inlines = [BlogBlockInline, BlogCommentInline]

    list_select_related = ("author",)

    date_hierarchy = "published_at"

    ordering = ("-published_at",)

    # ------------------------------------------------------------------
    # Custom display fields
    # ------------------------------------------------------------------

    def likes_count_display(self, obj):
        return obj.likes_count
    likes_count_display.short_description = "👍 Likes"

    def comments_count_display(self, obj):
        return obj.comments_count
    comments_count_display.short_description = "💬 Comments"

    # ------------------------------------------------------------------
    # Bulk actions
    # ------------------------------------------------------------------

    actions = ["publish_selected", "unpublish_selected"]

    def publish_selected(self, request, queryset):
        for blog in queryset:
            blog.publish()
    publish_selected.short_description = "Publish selected blogs"

    def unpublish_selected(self, request, queryset):
        queryset.update(is_published=False)
    unpublish_selected.short_description = "Unpublish selected blogs"


# ============================================================================
# BlogBlock Admin (Standalone)
# ============================================================================

@admin.register(BlogBlock)
class BlogBlockAdmin(admin.ModelAdmin):
    list_display = ("blog", "order", "type")
    list_filter = ("type",)
    search_fields = ("blog__title", "content")
    ordering = ("blog", "order")

    autocomplete_fields = ("blog",)


# ============================================================================
# BlogReaction Admin (Read-heavy → restrict edits)
# ============================================================================

@admin.register(BlogReaction)
class BlogReactionAdmin(admin.ModelAdmin):
    list_display = ("blog", "user", "reaction_type", "ip_address", "created_at")
    list_filter = ("reaction_type", "created_at")
    search_fields = ("blog__title", "user__username", "ip_address")

    autocomplete_fields = ("blog", "user")

    readonly_fields = (
        "blog",
        "user",
        "reaction_type",
        "ip_address",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


# ============================================================================
# BlogComment Admin (Moderation Panel)
# ============================================================================

@admin.register(BlogComment)
class BlogCommentAdmin(admin.ModelAdmin):
    list_display = (
        "blog",
        "display_name",
        "short_content",
        "is_approved",
        "created_at",
    )

    list_filter = ("is_approved", "created_at")

    search_fields = (
        "blog__title",
        "content",
        "name",
        "email",
        "user__username",
    )

    autocomplete_fields = ("blog", "user", "parent")

    readonly_fields = ("created_at", "updated_at", "approved_at")

    actions = ["approve_comments"]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def short_content(self, obj):
        return obj.content[:50] + "..."
    short_content.short_description = "Comment"

    def approve_comments(self, request, queryset):
        for comment in queryset:
            comment.approve()
    approve_comments.short_description = "Approve selected comments"