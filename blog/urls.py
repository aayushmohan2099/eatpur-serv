"""
blog/urls.py
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import *

router = DefaultRouter()
router.register(r"blogs", BlogViewSet, basename="blog")

urlpatterns = [
    # --- ViewSet (CRUD + publish/unpublish/full) ---
    path("", include(router.urls)),

    # --- Analytics ---
    path('analytics/', BlogAnalyticsAPIView.as_view(), name='blog-analytics'),

    # --- Reactions ---
    path(
        "blogs/<int:blog_id>/react/",
        BlogReactionView.as_view(),
        name="blog-react",
    ),

    # --- Comments (list + submit) ---
    path(
        "blogs/<int:blog_id>/comments/",
        BlogCommentView.as_view(),
        name="blog-comments",
    ),

    # --- Comment moderation (staff only) ---
    path(
        "comments/<int:comment_id>/approve/",
        BlogCommentApproveView.as_view(),
        name="comment-approve",
    ),

    # Blog Review (Approve/Reject)
    path('review/', BlogReviewAPIView.as_view(), name='blog-review'),

    # Blog Publish
    path(
        "toggle-publish/",
        ToggleBlogPublishAPIView.as_view(),
        name="toggle-blog-publish",
    ),

    # Blog Author Analytics
    path('authors/', BlogAuthorAnalyticsView.as_view(), name='author-analytics'),
]
