# domains/accounts/jwt.py
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password

from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView

User = get_user_model()


class EmailTokenObtainPairSerializer(TokenObtainPairSerializer):
    # 입력 필드로 email을 쓰겠다고 선언 (폼/스키마용)
    username_field = "email"

    def validate(self, attrs):
        email = (attrs.get("email") or "").strip()
        password = attrs.get("password") or ""

        # 이메일 대소문자 무시 조회
        user = User.objects.filter(email__iexact=email).first()

        # 존재/활성/비밀번호 확인
        if (
            not user
            or not getattr(user, "is_active", True)
            or not check_password(password, user.password)
        ):
            raise AuthenticationFailed(
                detail="지정된 자격 증명에 해당하는 활성화된 사용자를 찾을 수 없습니다",
                code="no_active_account",
            )

        # 기본 토큰 발급 로직 재사용
        refresh = self.get_token(user)
        return {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
        }


class EmailTokenObtainPairView(TokenObtainPairView):
    serializer_class = EmailTokenObtainPairSerializer
