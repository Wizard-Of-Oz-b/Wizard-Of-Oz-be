# shared/permissions.py
from __future__ import annotations

from typing import Iterable, Optional

from rest_framework.permissions import SAFE_METHODS, BasePermission

# ---- helpers ---------------------------------------------------------------


def _is_schema_generation(view) -> bool:
    """drf-spectacular 스키마 생성 시 True (권한을 널널하게 통과시켜 문서 생성 편의)."""
    return bool(getattr(view, "swagger_fake_view", False))


def _user_has_role(user, roles: Iterable[str]) -> bool:
    """User.role 이 주어진 roles 중 하나인지."""
    return bool(
        getattr(user, "is_authenticated", False)
        and getattr(user, "role", None) in set(roles)
    )


def _get_owner_id(obj) -> Optional[int | str]:
    """
    여러 도메인에서 통용되도록 owner id를 추정.
    우선순위: user_id, owner_id, author_id, account_id → user.pk, owner.pk, author.pk, account.pk
    """
    id_keys = ("user_id", "owner_id", "author_id", "account_id")
    obj_keys = ("user", "owner", "author", "account")

    for k in id_keys:
        if hasattr(obj, k):
            return getattr(obj, k)

    for k in obj_keys:
        if hasattr(obj, k) and getattr(obj, k) is not None:
            try:
                return getattr(obj, k).pk
            except Exception:
                pass

    return None


# ---- role-based permissions ------------------------------------------------


def role_required(*accepted_roles: str):
    """
    사용 예)
        permission_classes = [role_required("admin")]
        permission_classes = [role_required("admin", "manager")]
    """

    class _RoleRequired(BasePermission):
        def has_permission(self, request, view):
            if _is_schema_generation(view):
                return True
            return _user_has_role(request.user, accepted_roles)

    _RoleRequired.__name__ = f"RoleRequired_{'_'.join(accepted_roles) or 'None'}"
    return _RoleRequired


class IsAdminRole(BasePermission):
    """role == 'admin'"""

    def has_permission(self, request, view):
        if _is_schema_generation(view):
            return True
        return _user_has_role(request.user, ("admin",))


class IsManagerOrAdmin(BasePermission):
    """role in {'manager', 'admin'}"""

    def has_permission(self, request, view):
        if _is_schema_generation(view):
            return True
        return _user_has_role(request.user, ("manager", "admin"))


class IsCSOrAdmin(BasePermission):
    """role in {'cs', 'admin'}"""

    def has_permission(self, request, view):
        if _is_schema_generation(view):
            return True
        return _user_has_role(request.user, ("cs", "admin"))


class IsAuthenticatedAndActive(BasePermission):
    """로그인 + status == 'active'"""

    def has_permission(self, request, view):
        if _is_schema_generation(view):
            return True
        u = request.user
        return bool(
            getattr(u, "is_authenticated", False)
            and getattr(u, "status", None) == "active"
        )


# ---- owner-based permissions ----------------------------------------------


class IsOwnerOrAdmin(BasePermission):
    """
    SAFE_METHODS(GET/HEAD/OPTIONS)은 모두 허용.
    그 외 메서드는 (admin) 또는 (obj의 owner == 현재 유저)만 허용.
    """

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        if _is_schema_generation(view):
            return True

        user = request.user
        if not getattr(user, "is_authenticated", False):
            return False
        if getattr(user, "role", None) == "admin":
            return True

        owner_id = _get_owner_id(obj)
        return owner_id is not None and owner_id == getattr(user, "pk", None)


class ReadOnly(BasePermission):
    """읽기만 허용"""

    def has_permission(self, request, view):
        if _is_schema_generation(view):
            return True
        return request.method in SAFE_METHODS


class ReadOnlyOrAdmin(BasePermission):
    """읽기 자유, 쓰기/변경은 admin만"""

    def has_permission(self, request, view):
        if _is_schema_generation(view):
            return True
        if request.method in SAFE_METHODS:
            return True
        return _user_has_role(request.user, ("admin",))


__all__ = [
    "role_required",
    "IsAdminRole",
    "IsManagerOrAdmin",
    "IsCSOrAdmin",
    "IsAuthenticatedAndActive",
    "IsOwnerOrAdmin",
    "ReadOnly",
    "ReadOnlyOrAdmin",
]
