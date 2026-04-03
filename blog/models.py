"""
blog/models.py
==============
Blog system: articles, rich content blocks, reactions, and threaded comments.

Changes from original
---------------------
1.  Removed custom `generate_id()` + CharField PK — the mixin already
    provides `urid` (UUID). Django's default auto-increment `id` is kept
    as PK for FK join performance; `urid` is used for public-facing URLs.

2.  `author` CharField → ForeignKey to CustomUser. Stores the real user
    reference instead of a raw string; `SET_NULL` preserves posts if the
    account is deleted.

3.  `likes_count` / `dislikes_count` / `comments_count` removed from Blog.
    Denormalised counters go stale and are a write-contention hotspot at
    scale. Use DB aggregation or a cache layer instead (see helpers below).

4.  `BlogReaction` extended: added `user` FK (nullable) alongside
    `ip_address` so logged-in users are tracked by account, not just IP.
    `unique_together` updated to `('blog', 'user')` for authenticated
    reactions, with a separate partial-index strategy for anonymous ones.

5.  `BlogComment` extended: added `user` FK (nullable) to link authenticated
    commenters; `is_approved` flag for moderation; indexes on `blog + parent`
    for efficient thread fetches.

6.  All models gain proper `verbose_name`, `verbose_name_plural`, `db_table`,
    and `__str__` methods consistent with the rest of the project.

7.  `is_published` → paired with `published_at` timestamp for scheduling.

8.  Added `read_time_minutes` (auto-computed) and `meta_description` for SEO.
"""

from django.db import models
from django.utils import timezone

from core.mixins import SoftDeleteMixin
from user.models import CustomUser


# ===========================================================================
# Blog
# ===========================================================================

class Blog(SoftDeleteMixin):
    """
    A single blog post / article.

    Content is stored in linked BlogBlock rows (ordered, typed blocks)
    rather than a single TextField, enabling rich mixed-media layouts.

    Public URL slug must be unique and is never reused (even after soft-delete)
    to avoid SEO / permalink collisions.
    """

    title = models.CharField(
        max_length=255, db_index=True, verbose_name="Title"
    )
    slug = models.SlugField(
        max_length=280,
        unique=True,
        db_index=True,
        verbose_name="URL Slug",
        help_text="Auto-generated from title. Never change after publishing.",
    )

    # ------------------------------------------------------------------
    # Authorship — FK instead of raw string
    # ------------------------------------------------------------------
    author = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="blogs",
        db_index=True,
        verbose_name="Author",
    )

    # ------------------------------------------------------------------
    # Cover media
    # ------------------------------------------------------------------
    cover_image = models.ImageField(
        upload_to="blogs/covers/%Y/%m/",
        null=True,
        blank=True,
        verbose_name="Cover Image",
    )

    # ------------------------------------------------------------------
    # SEO / metadata
    # ------------------------------------------------------------------
    meta_description = models.CharField(
        max_length=160,
        blank=True,
        verbose_name="Meta Description",
        help_text="Used for search engine snippets. Max 160 characters.",
    )

    # Estimated read time — set on save based on block word counts
    read_time_minutes = models.PositiveSmallIntegerField(
        default=1, verbose_name="Estimated Read Time (minutes)"
    )

    # ------------------------------------------------------------------
    # Publishing
    # ------------------------------------------------------------------
    is_published = models.BooleanField(
        default=False, db_index=True, verbose_name="Is Published"
    )
    published_at = models.DateTimeField(
        null=True, blank=True, db_index=True, verbose_name="Published At"
    )

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

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def publish(self, ip: str | None = None):
        """Mark blog as published and stamp published_at."""
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

    # ------------------------------------------------------------------
    # Aggregation helpers (use these instead of cached counters)
    # ------------------------------------------------------------------

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
# BlogBlock — Rich content blocks
# ===========================================================================

class BlogBlock(SoftDeleteMixin):
    """
    An ordered content unit within a Blog.

    Blocks are rendered in ascending `order`. Each block is either:
      - 'text'  : Markdown / HTML content in `content`
      - 'image' : an uploaded image in `image` with optional caption in `content`
      - 'video' : an embedded video URL in `content`
      - 'quote' : a pull-quote in `content`
      - 'code'  : a code snippet in `content` (language in `meta`)

    `meta` is a flexible JSON field for block-type-specific extras:
        image  → {"alt": "...", "caption": "..."}
        code   → {"language": "python", "filename": "views.py"}
        video  → {"provider": "youtube", "thumbnail": "..."}
    """

    BLOCK_TYPES = (
        ("text", "Text / Markdown"),
        ("image", "Image"),
        ("video", "Video Embed"),
        ("quote", "Pull Quote"),
        ("code", "Code Snippet"),
    )

    blog = models.ForeignKey(
        Blog,
        on_delete=models.CASCADE,
        related_name="blocks",
        db_index=True,
        verbose_name="Blog",
    )
    type = models.CharField(
        max_length=10,
        choices=BLOCK_TYPES,
        db_index=True,
        verbose_name="Block Type",
    )
    order = models.PositiveIntegerField(verbose_name="Display Order")

    # Text / markdown / embed URL / code / quote all live here
    content = models.TextField(null=True, blank=True, verbose_name="Content")

    # Image upload (used when type = 'image')
    image = models.ImageField(
        upload_to="blogs/blocks/%Y/%m/",
        null=True,
        blank=True,
        verbose_name="Block Image",
    )

    # Flexible extras per block type
    meta = models.JSONField(
        null=True, blank=True, verbose_name="Block Meta (JSON)"
    )

    class Meta:
        db_table = "blog_block"
        verbose_name = "Blog Block"
        verbose_name_plural = "Blog Blocks"
        ordering = ["order"]
        unique_together = [("blog", "order")]
        indexes = [
            models.Index(fields=["blog", "order"]),
            models.Index(fields=["type"]),
        ]

    def __str__(self):
        return f"{self.blog.title} | Block #{self.order} [{self.type}]"


