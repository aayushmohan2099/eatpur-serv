"""
blog/views.py
"""

from django.shortcuts import get_object_or_404
from django.db import models as db_models
from rest_framework import viewsets, status, permissions, filters, generics
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.pagination import PageNumberPagination
from django.db.models import OuterRef, Subquery, Q, Count, Sum, IntegerField
from django.db.models.functions import Coalesce
from django.utils import timezone
from datetime import timedelta

from core.mixins import get_client_ip
from user.models import CustomUser
from .models import *
from .serializers import *

class BlogCommentPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100

class BlogPagination(PageNumberPagination):
    page_size = 12
    page_size_query_param = "page_size"
    max_page_size = 100

# ===========================================================================
# BlogViewSet
# ===========================================================================

class BlogViewSet(viewsets.ModelViewSet):
    pagination_class = BlogPagination
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["title", "meta_description", "guest_name", "author__username"]
    ordering_fields = ["published_at", "created_at", "title"]
    ordering = ["-published_at"]

    def get_queryset(self):
        # 1. Prepare a subquery to get the MOST RECENT status for each blog
        latest_approval = BlogApproval.objects.filter(
            blog=OuterRef('pk')
        ).order_by('-pk')  # Using -pk guarantees the chronologically latest record

        qs = Blog.objects.select_related("author").prefetch_related("approval")
        
        # 2. Annotate every blog with its current (latest) approval status
        qs = qs.annotate(
            current_approval_status=Subquery(latest_approval.values('status')[:1])
        )

        # 3. Apply filters based on user role
        if not (self.request.user.is_authenticated and self.request.user.is_staff):
            # Normal users ONLY see currently APPROVED and published blogs
            qs = qs.filter(is_published=True, current_approval_status="APPROVED")
        else:
            # Staff users can filter via query param: ?approval_status=PENDING
            approval_status_param = self.request.query_params.get('approval_status')
            
            if approval_status_param:
                approval_status_param = approval_status_param.upper()
                
                if approval_status_param == "DRAFT":
                    # Handle DRAFT or edge cases where no approval record exists yet
                    qs = qs.filter(
                        Q(current_approval_status="DRAFT") | 
                        Q(current_approval_status__isnull=True)
                    )
                else:
                    qs = qs.filter(current_approval_status=approval_status_param)

        # 4. Handle optimizations for detail views
        action = self.action
        if action in ("retrieve", "get_full_blog"):
            qs = qs.prefetch_related(
                "blocks",
                db_models.Prefetch(
                    "comments",
                    queryset=BlogComment.objects.filter(
                        is_deleted=False, is_approved=True, parent__isnull=True
                    ).select_related("user").prefetch_related("replies"),
                ),
                "reactions",
            )
        return qs

    def get_serializer_class(self):
        if self.action == "list":
            return BlogListSerializer
        if self.action in ("retrieve", "get_full_blog"):
            return BlogDetailSerializer
        return BlogWriteSerializer

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx

    def get_permissions(self):
        # AllowAny can List AND Retrieve blogs
        if self.action in ("list", "retrieve", "get_full_blog"):
            return [permissions.AllowAny()]
        # Creating, Updating, deleting, publishing require auth
        return [permissions.IsAuthenticated()]

    def perform_create(self, serializer):
        blog_instance = serializer.save()

        BlogApproval.objects.create(
            blog=blog_instance,
            status="PENDING"
        )

    def perform_update(self, serializer):
        serializer.save()

    def perform_destroy(self, instance):
        ip = get_client_ip(self.request)
        instance.soft_delete(ip=ip)

    @action(detail=True, methods=["get"], url_path="full", permission_classes=[permissions.AllowAny])
    def get_full_blog(self, request, pk=None):
        blog = self.get_object()
        serializer = BlogDetailSerializer(blog, context=self.get_serializer_context())
        return Response(serializer.data)

    @action(detail=True, methods=["post"], url_path="publish", permission_classes=[permissions.IsAuthenticated])
    def publish(self, request, pk=None):
        blog = self.get_object()
        if blog.is_published:
            return Response({"detail": "Already published."}, status=status.HTTP_400_BAD_REQUEST)
        blog.publish(ip=get_client_ip(request))
        return Response({"detail": "Published.", "published_at": blog.published_at}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="unpublish", permission_classes=[permissions.IsAuthenticated])
    def unpublish(self, request, pk=None):
        blog = self.get_object()
        if not blog.is_published:
            return Response({"detail": "Already unpublished."}, status=status.HTTP_400_BAD_REQUEST)
        blog.unpublish(ip=get_client_ip(request))
        return Response({"detail": "Unpublished."}, status=status.HTTP_200_OK)


