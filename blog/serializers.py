# blog/serializers.py

from rest_framework import serializers
from .models import *

class BlogBlockReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = BlogBlock
        fields = ["id", "type", "order", "content", "image"]

class BlogDetailSerializer(serializers.ModelSerializer):
    blocks = BlogBlockReadSerializer(many=True, read_only=True)
    comments = serializers.SerializerMethodField()
    likes_count = serializers.SerializerMethodField()
    dislikes_count = serializers.SerializerMethodField()

    class Meta:
        model = Blog
        fields = "__all__"

    def get_comments(self, obj):
        comments = obj.comments.filter(
            is_active=True,
            parent__isnull=True  
        ).order_by('-created_at')
        return BlogCommentSerializer(comments, many=True).data             

    def get_likes_count(self, obj):
        return obj.reactions.filter(
            reaction_type='like',
            is_active=True
        ).count()

    def get_dislikes_count(self, obj):
        return obj.reactions.filter(
            reaction_type='dislike',
            is_active=True
        ).count()

class BlogBlockSerializer(serializers.ModelSerializer):
    class Meta:
        model = BlogBlock
        fields = "__all__"


class BlogSerializer(serializers.ModelSerializer):
    class Meta:
        model = Blog
        fields = "__all__"

    def create(self, validated_data):
        request = self.context.get('request')

        # ✅ Create Blog FIRST
        blog = Blog.objects.create(**validated_data)

        # ✅ Extract blocks manually
        i = 0
        while True:
            type_key = f'blocks[{i}][type]'
            if type_key not in request.data:
                break

            block_type = request.data.get(type_key)
            order = int(request.data.get(f'blocks[{i}][order]', i))

            content = request.data.get(f'blocks[{i}][content]')
            image = request.FILES.get(f'blocks[{i}][image]')

            BlogBlock.objects.create(
                blog=blog,
                type=block_type,
                order=order,
                content=content if block_type == "text" else None,
                image=image if block_type == "image" else None,
            )

            i += 1

        return blog
    
class BlogReactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = BlogReaction
        fields = "__all__"


class BlogCommentSerializer(serializers.ModelSerializer):
    replies = serializers.SerializerMethodField()

    class Meta:
        model = BlogComment
        fields = "__all__"

    def get_replies(self, obj):
        return BlogCommentSerializer(obj.replies.filter(is_active=True), many=True).data        