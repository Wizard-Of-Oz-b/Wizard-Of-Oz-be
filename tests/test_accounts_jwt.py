import pytest
from unittest.mock import patch, MagicMock
from django.contrib.auth import get_user_model
from rest_framework.exceptions import AuthenticationFailed

from domains.accounts.jwt import EmailTokenObtainPairSerializer, EmailTokenObtainPairView

User = get_user_model()


@pytest.mark.django_db
class TestEmailTokenObtainPairSerializer:
    """EmailTokenObtainPairSerializer 테스트"""
    
    def test_username_field(self):
        """username_field가 email로 설정되었는지 테스트"""
        serializer = EmailTokenObtainPairSerializer()
        assert serializer.username_field == "email"
    
    def test_validate_success(self, user_factory):
        """유효한 이메일/비밀번호로 토큰 발급 성공 테스트"""
        user = user_factory(email="test@example.com", password="testpass123")
        
        serializer = EmailTokenObtainPairSerializer()
        attrs = {
            "email": "test@example.com",
            "password": "testpass123"
        }
        
        result = serializer.validate(attrs)
        
        # 검증
        assert "refresh" in result
        assert "access" in result
        assert result["refresh"] is not None
        assert result["access"] is not None
    
    def test_validate_email_case_insensitive(self, user_factory):
        """이메일 대소문자 무시 테스트"""
        user = user_factory(email="Test@Example.com", password="testpass123")
        
        serializer = EmailTokenObtainPairSerializer()
        attrs = {
            "email": "test@example.com",  # 소문자로 입력
            "password": "testpass123"
        }
        
        result = serializer.validate(attrs)
        
        # 검증
        assert "refresh" in result
        assert "access" in result
    
    def test_validate_email_whitespace_trim(self, user_factory):
        """이메일 공백 제거 테스트"""
        user = user_factory(email="test@example.com", password="testpass123")
        
        serializer = EmailTokenObtainPairSerializer()
        attrs = {
            "email": "  test@example.com  ",  # 앞뒤 공백
            "password": "testpass123"
        }
        
        result = serializer.validate(attrs)
        
        # 검증
        assert "refresh" in result
        assert "access" in result
    
    def test_validate_user_not_found(self):
        """존재하지 않는 사용자 테스트"""
        serializer = EmailTokenObtainPairSerializer()
        attrs = {
            "email": "nonexistent@example.com",
            "password": "testpass123"
        }
        
        with pytest.raises(AuthenticationFailed) as exc_info:
            serializer.validate(attrs)
        
        assert "지정된 자격 증명에 해당하는 활성화된 사용자를 찾을 수 없습니다" in str(exc_info.value)
        assert exc_info.value.detail == "지정된 자격 증명에 해당하는 활성화된 사용자를 찾을 수 없습니다"
        # AuthenticationFailed의 default_code는 'authentication_failed'가 됨
        assert exc_info.value.default_code == "authentication_failed"
    
    def test_validate_wrong_password(self, user_factory):
        """잘못된 비밀번호 테스트"""
        user = user_factory(email="test@example.com", password="correctpass123")
        
        serializer = EmailTokenObtainPairSerializer()
        attrs = {
            "email": "test@example.com",
            "password": "wrongpass123"
        }
        
        with pytest.raises(AuthenticationFailed) as exc_info:
            serializer.validate(attrs)
        
        assert "지정된 자격 증명에 해당하는 활성화된 사용자를 찾을 수 없습니다" in str(exc_info.value)
        assert exc_info.value.default_code == "authentication_failed"
    
    def test_validate_inactive_user(self, user_factory):
        """비활성 사용자 테스트"""
        user = user_factory(email="test@example.com", password="testpass123", is_active=False)
        
        serializer = EmailTokenObtainPairSerializer()
        attrs = {
            "email": "test@example.com",
            "password": "testpass123"
        }
        
        with pytest.raises(AuthenticationFailed) as exc_info:
            serializer.validate(attrs)
        
        assert "지정된 자격 증명에 해당하는 활성화된 사용자를 찾을 수 없습니다" in str(exc_info.value)
        assert exc_info.value.default_code == "authentication_failed"
    
    def test_validate_empty_email(self):
        """빈 이메일 테스트"""
        serializer = EmailTokenObtainPairSerializer()
        attrs = {
            "email": "",
            "password": "testpass123"
        }
        
        with pytest.raises(AuthenticationFailed) as exc_info:
            serializer.validate(attrs)
        
        assert "지정된 자격 증명에 해당하는 활성화된 사용자를 찾을 수 없습니다" in str(exc_info.value)
    
    def test_validate_none_email(self):
        """None 이메일 테스트"""
        serializer = EmailTokenObtainPairSerializer()
        attrs = {
            "email": None,
            "password": "testpass123"
        }
        
        with pytest.raises(AuthenticationFailed) as exc_info:
            serializer.validate(attrs)
        
        assert "지정된 자격 증명에 해당하는 활성화된 사용자를 찾을 수 없습니다" in str(exc_info.value)
    
    def test_validate_empty_password(self, user_factory):
        """빈 비밀번호 테스트"""
        user = user_factory(email="test@example.com", password="testpass123")
        
        serializer = EmailTokenObtainPairSerializer()
        attrs = {
            "email": "test@example.com",
            "password": ""
        }
        
        with pytest.raises(AuthenticationFailed) as exc_info:
            serializer.validate(attrs)
        
        assert "지정된 자격 증명에 해당하는 활성화된 사용자를 찾을 수 없습니다" in str(exc_info.value)
    
    def test_validate_none_password(self, user_factory):
        """None 비밀번호 테스트"""
        user = user_factory(email="test@example.com", password="testpass123")
        
        serializer = EmailTokenObtainPairSerializer()
        attrs = {
            "email": "test@example.com",
            "password": None
        }
        
        with pytest.raises(AuthenticationFailed) as exc_info:
            serializer.validate(attrs)
        
        assert "지정된 자격 증명에 해당하는 활성화된 사용자를 찾을 수 없습니다" in str(exc_info.value)
    
    def test_validate_missing_email_key(self):
        """이메일 키 누락 테스트"""
        serializer = EmailTokenObtainPairSerializer()
        attrs = {
            "password": "testpass123"
        }
        
        with pytest.raises(AuthenticationFailed) as exc_info:
            serializer.validate(attrs)
        
        assert "지정된 자격 증명에 해당하는 활성화된 사용자를 찾을 수 없습니다" in str(exc_info.value)
    
    def test_validate_missing_password_key(self, user_factory):
        """비밀번호 키 누락 테스트"""
        user = user_factory(email="test@example.com", password="testpass123")
        
        serializer = EmailTokenObtainPairSerializer()
        attrs = {
            "email": "test@example.com"
        }
        
        with pytest.raises(AuthenticationFailed) as exc_info:
            serializer.validate(attrs)
        
        assert "지정된 자격 증명에 해당하는 활성화된 사용자를 찾을 수 없습니다" in str(exc_info.value)


