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
    def has_object_permission(self, request, view, obj):
            return False
