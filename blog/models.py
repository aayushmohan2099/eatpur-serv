# blog/models.py

import uuid
from django.db import models
from core.mixins import SoftDeleteMixin

def generate_id():
    return str(uuid.uuid4())

class Blog(SoftDeleteMixin):
    id = models.CharField(primary_key=True, max_length=36, default=generate_id, editable=False)
    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)

    author = models.CharField(max_length=100)

    cover_image = models.ImageField(upload_to="blogs/covers/", null=True, blank=True)

    is_published = models.BooleanField(default=False)

    likes_count = models.PositiveIntegerField(default=0)
    dislikes_count = models.PositiveIntegerField(default=0)
    comments_count = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.title


class BlogBlock(SoftDeleteMixin):
    BLOCK_TYPES = (
        ('text', 'Text'),
        ('image', 'Image'),
    )

    id = models.CharField(primary_key=True, max_length=36, default=generate_id, editable=False)

    blog = models.ForeignKey(Blog, related_name="blocks", on_delete=models.CASCADE)

    type = models.CharField(max_length=10, choices=BLOCK_TYPES)

    order = models.PositiveIntegerField()

    content = models.TextField(null=True, blank=True)

    image = models.ImageField(upload_to="blogs/blocks/", null=True, blank=True)

    class Meta:
        ordering = ['order']
        unique_together = ('blog', 'order')

    def __str__(self):
        return f"{self.blog.title} - {self.type} - {self.order}"

class BlogReaction(SoftDeleteMixin):
    REACTION_TYPES = (
        ('like', 'Like'),
        ('dislike', 'Dislike'),
    )

    id = models.CharField(primary_key=True, max_length=36, default=generate_id, editable=False)

    blog = models.ForeignKey(Blog, related_name="reactions", on_delete=models.CASCADE)

    reaction_type = models.CharField(max_length=10, choices=REACTION_TYPES)

    ip_address = models.GenericIPAddressField()

    class Meta:
        unique_together = ('blog', 'ip_address')      
        indexes = [
            models.Index(fields=['blog', 'reaction_type']),
        ]          

class BlogComment(SoftDeleteMixin):
    id = models.CharField(primary_key=True, max_length=36, default=generate_id, editable=False)

    blog = models.ForeignKey(Blog, related_name="comments", on_delete=models.CASCADE)

    name = models.CharField(max_length=100, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)

    content = models.TextField()

    ip_address = models.GenericIPAddressField()

    # Optional threading (reply system)
    parent = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        related_name='replies',
        on_delete=models.CASCADE
    )

    def __str__(self):
        return f"{self.name or 'Anonymous'} - {self.blog.title}"                