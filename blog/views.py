# blog/views.py

from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import *
from .serializers import *
from core.mixins import get_client_ip
from django.shortcuts import get_object_or_404
from rest_framework.parsers import MultiPartParser, FormParser

class BlogViewSet(viewsets.ModelViewSet):
    queryset = Blog.objects.all().order_by('-created_at').prefetch_related(
        'blocks',
        'comments',
        'comments__replies',
        'reactions'
    )
    serializer_class = BlogSerializer
    parser_classes = (MultiPartParser, FormParser)

    def get_serializer_context(self):
        return {'request': self.request}

    def get_serializer_class(self):
        if self.action in ['retrieve', 'get_full_blog']:
            return BlogDetailSerializer
        return BlogSerializer

    def perform_create(self, serializer):
        instance = serializer.save()
        instance.save(request=self.request)

    def perform_update(self, serializer):
        instance = serializer.save()
        instance.save(request=self.request)

    def perform_destroy(self, instance):
        instance.soft_delete(request=self.request)

    @action(detail=True, methods=['get'], url_path='full')
    def get_full_blog(self, request, pk=None):
        blog = self.get_object()
        serializer = BlogDetailSerializer(blog)
        return Response(serializer.data)   

class BlogReactionView(APIView):

    def post(self, request, blog_id):
        ip = get_client_ip(request)
        reaction_type = request.data.get("reaction_type")
        if reaction_type not in ['like', 'dislike']:
            return Response({"error": "Invalid reaction"}, status=400)

        blog = get_object_or_404(Blog, id=blog_id)

        reaction, created = BlogReaction.all_objects.get_or_create(
            blog=blog,
            ip_address=ip,
            defaults={'reaction_type': reaction_type}
        )

        if not created:
            if reaction.reaction_type == reaction_type:
                reaction.soft_delete(request)
                return Response({"message": "Reaction removed"})
            else:
                reaction.reaction_type = reaction_type
                reaction.is_active = True
                reaction.save()

        return Response({"message": "Reaction updated"})        
    
class BlogCommentView(APIView):

    def post(self, request, blog_id):
        ip = get_client_ip(request)

        data = request.data.copy()
        data['blog'] = blog_id
        data['ip_address'] = ip

        serializer = BlogCommentSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data, status=status.HTTP_201_CREATED)    