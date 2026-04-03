"""
messages/admin.py
=================

Admin for Messaging System
Optimized for:
- Moderation & debugging
- Fast querying (no heavy joins unless needed)
- Read-only safety for message integrity
"""

from django.contrib import admin
from django.utils.html import format_html

from .models import (
    InboxType,
    MessageStatus,
    MessageAuth,
    MessageBody,
    Inbox,
)


# ============================================================================
# Inline: MessageBody (content)
# ============================================================================

class MessageBodyInline(admin.StackedInline):
    model = MessageBody
    extra = 0
    readonly_fields = ("text_preview", "image_preview", "file")

    def text_preview(self, obj):
        if obj.text_content:
            return obj.text_content[:200]
        return "-"
    text_preview.short_description = "Text"

    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="120" />', obj.image.url)
        return "-"
    image_preview.short_description = "Image"


# ============================================================================
# MessageAuth (CORE VIEW)
# ============================================================================

@admin.register(MessageAuth)
class MessageAuthAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "sender",
        "receiver",
        "message_status",
        "sent_at",
        "short_message",
    )

    list_filter = (
        "message_status",
        "sent_at",
    )

    search_fields = (
        "sender__username",
        "receiver__username",
        "body__text_content",
    )

    autocomplete_fields = ("sender", "receiver", "message_status")

    readonly_fields = ("sent_at", "created_at", "updated_at")

    inlines = [MessageBodyInline]

    list_select_related = ("sender", "receiver", "message_status")

    ordering = ("-sent_at",)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def short_message(self, obj):
        if hasattr(obj, "body") and obj.body.text_content:
            return obj.body.text_content[:50] + "..."
        return "[media]"
    short_message.short_description = "Message Preview"


# ============================================================================
# MessageBody (Standalone)
# ============================================================================

@admin.register(MessageBody)
class MessageBodyAdmin(admin.ModelAdmin):
    list_display = ("message_auth", "text_preview", "has_media")

    search_fields = ("text_content", "message_auth__sender__username")

    autocomplete_fields = ("message_auth",)

    readonly_fields = ("image_preview", "file")

    def text_preview(self, obj):
        return obj.text_content[:80] if obj.text_content else "-"
    text_preview.short_description = "Text"

    def has_media(self, obj):
        return bool(obj.image or obj.file)
    has_media.boolean = True
    has_media.short_description = "Media"

    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="120" />', obj.image.url)
        return "-"


# ============================================================================
# Inbox (User Routing View)
# ============================================================================

@admin.register(Inbox)
class InboxAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "message_auth",
        "inbox_type",
        "message_status",
        "sent_at",
    )

    list_filter = (
        "inbox_type",
        "message_auth__message_status",
    )

    search_fields = (
        "user__username",
        "message_auth__sender__username",
        "message_auth__receiver__username",
    )

    autocomplete_fields = ("user", "message_auth", "inbox_type")

    list_select_related = ("user", "message_auth", "inbox_type")

    ordering = ("-created_at",)

    # ------------------------------------------------------------------
    # Proxy fields (avoid extra queries)
    # ------------------------------------------------------------------

    def message_status(self, obj):
        return obj.message_auth.message_status
    message_status.short_description = "Status"

    def sent_at(self, obj):
        return obj.message_auth.sent_at
    sent_at.short_description = "Sent At"


# ============================================================================
# Lookup: InboxType
# ============================================================================

@admin.register(InboxType)
class InboxTypeAdmin(admin.ModelAdmin):
    list_display = ("type_name",)
    search_fields = ("type_name",)


# ============================================================================
# Lookup: MessageStatus
# ============================================================================

@admin.register(MessageStatus)
class MessageStatusAdmin(admin.ModelAdmin):
    list_display = ("status_name",)
    search_fields = ("status_name",)