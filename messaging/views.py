# views.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from messaging.models import GoogleFormResponse

@api_view(["POST"])
@permission_classes([AllowAny])  # IMPORTANT
def google_form_webhook(request):
    GoogleFormResponse.objects.create(
        name=request.data.get("name"),
        mobile=request.data.get("mobile"),
        email=request.data.get("email"),
        response_description=request.data.get("response_description"),
        response_url=request.data.get("response_url"),
    )
    return Response({"status": "ok"})