@pytest.mark.django_db
class TestEmailTokenObtainPairView:
    """EmailTokenObtainPairView 테스트"""
    
    def test_serializer_class(self):
        """serializer_class가 올바르게 설정되었는지 테스트"""
        view = EmailTokenObtainPairView()
        assert view.serializer_class == EmailTokenObtainPairSerializer
    
    def test_view_inheritance(self):
        """TokenObtainPairView를 상속받았는지 테스트"""
        from rest_framework_simplejwt.views import TokenObtainPairView
        assert issubclass(EmailTokenObtainPairView, TokenObtainPairView)


@pytest.mark.django_db
class TestJWTIntegration:
    """JWT 통합 테스트"""
    
    def test_complete_jwt_flow(self, user_factory):
        """완전한 JWT 플로우 테스트"""
        # 사용자 생성
        user = user_factory(
            email="integration@example.com",
            password="integrationpass123"
        )
        
        # 시리얼라이저로 토큰 발급
        serializer = EmailTokenObtainPairSerializer()
        attrs = {
            "email": "integration@example.com",
            "password": "integrationpass123"
        }
        
        result = serializer.validate(attrs)
        
        # 검증
        assert "refresh" in result
        assert "access" in result
        
        # 토큰이 유효한 문자열인지 확인
        assert isinstance(result["refresh"], str)
        assert isinstance(result["access"], str)
        assert len(result["refresh"]) > 0
        assert len(result["access"]) > 0
    
    def test_multiple_users_different_emails(self, user_factory):
        """여러 사용자 다른 이메일 테스트"""
        user1 = user_factory(email="user1@example.com", password="pass1")
        user2 = user_factory(email="user2@example.com", password="pass2")
        
        serializer = EmailTokenObtainPairSerializer()
        
        # 첫 번째 사용자
        attrs1 = {
            "email": "user1@example.com",
            "password": "pass1"
        }
        result1 = serializer.validate(attrs1)
        
        # 두 번째 사용자
        attrs2 = {
            "email": "user2@example.com",
            "password": "pass2"
        }
        result2 = serializer.validate(attrs2)
        
        # 각각 다른 토큰이 발급되는지 확인
        assert result1["refresh"] != result2["refresh"]
        assert result1["access"] != result2["access"]
    
    def test_same_user_different_case_emails(self, user_factory):
        """같은 사용자 다른 대소문자 이메일 테스트"""
        user = user_factory(email="MixedCase@Example.com", password="testpass123")
        
        serializer = EmailTokenObtainPairSerializer()
        
        # 다양한 대소문자 조합으로 테스트
        test_emails = [
            "mixedcase@example.com",
            "MIXEDCASE@EXAMPLE.COM",
            "MixedCase@Example.com",
            "MIXEDCASE@example.com"
        ]
        
        for email in test_emails:
            attrs = {
                "email": email,
                "password": "testpass123"
            }
            result = serializer.validate(attrs)
            
            # 모든 경우에 토큰이 발급되는지 확인
            assert "refresh" in result
            assert "access" in result