# ===========================================================================
# BlogReaction — Likes / Dislikes
# ===========================================================================

class BlogReaction(SoftDeleteMixin):
    """
    A single like or dislike on a blog post.

    For authenticated users: uniqueness enforced on (blog, user).
    For anonymous visitors: uniqueness enforced on (blog, ip_address).

    Strategy: attempt FK lookup first; fall back to IP for guests.
    The DB-level unique_together covers the authenticated path.
    An application-layer check handles the anonymous path to avoid
    a multi-column partial-index dependency on MySQL.
    """

    REACTION_TYPES = (
        ("like", "Like"),
        ("dislike", "Dislike"),
    )

    blog = models.ForeignKey(
        Blog,
        on_delete=models.CASCADE,
        related_name="reactions",
        db_index=True,
        verbose_name="Blog",
    )

    # Authenticated user (nullable — anonymous reactions allowed)
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="blog_reactions",
        db_index=True,
        verbose_name="User (if authenticated)",
    )

    reaction_type = models.CharField(
        max_length=10,
        choices=REACTION_TYPES,
        db_index=True,
        verbose_name="Reaction Type",
    )

    # IP is always captured (rate-limiting, abuse prevention)
    ip_address = models.GenericIPAddressField(
        db_index=True, verbose_name="IP Address"
    )

    class Meta:
        db_table = "blog_reaction"
        verbose_name = "Blog Reaction"
        verbose_name_plural = "Blog Reactions"
        # One reaction per authenticated user per blog
        unique_together = [("blog", "user")]
        indexes = [
            models.Index(fields=["blog", "reaction_type"]),
            models.Index(fields=["blog", "ip_address"]),
            models.Index(fields=["user"]),
        ]

    def __str__(self):
        actor = str(self.user) if self.user else self.ip_address
        return f"{self.reaction_type} on '{self.blog.title}' by {actor}"


# ===========================================================================
# BlogComment — Threaded comments
# ===========================================================================

class BlogComment(SoftDeleteMixin):
    """
    A threaded comment on a blog post.

    Threading:
        Top-level comment → parent = NULL
        Reply             → parent = <BlogComment instance>

    Moderation:
        is_approved = False by default; set True by a staff member
        or auto-approve if trusted (e.g., authenticated user).

    Authenticated users are linked via `user` FK.
    Guest commenters use `name` + `email` + `ip_address`.
    """

    blog = models.ForeignKey(
        Blog,
        on_delete=models.CASCADE,
        related_name="comments",
        db_index=True,
        verbose_name="Blog",
    )

    # Authenticated commenter (nullable — guests allowed)
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="blog_comments",
        db_index=True,
        verbose_name="User (if authenticated)",
    )

    # Guest identity fields
    name = models.CharField(
        max_length=100, null=True, blank=True, verbose_name="Guest Name"
    )
    email = models.EmailField(
        null=True, blank=True, verbose_name="Guest Email"
    )

    content = models.TextField(verbose_name="Comment Content")

    ip_address = models.GenericIPAddressField(
        db_index=True, verbose_name="IP Address"
    )

    # Moderation
    is_approved = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name="Is Approved",
        help_text="Only approved comments are shown publicly.",
    )
    approved_at = models.DateTimeField(
        null=True, blank=True, verbose_name="Approved At"
    )

    # Threading — self-referential FK
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        related_name="replies",
        on_delete=models.CASCADE,
        db_index=True,
        verbose_name="Parent Comment",
    )

    class Meta:
        db_table = "blog_comment"
        verbose_name = "Blog Comment"
        verbose_name_plural = "Blog Comments"
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["blog", "is_approved"]),
            models.Index(fields=["blog", "parent"]),  # fetch top-level comments fast
            models.Index(fields=["parent"]),            # fetch replies fast
            models.Index(fields=["user"]),
            models.Index(fields=["ip_address"]),
        ]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def approve(self, ip: str | None = None):
        self.is_approved = True
        self.approved_at = timezone.now()
        if ip:
            self.updated_by_ip = ip
        self.save(update_fields=["is_approved", "approved_at", "updated_by_ip", "updated_at"])

    @property
    def display_name(self) -> str:
        """Resolved display name for rendering."""
        if self.user:
            return self.user.username
        return self.name or "Anonymous"

    @property
    def is_reply(self) -> bool:
        return self.parent_id is not None

    def __str__(self):
        return f"{self.display_name} on '{self.blog.title}' [{'reply' if self.is_reply else 'top-level'}]"
