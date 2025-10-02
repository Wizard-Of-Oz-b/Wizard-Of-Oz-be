from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsSelf(BasePermission):
    """
    객체의 주인이면 허용.
    """

    def has_object_permission(self, request, view, obj):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        # obj가 User 인스턴스라고 가정
        return getattr(obj, "pk", None) == getattr(user, "pk", None)


class IsAdminRole(BasePermission):
    message = "관리자만 접근할 수 있습니다."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and getattr(request.user, "role", "") == "admin"
        )
