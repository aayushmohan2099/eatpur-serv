# blog/signals.py

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import BlogReaction, BlogComment


@receiver(post_save, sender=BlogReaction)
def update_reaction_counts(sender, instance, **kwargs):
    blog = instance.blog

    likes = blog.reactions.filter(
        reaction_type='like',
        is_active=True
    ).count()

    dislikes = blog.reactions.filter(
        reaction_type='dislike',
        is_active=True
    ).count()

    blog.likes_count = likes
    blog.dislikes_count = dislikes
    blog.save(update_fields=['likes_count', 'dislikes_count'])


@receiver(post_save, sender=BlogComment)
def update_comment_count(sender, instance, created, **kwargs):
    blog = instance.blog
    count = blog.comments.filter(is_active=True).count()
    blog.comments_count = count
    blog.save(update_fields=['comments_count'])