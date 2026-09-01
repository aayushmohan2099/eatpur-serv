from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import *

# Use DefaultRouter to automatically map the standard ViewSet actions
router = DefaultRouter()
router.register(r'products', ProductViewSet, basename='product')
router.register(r'categories', ProductCategoryViewSet, basename='category')

urlpatterns = [
    path('', include(router.urls)),
    path('public-catalog/', PublicProductListView.as_view(), name='public-product-catalog'),    
    path('products/<str:pid>/like/', ProductLikeToggleView.as_view(), name='product-like-toggle'),
    path('products/<str:pid>/comments/', ProductCommentCreateView.as_view(), name='product-comments'),
]

