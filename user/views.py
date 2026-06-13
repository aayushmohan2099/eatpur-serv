# user/views.py
from rest_framework import generics, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.shortcuts import render

from .models import CustomUser, Role
from .serializers import (
    UserDetailSerializer, 
    UserCreateUpdateSerializer, 
    RoleSerializer
)
from .pagination import StandardResultsSetPagination
from .permissions import IsRoleIdFive

def get_client_ip(request):
    """Utility function to extract client IP from the request."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


# ===========================================================================
# 1, 2 & 3) USER APIS
# ===========================================================================

class UserListAPIView(generics.ListAPIView):
    """
    1) Paginated user listing (15 items per page).
    """
    queryset = CustomUser.objects.filter(is_deleted=False)
    serializer_class = UserDetailSerializer
    pagination_class = StandardResultsSetPagination
    permission_classes = [permissions.IsAuthenticated]


class UserDetailAPIView(generics.RetrieveAPIView):
    """
    1) Returns ALL related fields of a user with role details.
    """
    queryset = CustomUser.objects.filter(is_deleted=False)
    serializer_class = UserDetailSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    lookup_field = 'id'
    lookup_url_kwarg = 'user_id'


class UserCreateAPIView(generics.CreateAPIView):
    """
    2) User creation API.
    """
    queryset = CustomUser.objects.all()
    serializer_class = UserCreateUpdateSerializer
    permission_classes = [permissions.IsAuthenticated]  # Or restrict to Admin


class UserUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    """
    3) User updation and deletion API.
    """
    queryset = CustomUser.objects.filter(is_deleted=False)
    serializer_class = UserCreateUpdateSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    lookup_field = 'id'
    lookup_url_kwarg = 'user_id'

    def perform_destroy(self, instance):
        """
        Triggers the custom soft_delete method on the CustomUser model.
        """
        ip = get_client_ip(self.request)
        instance.soft_delete(ip=ip)


# ===========================================================================
# 4 & 5) ROLE APIS
# ===========================================================================

class RoleListAPIView(generics.ListAPIView):
    """
    4) Roles listing API.
    """
    queryset = Role.objects.filter(is_deleted=False)
    serializer_class = RoleSerializer
    permission_classes = [permissions.IsAuthenticated]


class RoleCreateAPIView(generics.CreateAPIView):
    """
    5) Roles Creation API (Only users with role_id = 5 allowed).
    """
    queryset = Role.objects.all()
    serializer_class = RoleSerializer
    permission_classes = [IsRoleIdFive]


class RoleRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    """
    5) Roles Updation/Deletion API (Only users with role_id = 5 allowed).
    """
    queryset = Role.objects.filter(is_deleted=False)
    serializer_class = RoleSerializer
    permission_classes = [IsRoleIdFive]

    def perform_destroy(self, instance):
        """Standard ORM delete(). Depends on Role model's SoftDeleteMixin implementation."""
        instance.delete()