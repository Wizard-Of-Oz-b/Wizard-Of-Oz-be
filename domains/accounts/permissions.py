from rest_framework.permissions import BasePermission, SAFE_METHODS

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
