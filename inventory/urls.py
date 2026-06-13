from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import *

# Use DefaultRouter to automatically map the standard ViewSet actions
router = DefaultRouter()
router.register(r'products', ProductViewSet, basename='product')
router.register(r'categories', ProductCategoryViewSet, basename='category')

urlpatterns = [
    path('', include(router.urls)),
]