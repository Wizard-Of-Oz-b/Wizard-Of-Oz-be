from django.contrib.auth import get_user_model

import pytest

from domains.accounts.models import SocialAccount, UserAddress, UserRole

User = get_user_model()


@pytest.mark.django_db
class TestUserModel:
    """User 모델 테스트"""

    def test_user_role_properties(self, user_factory):
        """사용자 역할 속성 테스트 (87, 91, 95번째 줄 커버)"""
        # 관리자 사용자 생성
        admin_user = user_factory(role="admin")
        assert admin_user.is_admin_role == True
        assert admin_user.is_manager_role == False
        assert admin_user.is_cs_role == False

        # 매니저 사용자 생성
        manager_user = user_factory(role="manager")
        assert manager_user.is_admin_role == False
        assert manager_user.is_manager_role == True
        assert manager_user.is_cs_role == False

        # CS 사용자 생성
        cs_user = user_factory(role="cs")
        assert cs_user.is_admin_role == False
        assert cs_user.is_manager_role == False
        assert cs_user.is_cs_role == True

        # 일반 사용자 생성
        user = user_factory(role="user")
        assert user.is_admin_role == False
        assert user.is_manager_role == False
        assert user.is_cs_role == False

    def test_user_str_method(self, user_factory):
        """사용자 문자열 표현 테스트 (99번째 줄 커버)"""
        # 이메일이 있는 사용자
        user_with_email = user_factory(email="test@example.com", username="testuser")
        assert str(user_with_email) == "test@example.com"

        # 이메일이 없는 사용자 (username 사용)
        user_without_email = user_factory(email="", username="testuser2")
        assert str(user_without_email) == "testuser2"

        # 이메일이 None인 사용자 (고유한 이메일 사용)
        user_none_email = user_factory(
            email="testuser3@example.com", username="testuser3"
        )
        # 이메일이 있으면 이메일을 반환
        assert str(user_none_email) == "testuser3@example.com"


@pytest.mark.django_db
class TestSocialAccountModel:
    """SocialAccount 모델 테스트"""

    def test_social_account_str_method(self, user_factory):
        """소셜 계정 문자열 표현 테스트 (158번째 줄 커버)"""
        user = user_factory()
        social_account = SocialAccount.objects.create(
            user=user, provider="google", provider_uid="google_123456"
        )

        expected_str = f"google:google_123456 -> {user.id}"
        assert str(social_account) == expected_str


@pytest.mark.django_db
class TestUserAddressModel:
    """UserAddress 모델 테스트"""

    def test_user_address_str_method(self, user_factory):
        """사용자 주소 문자열 표현 테스트 (186번째 줄 커버)"""
        user = user_factory()
        address = UserAddress.objects.create(
            user=user,
            recipient="홍길동",
            address1="서울시 강남구 테헤란로 123",
            address2="456호",
            postcode="12345",
            phone="010-1234-5678",
        )

        expected_str = f"{user.id} / 홍길동 / 서울시 강남구 테헤란로 123"
        assert str(address) == expected_str

    def test_user_address_default_constraint(self, user_factory):
        """사용자 기본 주소 제약 조건 테스트"""
        user = user_factory()

        # 첫 번째 기본 주소 생성
        address1 = UserAddress.objects.create(
            user=user,
            recipient="홍길동",
            address1="서울시 강남구 테헤란로 123",
            postcode="12345",
            phone="010-1234-5678",
            is_default=True,
        )

        # 같은 사용자의 두 번째 기본 주소 생성 시도 (제약 조건 위반)
        with pytest.raises(Exception):  # IntegrityError 또는 ValidationError
            UserAddress.objects.create(
                user=user,
                recipient="김철수",
                address1="서울시 서초구 서초대로 456",
                postcode="67890",
                phone="010-9876-5432",
                is_default=True,
            )
