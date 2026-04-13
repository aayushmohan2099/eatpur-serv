def user_role(request):
    if request.user.is_authenticated:
        role = getattr(request.user.role, "role_name", "CUSTOMER")
    else:
        role = "GUEST"

    return {
        "USER_ROLE": role
    }