"""
logistics/api/ekart_auth/serializers.py
"""
from rest_framework import serializers
from logistics.models import EkartAuthToken

class EkartAuthTokenSerializer(serializers.ModelSerializer):
    class Meta:
        model = EkartAuthToken
        fields = ["access_token", "token_type", "scope", "expires_at", "created_at"]
        
    def to_representation(self, instance):
        """Mask the actual token for security when returning to the frontend/admin."""
        ret = super().to_representation(instance)
        token = ret.get("access_token", "")
        if len(token) > 10:
            ret["access_token"] = f"{token[:5]}...{token[-5:]}"
        return ret