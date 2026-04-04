from django.shortcuts import render

# Create your views here.
class UpdateProfileView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def put(self, request):
        user = request.user

        data = request.data

        user.username = data.get("username", user.username)
        user.mobile = data.get("mobile", user.mobile)

        if "avatar" in request.FILES:
            user.avatar = request.FILES["avatar"]

        user.save()

        return Response(
            {"user": UserProfileSerializer(user).data},
            status=status.HTTP_200_OK,
        )
        
class ChangePasswordView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user

        old_password = request.data.get("old_password")
        new_password = request.data.get("new_password")

        if not user.check_password(old_password):
            return Response(
                {"error": "Invalid old password"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(new_password)
        user.save()

        return Response(
            {"message": "Password updated successfully"},
            status=status.HTTP_200_OK,
        )        
        
class DeleteAccountView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request):
        user = request.user
        ip = get_client_ip(request)

        user.soft_delete(ip=ip)

        return Response(
            {"message": "Account deleted successfully"},
            status=status.HTTP_200_OK,
        )
        
class UserListView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        users = CustomUser.objects.all()

        return Response(
            UserProfileSerializer(users, many=True).data
        )                