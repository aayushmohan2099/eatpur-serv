"""
blog/urls.py
============

Router-registered routes (BlogViewSet)
---------------------------------------
GET    /blogs/                   → list published blogs
POST   /blogs/                   → create blog (auth required)
GET    /blogs/{id}/              → retrieve blog (detail)
PUT    /blogs/{id}/              → full update (auth required)
PATCH  /blogs/{id}/              → partial update (auth required)
DELETE /blogs/{id}/              → soft delete (auth required)
GET    /blogs/{id}/full/         → alias for detail (full payload)
POST   /blogs/{id}/publish/      → publish blog (auth required)
POST   /blogs/{id}/unpublish/    → unpublish blog (auth required)

Manual routes
-------------
POST   /blogs/{id}/react/                → toggle like/dislike
GET    /blogs/{id}/comments/             → paginated approved comments
POST   /blogs/{id}/comments/             → submit comment
POST   /comments/{comment_id}/approve/   → staff-only moderation
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    BlogViewSet,
    BlogReactionView,
    BlogCommentView,
    BlogCommentApproveView,
)

router = DefaultRouter()
router.register(r"blogs", BlogViewSet, basename="blog")

urlpatterns = [
    # --- ViewSet (CRUD + publish/unpublish/full) ---
    path("", include(router.urls)),

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
]
