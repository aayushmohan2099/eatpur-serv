"""
logistics/api/ekart_auth/views.py
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser
from rest_framework import status

from logistics.models import EkartAuthToken
from logistics.utils.ekart_client import EkartClient
from .serializers import EkartAuthTokenSerializer

class EkartTokenRefreshView(APIView):
    """
    POST /api/logistics/auth/refresh/
    
    Forces a manual refresh of the Ekart authentication token.
    Requires Admin privileges.
    """
    permission_classes = [IsAdminUser]

    def post(self, request):
        client = EkartClient()
        try:
            # Force a fresh token fetch
            client.get_valid_token(force_refresh=True)
            
            # Fetch the newly created token to serialize
            new_token = EkartAuthToken.objects.filter(is_deleted=False).order_by("-expires_at").first()
            
            return Response({
                "message": "Ekart token successfully refreshed.",
                "token_info": EkartAuthTokenSerializer(new_token).data
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                "error": "Failed to refresh token.",
                "detail": str(e)
            }, status=status.HTTP_502_BAD_GATEWAY)

    def get(self, request):
        """
        GET /api/logistics/auth/refresh/
        Returns the current active token status without refreshing.
        """
        active_token = EkartAuthToken.objects.filter(is_deleted=False).order_by("-expires_at").first()
        
        if not active_token:
            return Response({"message": "No active token found in database."}, status=status.HTTP_404_NOT_FOUND)
            
        return Response({
            "is_valid_currently": active_token.is_valid(),
            "token_info": EkartAuthTokenSerializer(active_token).data
        }, status=status.HTTP_200_OK)