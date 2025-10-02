"""
domains/accounts/permissions.py 테스트
"""

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from domains.accounts.models import User


@pytest.mark.django_db
def test_is_self_permission():
    """IsSelf 권한 테스트"""
    from domains.accounts.permissions import IsSelf

    # 테스트 사용자 생성
    user1 = User.objects.create_user(
        username="user1", email="user1@test.com", password="testpass123"
    )
    user2 = User.objects.create_user(
        username="user2", email="user2@test.com", password="testpass123"
    )

    permission = IsSelf()

    # 인증되지 않은 사용자
    class MockRequest:
        user = None

    request = MockRequest()
    assert permission.has_object_permission(request, None, user1) == False

    # 본인 객체에 대한 접근
    class MockRequestSelf:
        user = user1

    request_self = MockRequestSelf()
    assert permission.has_object_permission(request_self, None, user1) == True

    # 다른 사용자 객체에 대한 접근
    class MockRequestOther:
        user = user1

    request_other = MockRequestOther()
    assert permission.has_object_permission(request_other, None, user2) == False


@pytest.mark.django_db
def test_is_admin_role_permission():
    """IsAdminRole 권한 테스트"""
    from domains.accounts.permissions import IsAdminRole

    # 일반 사용자 생성
    user = User.objects.create_user(
        username="user", email="user@test.com", password="testpass123", role="user"
    )

    # 관리자 사용자 생성
    admin = User.objects.create_user(
        username="admin", email="admin@test.com", password="testpass123", role="admin"
    )

    permission = IsAdminRole()

    # 인증되지 않은 사용자
    class MockRequestUnauth:
        user = None

    request_unauth = MockRequestUnauth()
    assert permission.has_permission(request_unauth, None) == False

    # 일반 사용자
    class MockRequestUser:
        def __init__(self, user_obj):
            self.user = user_obj

    request_user = MockRequestUser(user)
    assert permission.has_permission(request_user, None) == False

    # 관리자 사용자
    class MockRequestAdmin:
        def __init__(self, user_obj):
            self.user = user_obj

    request_admin = MockRequestAdmin(admin)
    assert permission.has_permission(request_admin, None) == True
