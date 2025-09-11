from rest_framework.permissions import BasePermission

def _get_admin_profile(user):
    return getattr(user, "admin_profile", None)

class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        u = request.user
        return bool(
            u and u.is_authenticated and (
                getattr(u, "is_superuser", False) or _get_admin_profile(u)
            )
        )

class IsSuperAdmin(BasePermission):
    def has_permission(self, request, view):
        u = request.user
        if not (u and u.is_authenticated):
            return False
        # Django 슈퍼유저면 무조건 허용
        if getattr(u, "is_superuser", False):
            return True
        ap = _get_admin_profile(u)
        return bool(ap and ap.role == "super")   # AdminRole.SUPER 로 써도 됨

# shared/permissions.py
from rest_framework.permissions import BasePermission

def _get_admin_profile(user):
    return getattr(user, "admin_profile", None)

class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        u = request.user
        return bool(
            u and u.is_authenticated and (
                getattr(u, "is_superuser", False) or _get_admin_profile(u)
            )
        )

class IsSuperAdmin(BasePermission):
    def has_permission(self, request, view):
        u = request.user
        if not (u and u.is_authenticated):
            return False
        if getattr(u, "is_superuser", False):
            return True
        ap = _get_admin_profile(u)
        return bool(ap and ap.role == "super")

# ✅ 다시 추가: object-level 권한
class IsOwnerOrAdmin(BasePermission):
    """
    객체 권한:
      - Django superuser 이거나
      - admin_profile 존재(임의 role) 이거나
      - obj의 소유자가 현재 사용자일 때 허용
    """
    def has_permission(self, request, view):
        # 객체 단위 검사 전에 최소한 인증은 요구
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        u = request.user
        # 관리자는 무조건 패스
        if getattr(u, "is_superuser", False) or _get_admin_profile(u):
            return True

        # 소유자 판정: 흔한 필드명 순서대로 체크
        if hasattr(obj, "user_id"):
            return obj.user_id == u.id
        if hasattr(obj, "user"):
            return getattr(obj.user, "id", None) == u.id
        if hasattr(obj, "owner_id"):
            return obj.owner_id == u.id
        if hasattr(obj, "owner"):
            return getattr(obj.owner, "id", None) == u.id
        if hasattr(obj, "created_by_id"):
            return obj.created_by_id == u.id
        if hasattr(obj, "created_by"):
            return getattr(obj.created_by, "id", None) == u.id

        return False

