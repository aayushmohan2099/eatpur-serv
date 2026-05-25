"""
blog/models.py
"""

from django.db import models
from django.utils import timezone

from core.mixins import SoftDeleteMixin
from user.models import CustomUser


# ===========================================================================
# Blog
# ===========================================================================

class Blog(SoftDeleteMixin):
    title = models.CharField(max_length=255, db_index=True, verbose_name="Title")
    slug = models.SlugField(
        max_length=280, unique=True, db_index=True, verbose_name="URL Slug",
        help_text="Auto-generated from title. Never change after publishing.",
    )

    # Authorship
    author = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="blogs", db_index=True, verbose_name="Author",
    )
    # NEW: Store the name of the author if they created it without logging in
    guest_name = models.CharField(
        max_length=100, null=True, blank=True, verbose_name="Guest Author Name"
    )

    cover_image = models.ImageField(
        upload_to="blogs/covers/%Y/%m/", null=True, blank=True, verbose_name="Cover Image",
    )
    meta_description = models.CharField(
        max_length=160, blank=True, verbose_name="Meta Description",
        help_text="Used for search engine snippets. Max 160 characters.",
    )
    read_time_minutes = models.PositiveSmallIntegerField(
        default=1, verbose_name="Estimated Read Time (minutes)"
    )

    # Publishing
    is_published = models.BooleanField(default=False, db_index=True, verbose_name="Is Published")
    published_at = models.DateTimeField(null=True, blank=True, db_index=True, verbose_name="Published At")

    class Meta:
        db_table = "blog"
        verbose_name = "Blog"
        verbose_name_plural = "Blogs"
        ordering = ["-published_at", "-created_at"]
        indexes = [
            models.Index(fields=["slug"]),
            models.Index(fields=["author"]),
            models.Index(fields=["is_published", "published_at"]),
        ]

    def publish(self, ip: str | None = None):
        self.is_published = True
        if not self.published_at:
            self.published_at = timezone.now()
        if ip:
            self.updated_by_ip = ip
        self.save(update_fields=["is_published", "published_at", "updated_by_ip", "updated_at"])

    def unpublish(self, ip: str | None = None):
        self.is_published = False
        if ip:
            self.updated_by_ip = ip
        self.save(update_fields=["is_published", "updated_by_ip", "updated_at"])

    @property
    def likes_count(self) -> int:
        return self.reactions.filter(reaction_type="like", is_deleted=False).count()

    @property
    def dislikes_count(self) -> int:
        return self.reactions.filter(reaction_type="dislike", is_deleted=False).count()

    @property
    def comments_count(self) -> int:
        return self.comments.filter(is_deleted=False).count()

    def __str__(self):
        return f"[{'✓' if self.is_published else '✗'}] {self.title}"


# ===========================================================================
# BlogBlock
# ===========================================================================

class BlogBlock(SoftDeleteMixin):
    BLOCK_TYPES = (
        ("text", "Text / Markdown"),
        ("image", "Image"),
        ("video", "Video Embed"),
        ("quote", "Pull Quote"),
        ("code", "Code Snippet"),
    )

    blog = models.ForeignKey(Blog, on_delete=models.CASCADE, related_name="blocks", db_index=True)
    type = models.CharField(max_length=10, choices=BLOCK_TYPES, db_index=True)
    order = models.PositiveIntegerField()
    content = models.TextField(null=True, blank=True)
    image = models.ImageField(upload_to="blogs/blocks/%Y/%m/", null=True, blank=True)
    meta = models.JSONField(null=True, blank=True)

    class Meta:
        db_table = "blog_block"
        ordering = ["order"]
        unique_together = [("blog", "order")]
        indexes = [
            models.Index(fields=["blog", "order"]),
            models.Index(fields=["type"]),
        ]

    def __str__(self):
        return f"{self.blog.title} | Block #{self.order} [{self.type}]"


# ===========================================================================
# BlogReaction
# ===========================================================================

class BlogReaction(SoftDeleteMixin):
    REACTION_TYPES = (("like", "Like"), ("dislike", "Dislike"))

    blog = models.ForeignKey(Blog, on_delete=models.CASCADE, related_name="reactions", db_index=True)
    
    # REQUIRED: Only authenticated users can react
    user = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name="blog_reactions", db_index=True, default=None
    )
    reaction_type = models.CharField(max_length=10, choices=REACTION_TYPES, db_index=True)
    ip_address = models.GenericIPAddressField(db_index=True)

    class Meta:
        db_table = "blog_reaction"
        unique_together = [("blog", "user")]  # One reaction per user per blog
        indexes = [
            models.Index(fields=["blog", "reaction_type"]),
            models.Index(fields=["user"]),
        ]

    def __str__(self):
        return f"{self.reaction_type} on '{self.blog.title}' by {self.user.username}"


# ===========================================================================
# BlogComment
# ===========================================================================

class BlogComment(SoftDeleteMixin):
    blog = models.ForeignKey(Blog, on_delete=models.CASCADE, related_name="comments", db_index=True)
    
    # REQUIRED: Only authenticated users can comment
    user = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name="blog_comments", db_index=True, default=None
    )
    
    content = models.TextField()
    ip_address = models.GenericIPAddressField(db_index=True)

    is_approved = models.BooleanField(default=False, db_index=True)
    approved_at = models.DateTimeField(null=True, blank=True)

    parent = models.ForeignKey(
        "self", null=True, blank=True, related_name="replies",
        on_delete=models.CASCADE, db_index=True
    )

    class Meta:
        db_table = "blog_comment"
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["blog", "is_approved"]),
            models.Index(fields=["blog", "parent"]),
            models.Index(fields=["parent"]),
            models.Index(fields=["user"]),
        ]

    def approve(self, ip: str | None = None):
        self.is_approved = True
        self.approved_at = timezone.now()
        if ip:
            self.updated_by_ip = ip
        self.save(update_fields=["is_approved", "approved_at", "updated_by_ip", "updated_at"])

    @property
    def display_name(self) -> str:
        return self.user.username

    @property
    def is_reply(self) -> bool:
        return self.parent_id is not None

    def __str__(self):
        return f"{self.user.username} on '{self.blog.title}'"
    

# ===========================================================================
# BlogApproval
# ===========================================================================
class BlogApproval(SoftDeleteMixin):
    blog = models.ForeignKey(Blog, on_delete=models.DO_NOTHING, related_name="approval", db_index=True)
    approver = models.ForeignKey(CustomUser, on_delete=models.DO_NOTHING, related_name="blog_approval", db_index=True, null=True, blank=True, default=None)

    STATUS_CHOICES = [
        ("DRAFT", "Draft"),
        ("PENDING", "Pending for Approval"),
        ("APPROVED", "Approved"),
        ("REJECTED", "Rejected"),
    ]

    status = models.CharField(max_length=50, db_index=True, choices=STATUS_CHOICES, verbose_name="status_name")
    date_of_approval = models.DateTimeField(null=True, blank=True)

    date_of_rejection = models.DateField(null=True, blank=True)
    rejection_reason = models.CharField(max_length=250, null=True, blank=True)

    def save(self, *args, **kwargs):
        if self.status == "APPROVED" and not self.date_of_approval:
            self.date_of_approval = timezone.now()

        super().save(*args, **kwargs)

    class Meta:
        db_table = "blog_approval"
        ordering = ["date_of_approval"]
        indexes = [
            models.Index(fields=["blog", "date_of_approval"]),
            models.Index(fields=["blog", "status"]),
            models.Index(fields=["approver", "blog"])
        ]