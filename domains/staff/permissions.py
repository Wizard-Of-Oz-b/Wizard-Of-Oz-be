# api/staff/permissions.py
from rest_framework.permissions import BasePermission

class IsAdminRole(BasePermission):
    message = "관리자만 접근할 수 있습니다."
    def has_permission(self, request, view):
        u = getattr(request, "user", None)
        return bool(u and u.is_authenticated and getattr(u, "role", "") == "admin")

class IsAdminOrManager(BasePermission):
    message = "관리자 또는 매니저만 접근할 수 있습니다."
    def has_permission(self, request, view):
        u = getattr(request, "user", None)
        return bool(u and u.is_authenticated and getattr(u, "role", "") in ("admin", "manager"))