# ===========================================================================
# BlogReactionView (STRICT AUTH)
# ===========================================================================

class BlogReactionView(APIView):

    def get_permissions(self):
        # Anyone can GET Reactions, but POST requires Auth
        if self.request.method == 'GET':
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def post(self, request, blog_id):
        reaction_type = request.data.get("reaction_type")
        if reaction_type not in ("like", "dislike"):
            return Response({"error": "Invalid reaction_type."}, status=status.HTTP_400_BAD_REQUEST)

        blog = get_object_or_404(Blog, pk=blog_id, is_deleted=False, is_published=True)
        ip = get_client_ip(request)

        # Lookup by exact authenticated user
        reaction = BlogReaction.all_objects.filter(blog=blog, user=request.user).first()

        if reaction is None:
            BlogReaction.objects.create(
                blog=blog, user=request.user, reaction_type=reaction_type, ip_address=ip
            )
            return Response({"message": f"Reaction '{reaction_type}' added."}, status=status.HTTP_201_CREATED)

        if reaction.is_deleted:
            reaction.is_deleted = False
            reaction.deleted_at = None
            reaction.reaction_type = reaction_type
            reaction.updated_by_ip = ip
            reaction.save(update_fields=["is_deleted", "deleted_at", "reaction_type", "updated_by_ip", "updated_at"])
            return Response({"message": f"Reaction '{reaction_type}' restored."})

        if reaction.reaction_type == reaction_type:
            reaction.soft_delete(ip=ip)
            return Response({"message": f"Reaction '{reaction_type}' removed."})

        reaction.reaction_type = reaction_type
        reaction.updated_by_ip = ip
        reaction.save(update_fields=["reaction_type", "updated_by_ip", "updated_at"])
        return Response({"message": f"Reaction switched to '{reaction_type}'."})


# ===========================================================================
# BlogCommentView (STRICT AUTH)
# ===========================================================================

