from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from .models import GoogleFormResponse


@api_view(["POST"])
@permission_classes([AllowAny])
def google_form_webhook(request):
    GoogleFormResponse.objects.create(
        stars=request.data.get("stars"),
        name=request.data.get("name"),
        mobile=request.data.get("mobile"),
        email=request.data.get("email"),
        response_description=request.data.get("response_description"),
        response_url=request.data.get("response_url"),
    )
    return Response({"status": "ok"})


#  GET API: Custom Admin Dashboard  reviews show

@api_view(["GET"])
@permission_classes([AllowAny])  
def get_all_reviews(request):
    
    reviews = GoogleFormResponse.objects.all().order_by('-id').values(
        'id', 
        'name', 
        'mobile', 
        'email', 
        'stars', 
        'response_description', 
        'address', 
        'response_url'
    )
    
    return Response({
        "status": "success",
        "total_reviews": reviews.count(),
        "data": list(reviews)
    })