# user/urls.py
from django.urls import path
from .views import (
    UserListAPIView, 
    UserDetailAPIView,
    UserCreateAPIView,
    UserUpdateDestroyAPIView,
    RoleListAPIView,
    RoleCreateAPIView,
    RoleRetrieveUpdateDestroyAPIView
)

urlpatterns = [
    # 1, 2 & 3) User endpoints
    path('users/', UserListAPIView.as_view(), name='user-list'),
    path('users/create/', UserCreateAPIView.as_view(), name='user-create'),
    path('users/detail/<int:user_id>/', UserDetailAPIView.as_view(), name='user-detail'),
    path('users/update-delete/<int:user_id>/', UserUpdateDestroyAPIView.as_view(), name='user-update-delete'),

    # 4 & 5) Role endpoints
    path('roles/', RoleListAPIView.as_view(), name='role-list'),
    path('roles/create/', RoleCreateAPIView.as_view(), name='role-create'),
    path('roles/<int:pk>/', RoleRetrieveUpdateDestroyAPIView.as_view(), name='role-detail-update-delete'),
]