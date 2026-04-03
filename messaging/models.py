"""
messages/models.py
==================
Modular messaging system with strict separation of concerns.

Architecture
------------
MessageAuth   → metadata only (sender, receiver, status, timing)
MessageBody   → heavy content (text, image, file) — 1-to-1 with MessageAuth
Inbox         → per-user routing (maps a message to a user + inbox type)
InboxType     → SENT / RECEIVED / DRAFT
MessageStatus → DRAFT / PENDING / SENT / FAILED / READ

This design lets us:
* Query inbox without loading message content (MessageBody is a JOIN away).
* Support multi-recipient messaging without duplicating content.
* Efficiently filter by sender/receiver independently.
"""

from django.db import models

from core.mixins import SoftDeleteMixin
from user.models import CustomUser


# ===========================================================================
# LOOKUP: InboxType
# ===========================================================================

class InboxType(SoftDeleteMixin):
    """
    Defines how a message appears in a user's inbox.
    Examples: SENT, RECEIVED, DRAFT
    """

    TYPE_CHOICES = [
        ("SENT", "Sent"),
        ("RECEIVED", "Received"),
        ("DRAFT", "Draft"),
    ]

    type_name = models.CharField(
        max_length=20,
        unique=True,
        choices=TYPE_CHOICES,
        verbose_name="Inbox Type",
    )

    class Meta:
        db_table = "inbox_types"
        verbose_name = "Inbox Type"
        verbose_name_plural = "Inbox Types"

    def __str__(self):
        return self.type_name


# ===========================================================================
# LOOKUP: MessageStatus
# ===========================================================================

class MessageStatus(SoftDeleteMixin):
    """
    Lifecycle status of a message.
    Examples: DRAFT, PENDING, SENT, FAILED, READ
    """

    STATUS_CHOICES = [
        ("DRAFT", "Draft"),
        ("PENDING", "Pending"),
        ("SENT", "Sent"),
        ("FAILED", "Failed"),
        ("READ", "Read"),
    ]

    status_name = models.CharField(
        max_length=20,
        unique=True,
        choices=STATUS_CHOICES,
        verbose_name="Status Name",
    )

    class Meta:
        db_table = "message_status"
        verbose_name = "Message Status"
        verbose_name_plural = "Message Statuses"

    def __str__(self):
        return self.status_name


# ===========================================================================
# MessageAuth — Core message metadata
# ===========================================================================

class MessageAuth(SoftDeleteMixin):
    """
    Stores immutable message metadata: who sent it, to whom, and when.

    Intentionally separated from MessageBody to allow lightweight queries
    on the message graph (e.g., "how many unread messages does user X have?")
    without loading TEXT/file content.
    """

    sender = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="sent_messages",
        db_index=True,
        verbose_name="Sender",
    )
    receiver = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="received_messages",
        db_index=True,
        verbose_name="Receiver",
    )
    message_status = models.ForeignKey(
        MessageStatus,
        on_delete=models.SET_NULL,
        null=True,
        related_name="messages",
        db_index=True,
        verbose_name="Message Status",
    )
    sent_at = models.DateTimeField(
        null=True, blank=True, db_index=True, verbose_name="Sent At"
    )

    class Meta:
        db_table = "message_auth"
        verbose_name = "Message Auth"
        verbose_name_plural = "Message Auths"
        indexes = [
            models.Index(fields=["sender"]),
            models.Index(fields=["receiver"]),
            models.Index(fields=["sent_at"]),
            models.Index(fields=["message_status"]),
            # Composite: quickly fetch conversation between two users
            models.Index(fields=["sender", "receiver"]),
        ]

    def __str__(self):
        return f"Msg#{self.pk}: {self.sender} → {self.receiver} [{self.message_status}]"


# ===========================================================================
# MessageBody — Heavy content (1-to-1 with MessageAuth)
# ===========================================================================

class MessageBody(SoftDeleteMixin):
    """
    Stores the actual content of a message.

    1-to-1 with MessageAuth so content can be lazy-loaded.
    Supports text-only, image-only, file-only, or mixed messages.
    """

    message_auth = models.OneToOneField(
        MessageAuth,
        on_delete=models.CASCADE,
        related_name="body",
        db_index=True,
        verbose_name="Message Auth",
    )
    text_content = models.TextField(blank=True, verbose_name="Text Content")
    image = models.ImageField(
        upload_to="messages/images/%Y/%m/",
        null=True, blank=True,
        verbose_name="Attached Image",
    )
    file = models.FileField(
        upload_to="messages/files/%Y/%m/",
        null=True, blank=True,
        verbose_name="Attached File",
    )

    class Meta:
        db_table = "message_body"
        verbose_name = "Message Body"
        verbose_name_plural = "Message Bodies"

    def __str__(self):
        preview = self.text_content[:40] + "…" if self.text_content else "[media only]"
        return f"Body[{self.message_auth_id}]: {preview}"


# ===========================================================================
# Inbox — Per-user message routing
# ===========================================================================

class Inbox(SoftDeleteMixin):
    """
    Maps a MessageAuth record to a specific user with an inbox classification.

    For each message sent from A → B:
      - One Inbox row for A  (inbox_type = SENT)
      - One Inbox row for B  (inbox_type = RECEIVED)

    This allows each user to independently delete, archive, or label messages
    without affecting the other party's view.
    """

    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="inbox_entries",
        db_index=True,
        verbose_name="User",
    )
    message_auth = models.ForeignKey(
        MessageAuth,
        on_delete=models.CASCADE,
        related_name="inbox_entries",
        db_index=True,
        verbose_name="Message",
    )
    inbox_type = models.ForeignKey(
        InboxType,
        on_delete=models.SET_NULL,
        null=True,
        related_name="inbox_entries",
        db_index=True,
        verbose_name="Inbox Type",
    )

    class Meta:
        db_table = "inbox"
        verbose_name = "Inbox Entry"
        verbose_name_plural = "Inbox Entries"
        # A user should not see the same message twice in the same inbox type
        unique_together = [("user", "message_auth", "inbox_type")]
        indexes = [
            models.Index(fields=["user", "inbox_type"]),
            models.Index(fields=["message_auth"]),
        ]

    def __str__(self):
        return f"Inbox[{self.user}] — {self.inbox_type} — Msg#{self.message_auth_id}"
