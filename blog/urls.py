# blog/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import *

router = DefaultRouter()
router.register(r'blogs', BlogViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('blogs/<str:blog_id>/react/', BlogReactionView.as_view()),
    path('blogs/<str:blog_id>/comment/', BlogCommentView.as_view()),
]