class BlogCommentView(APIView):
    def get_permissions(self):
        # Anyone can GET comments, but POST requires Auth
        if self.request.method == 'GET':
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def get(self, request, blog_id):
        blog = get_object_or_404(Blog, pk=blog_id, is_deleted=False)
        qs = (
            BlogComment.objects
            .filter(blog=blog, is_approved=True, parent__isnull=True)
            .select_related("user")
            .prefetch_related("replies")
            .order_by("created_at")
        )
        paginator = BlogCommentPagination()
        page = paginator.paginate_queryset(qs, request)
        serializer = BlogCommentSerializer(page, many=True, context={"request": request})
        return paginator.get_paginated_response(serializer.data)

    def post(self, request, blog_id):
        blog = get_object_or_404(Blog, pk=blog_id, is_deleted=False, is_published=True)
        ip = get_client_ip(request)

        data = {
            "blog": blog.pk,
            "content": request.data.get("content"),
            "parent": request.data.get("parent"),
        }

        serializer = BlogCommentSerializer(data=data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        comment = serializer.save(
            ip_address=ip,
            user=request.user,  # Guaranteed by IsAuthenticated
            is_approved=True,   # Auto-approve since they are logged in (optional logic choice)
        )

        from django.utils import timezone
        comment.approved_at = timezone.now()
        comment.save(update_fields=["approved_at"])

        return Response(
            BlogCommentSerializer(comment, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class BlogCommentApproveView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, comment_id):
        comment = get_object_or_404(BlogComment, pk=comment_id, is_deleted=False)
        if comment.is_approved:
            return Response({"detail": "Comment is already approved."}, status=status.HTTP_400_BAD_REQUEST)

        comment.approve(ip=get_client_ip(request))
        return Response(
            BlogCommentSerializer(comment, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )
    
# ===========================================================================
# BlogApproval - Workflow
# ===========================================================================    

class BlogReviewAPIView(APIView):
    """
    POST Endpoint to Approve or Reject a Blog.
    Expected Payload (Approval): {"blog": 1, "status": "APPROVED"}
    Expected Payload (Rejection): {"blog": 1, "status": "REJECTED", "rejection_reason": "Spam content"}
    """
    # Ensure only authenticated users (and ideally only staff) can access this
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser] 

    def post(self, request, *args, **kwargs):
        serializer = BlogReviewSerializer(data=request.data)
        
        if serializer.is_valid():
            approval_status = serializer.validated_data.get('status')
            
            # Base arguments injected automatically bypassing the request payload
            save_kwargs = {
                'approver': request.user
            }
            
            # Set the rejection date if rejected
            if approval_status == 'REJECTED':
                save_kwargs['date_of_rejection'] = timezone.now().date()
            
            # Save the new BlogApproval history record
            serializer.save(**save_kwargs)
            
            return Response(
                {
                    "detail": f"Blog successfully {approval_status.lower()}.",
                    "data": serializer.data
                },
                status=status.HTTP_201_CREATED
            )
            
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ===========================================================================
# BlogPublish 
# ===========================================================================    

class ToggleBlogPublishAPIView(APIView):
    """
    Toggle blog publish status.
    
    Payload:
    {
        "blog": 1
    }
    """

    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]

    def post(self, request, *args, **kwargs):
        blog_id = request.data.get("blog")

        if not blog_id:
            return Response(
                {"detail": "Blog ID is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        blog = get_object_or_404(Blog, id=blog_id)

        # Toggle publish status
        blog.is_published = not blog.is_published

        # Set published_at only when publishing first time
        if blog.is_published and not blog.published_at:
            blog.published_at = timezone.now()

        blog.save(update_fields=["is_published", "published_at", "updated_at"])

        return Response(
            {
                "detail": f"Blog {'published' if blog.is_published else 'unpublished'} successfully.",
                "is_published": blog.is_published,
                "blog_id": blog.id,
            },
            status=status.HTTP_200_OK
        )
    
class BlogAnalyticsAPIView(APIView):
    """
    Returns complete analytics for the admin dashboard.
    """
    permission_classes = [permissions.IsAuthenticated] # Consider adding IsAdminUser

    def get(self, request):
        # 1. Base Querysets (Excluding Soft-Deleted)
        blogs = Blog.objects.filter(is_deleted=False)
        reactions = BlogReaction.objects.filter(is_deleted=False)
        comments = BlogComment.objects.filter(is_deleted=False)

        # 2. High-Level KPIs
        total_blogs = blogs.count()
        published_blogs = blogs.filter(is_published=True).count()
        
        # Safely sum views (returns None if no blogs exist, so we default to 0)
        total_views = blogs.aggregate(Sum('views_count'))['views_count__sum'] or 0
        
        total_likes = reactions.filter(reaction_type='like').count()
        total_dislikes = reactions.filter(reaction_type='dislike').count()
        total_comments = comments.count()

        # 3. Top 3 Blogs by Engagement (Likes + Comments + Views)
        # We annotate each blog with its specific counts to avoid N+1 queries
        top_blogs_qs = blogs.filter(is_published=True).annotate(
            like_count=Count('reactions', filter=Q(reactions__reaction_type='like', reactions__is_deleted=False), distinct=True),
            comment_count=Count('comments', filter=Q(comments__is_deleted=False), distinct=True)
        ).order_by('-views_count', '-like_count')[:3]

        top_blogs_data = []
        for blog in top_blogs_qs:
            author_name = blog.author.username if blog.author else blog.guest_name
            top_blogs_data.append({
                "id": blog.id,
                "title": blog.title,
                "author": author_name,
                "views": blog.views_count,
                "likes": blog.like_count,
                "comments": blog.comment_count,
                "published_at": blog.published_at.isoformat() if blog.published_at else None,
            })

        # 4. Status Distribution (From BlogApproval)
        # Useful for pie charts or progress bars
        approval_distribution = list(BlogApproval.objects.filter(is_deleted=False)
            .values('status')
            .annotate(count=Count('id'))
            .order_by('-count')
        )

        # Map the distribution into a clean dictionary: {"APPROVED": 10, "PENDING": 5}
        status_counts = {item['status']: item['count'] for item in approval_distribution}

        # 5. Recent Activity (Last 7 Days) for Bar Charts
        seven_days_ago = timezone.now() - timedelta(days=7)
        recent_blogs_count = blogs.filter(created_at__gte=seven_days_ago).count()
        recent_comments_count = comments.filter(created_at__gte=seven_days_ago).count()

        # Compile Final Response
        return Response({
            "kpis": {
                "total_blogs": total_blogs,
                "published_blogs": published_blogs,
                "total_views": total_views,
                "total_likes": total_likes,
                "total_dislikes": total_dislikes,
                "total_comments": total_comments,
            },
            "top_blogs": top_blogs_data,
            "status_distribution": status_counts,
            "recent_activity": {
                "new_blogs_last_7_days": recent_blogs_count,
                "new_comments_last_7_days": recent_comments_count,
            }
        }, status=status.HTTP_200_OK)    
    
# ===========================================================================
# BlogAuthorApi
# ===========================================================================    

class BlogAuthorAnalyticsView(generics.ListAPIView):
    """
    Returns analytics ONLY for users who have created at least one published/draft blog.
    Uses Subqueries to avoid the dreaded Django Cartesian Product multiplication bug.
    """
    serializer_class = BlogAuthorAnalyticsSerializer
    
    # Assuming only Staff/Admins should see these analytics
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]

    def get_queryset(self):
        # 1. Subquery: Count of blogs by the user
        blogs_sq = Blog.objects.filter(
            author=OuterRef('pk'), 
            is_deleted=False
        ).values('author').annotate(c=Count('id')).values('c')

        # 2. Subquery: Sum of all views across the user's blogs
        views_sq = Blog.objects.filter(
            author=OuterRef('pk'), 
            is_deleted=False
        ).values('author').annotate(s=Sum('views_count')).values('s')

        # 3. Subquery: Count of all 'likes' on the user's blogs
        likes_sq = BlogReaction.objects.filter(
            blog__author=OuterRef('pk'), 
            reaction_type='like', 
            is_deleted=False, 
            blog__is_deleted=False
        ).values('blog__author').annotate(c=Count('id')).values('c')

        # 4. Subquery: Count of all comments on the user's blogs
        comments_sq = BlogComment.objects.filter(
            blog__author=OuterRef('pk'), 
            is_deleted=False, 
            blog__is_deleted=False
        ).values('blog__author').annotate(c=Count('id')).values('c')

        # Base Query: Get active users, annotate them with the subqueries
        queryset = CustomUser.objects.filter(
            is_deleted=False, 
            blogs__is_deleted=False # Only fetch users tied to at least one active blog
        ).distinct().annotate(
            total_blogs=Coalesce(Subquery(blogs_sq, output_field=IntegerField()), 0),
            total_views=Coalesce(Subquery(views_sq, output_field=IntegerField()), 0),
            total_likes=Coalesce(Subquery(likes_sq, output_field=IntegerField()), 0),
            total_comments=Coalesce(Subquery(comments_sq, output_field=IntegerField()), 0),
        ).filter(
            total_blogs__gt=0 # Strict check: MUST have more than 0 blogs
        ).order_by('-total_blogs', '-total_views') # Order by most active authors first

        return queryset