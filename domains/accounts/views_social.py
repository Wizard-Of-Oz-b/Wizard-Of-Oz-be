# domains/accounts/views_social.py
from typing import Dict, Optional
import os
import json
from django.db import models as dj_models

from django.conf import settings
from django.db import transaction
from rest_framework import status, permissions, generics, serializers
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User, SocialAccount
from .serializers import TokenPairResponseSerializer
from .serializers_social import SocialAuthRequestSerializer  # ← 여기로 통일
from .social import exchange_code_for_tokens, fetch_userinfo, SocialAuthError


# ---- 유틸: JWT 발급 ----
def issue_jwt_pair(user: User) -> Dict[str, str]:
    refresh = RefreshToken.for_user(user)
    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
    }

# ---- 유틸: Refresh 쿠키 ----
def set_refresh_cookie(response: Response, refresh_token: str):
    cfg = getattr(settings, "SIMPLE_JWT", {})
    lifetime = cfg.get("REFRESH_TOKEN_LIFETIME")
    # 타입 방어 (timedelta가 아닐 수도 있음)
    max_age = int(lifetime.total_seconds()) if hasattr(lifetime, "total_seconds") else None
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=False,   # 개발용. 운영에선 True 권장 + SameSite 조정
        samesite="Lax",
        max_age=max_age,
        path="/",
    )

# ---- provider 키 로딩 ----
def _env(name: str) -> str:
    # env 우선, 없으면 settings.* 도 시도
    return os.getenv(name) or getattr(settings, name, "")

def get_provider_keys(provider: str):
    p = provider.lower()
    if p == "naver":
        return {"client_id": _env("NAVER_CLIENT_ID"), "client_secret": _env("NAVER_CLIENT_SECRET")}
    if p == "google":
        return {"client_id": _env("GOOGLE_CLIENT_ID"), "client_secret": _env("GOOGLE_CLIENT_SECRET")}
    if p == "kakao":
        # REST_API_KEY 이름을 썼던 케이스까지 호환
        cid = _env("KAKAO_CLIENT_ID") or _env("KAKAO_REST_API_KEY")
        return {"client_id": cid, "client_secret": _env("KAKAO_CLIENT_SECRET")}
    return None
# ---- 소셜 로그인 ----
class SocialLoginView(generics.GenericAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = SocialAuthRequestSerializer  # ← 통일

    def post(self, request, provider: str):
        provider = (provider or "").lower()

        # 1) 요청 검증
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)

        code = ser.validated_data["code"]
        state = ser.validated_data.get("state") or ""
        redirect_uri = (
                ser.validated_data.get("redirect_uri")
                or os.getenv(f"{provider.upper()}_REDIRECT_URI", "")
        )
        if not redirect_uri:
            return Response({"detail": "redirect_uri required"}, status=400)

        # 2) 키 확인
        keys = get_provider_keys(provider)
        if not keys or not keys.get("client_id"):
            return Response({"detail": f"{provider} provider keys not configured"}, status=400)

        # 3) 코드 → 토큰 교환
        try:
            tokens = exchange_code_for_tokens(
                provider=provider,
                code=code,
                redirect_uri=redirect_uri,  # 인가 때와 완전히 동일해야 함
                state=state,
            )
        except SocialAuthError as e:
            # 카카오/구글/네이버의 실제 에러 메시지를 그대로 확인 가능
            return Response({"detail": f"{provider} token error: {e}"}, status=400)

        if not isinstance(tokens, dict):
            return Response({"detail": "token endpoint returned unexpected response"}, status=400)

        access_token = tokens.get("access_token") or tokens.get("accessToken")
        if not access_token:
            return Response({"detail": "missing access_token from provider"}, status=400)
        # 4) 사용자 프로필 조회
        profile = fetch_userinfo(provider, access_token)
        if not profile or not profile.get("provider_uid"):
            return Response({"detail": "failed to fetch userinfo"}, status=400)

        provider_uid = str(profile["provider_uid"])
        email = profile.get("email")

        # 5) 유저 매핑/생성 (트랜잭션)
        with transaction.atomic():
            sa = SocialAccount.objects.select_for_update().filter(
                provider=provider, provider_uid=provider_uid
            ).first()

            if sa:
                user = sa.user
            else:
                user = User.objects.filter(email__iexact=email).first() if email else None
                if not user:
                    candidate_email = email or f"{provider}_{provider_uid}@example.local"
                    candidate_nickname = profile.get("nickname") or profile.get("name") or ""

                    # ✅ 모델에 존재하는 필드만 세팅
                    user = User(email=candidate_email)

                    # username 필드가 있다면 email로 채움
                    if hasattr(User, "username") and not getattr(user, "username", None):
                        user.username = candidate_email

                    if hasattr(User, "nickname"):
                        user.nickname = candidate_nickname
                    if hasattr(User, "phone_number"):
                        user.phone_number = ""
                    if hasattr(User, "address"):
                        user.address = ""

                    user.set_unusable_password()  # 소셜 전용 계정
                    user.save()

                fields = {f.name for f in SocialAccount._meta.get_fields()}
                create_kwargs = {
                    "user": user,
                    "provider": provider,
                    "provider_uid": provider_uid,
                }

                def put_profile(field_name: str):
                    # 필드 타입 확인 후 JSONField면 dict 그대로, 그 외(TextField 등)이면 문자열로
                    field = SocialAccount._meta.get_field(field_name)
                    if isinstance(field, dj_models.JSONField):
                        create_kwargs[field_name] = profile
                    else:
                        create_kwargs[field_name] = json.dumps(profile, ensure_ascii=False)

                # 우선순위대로 존재하는 필드에 저장
                if "raw_profile_json" in fields:
                    put_profile("raw_profile_json")
                elif "raw_profile" in fields:
                    put_profile("raw_profile")
                elif "extra_data" in fields:
                    put_profile("extra_data")
                # 아무 필드도 없으면, 프로필 저장은 생략(계정 연결만 생성)

                SocialAccount.objects.create(**create_kwargs)

        # 6) 토큰 응답 + refresh 쿠키
        pair = issue_jwt_pair(user)
        resp_ser = TokenPairResponseSerializer(instance=pair)
        resp = Response(resp_ser.data, status=200)
        set_refresh_cookie(resp, pair["refresh"])
        return resp


# ---- 소셜 연동 해제 ----
class SocialUnlinkView(generics.DestroyAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = serializers.Serializer  # 스키마용 더미

    def delete(self, request, provider: str):
        acc = SocialAccount.objects.filter(user=request.user, provider=provider.lower()).first()
        if not acc:
            return Response({"detail": "not linked"}, status=404)
        acc.delete()
        return Response(status=204)
