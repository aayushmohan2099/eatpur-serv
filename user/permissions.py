# user/permissions.py
from rest_framework import permissions

class IsRoleIdFive(permissions.BasePermission):
    """
    Custom permission to only allow access to users who have role_id = 5.
    """
    def has_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and 
            request.user.role_id == 5
        )