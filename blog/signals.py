"""
blog/signals.py
"""

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from .models import Blog, BlogBlock

# ===========================================================================
# 📖 AUTO-CALCULATE READ TIME
# ===========================================================================

@receiver(post_save, sender=BlogBlock)
def update_blog_read_time(sender, instance, **kwargs):
    """
    Recalculate blog read time whenever a block is created/updated.
    Logic:
    - Count words from text-like blocks
    - Avg reading speed = 200 words/min
    - Minimum = 1 minute
    """

    blog = instance.blog

    # Only active (non-deleted) blocks
    blocks = blog.blocks.filter(is_active=True)

    total_words = 0

    for block in blocks:
        if block.type in ("text", "quote", "code") and block.content:
            total_words += len(block.content.split())

    read_time = max(1, total_words // 200)

    # Avoid unnecessary DB write
    if blog.read_time_minutes != read_time:
        blog.read_time_minutes = read_time
        blog.save(update_fields=["read_time_minutes"])


# ===========================================================================
# 🕒 ENSURE PUBLISHED TIMESTAMP CONSISTENCY
# ===========================================================================

@receiver(post_save, sender=Blog)
def ensure_published_timestamp(sender, instance, created, **kwargs):
    """
    Safety fallback:
    Ensures published_at is always set when blog is marked as published.

    NOTE:
    Primary logic should remain in Blog.publish()
    This is just a guard.
    """

    if instance.is_published and not instance.published_at:
        instance.published_at = timezone.now()
        instance.save(update_fields=["published_at"])
