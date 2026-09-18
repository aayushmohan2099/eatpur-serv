# user/serializers.py
from rest_framework import serializers
from django.contrib.auth.hashers import make_password
from .models import CustomUser, Role, Address

class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = '__all__'


class UserDetailSerializer(serializers.ModelSerializer):
    """
    Used for Listing and Retrieving users (Read-Only).
    Nests the Role details.
    """
    role = RoleSerializer(read_only=True)

    class Meta:
        model = CustomUser
        exclude = ['password', 'is_superuser', 'groups', 'user_permissions']


class UserCreateUpdateSerializer(serializers.ModelSerializer):
    """
    Used for Creating and Updating users (Write).
    Expects a role ID and handles password hashing safely.
    """
    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'mobile', 'password', 'avatar', 'role', 'is_active', 'is_staff']
        extra_kwargs = {
            'password': {'write_only': True, 'required': False}
        }

    def create(self, validated_data):
        # Hash password upon creation
        if 'password' in validated_data:
            validated_data['password'] = make_password(validated_data['password'])
        return super().create(validated_data)

    def update(self, instance, validated_data):
        # Hash password if updated
        if 'password' in validated_data:
            validated_data['password'] = make_password(validated_data['password'])
        return super().update(instance, validated_data)

# ===========================================================================
# ADDRESS SERIALIZER
# ===========================================================================
class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = ['id', 'user', 'title', 'street_address', 'city', 'state', 'pincode', 'is_deleted']
        
        read_only_fields = ['user', 'is_deleted']