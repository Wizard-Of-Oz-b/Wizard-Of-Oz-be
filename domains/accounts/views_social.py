from django.conf import settings
from django.http import HttpResponseRedirect
from urllib.parse import urlencode

from rest_framework import generics, permissions, status, renderers, serializers
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiParameter

# 추가 import
import requests
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken

from .utils import refresh_cookie_kwargs
from .social import generate_authorize_url, _provider_config, SocialAuthError

User = get_user_model()


# ----- Serializer for POST /social/{provider}/login/ -----
class SocialLoginSerializer(serializers.Serializer):
    code = serializers.CharField()
    state = serializers.CharField(required=False, allow_blank=True)
    redirect_uri = serializers.CharField(required=False, allow_blank=True)

# ========== Provider helpers ==========

def _exchange_token(provider: str, code: str, redirect_uri: str = "", state: str = "") -> str:
    """
    code -> provider access_token  (SOCIAL_OAUTH 사용)
    """
    provider = (provider or "").lower()
    timeout = (5, 5)

    # settings에서 한 곳으로 관리
    cfg = _provider_config(provider)  # ← 이미 프로젝트에 있음
    if not cfg:
        raise ValueError(f"Unsupported provider: {provider}")

    client_id = cfg.get("client_id", "")
    client_secret = cfg.get("client_secret", "")
    default_redirect = cfg.get("redirect_uri", "")
    token_url = cfg.get("token_url", "")

    if not client_id or not token_url:
        raise ValueError(f"{provider} oauth config missing (client_id or token_url)")

    data = {
        "grant_type": "authorization_code",
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "redirect_uri": redirect_uri or default_redirect,
    }
    # 네이버만 state 필요
    if provider == "naver":
        data["state"] = state or ""

    r = requests.post(token_url, data=data, timeout=timeout)
    r.raise_for_status()
    j = r.json()
    # 구글/카카오/네이버 모두 access_token 키 사용
    return j["access_token"]


def _fetch_profile(provider: str, provider_access_token: str) -> dict:
    """
    provider access_token -> normalized profile dict: {email?, sub}
    SOCIAL_OAUTH.userinfo_url 사용
    """
    provider = (provider or "").lower()
    cfg = _provider_config(provider)
    if not cfg:
        raise ValueError(f"Unsupported provider: {provider}")

    userinfo_url = cfg.get("userinfo_url", "")
    if not userinfo_url:
        raise ValueError(f"{provider} oauth config missing (userinfo_url)")

    headers = {"Authorization": f"Bearer {provider_access_token}"}
    timeout = (5, 5)
    r = requests.get(userinfo_url, headers=headers, timeout=timeout)
    r.raise_for_status()
    j = r.json()

    if provider == "kakao":
        email = (j.get("kakao_account") or {}).get("email")
        sub = str(j.get("id"))
        return {"email": email, "sub": sub}

    if provider == "google":
        # 구글은 openid userinfo 스펙
        return {"email": j.get("email"), "sub": j.get("sub") or j.get("id")}

    if provider == "naver":
        res = j.get("response", {})
        return {"email": res.get("email"), "sub": res.get("id")}

    raise ValueError(f"Unsupported provider: {provider}")



def _get_or_create_user(provider: str, profile: dict) -> User:
    """
    profile(email?, sub) -> Django user
    이메일이 없을 수도 있으니(권한 미동의) provider_sub 기반 대체 이메일을 생성
    """
    provider = (provider or "").lower()
    email = profile.get("email") or f"{provider}_{profile.get('sub')}@ozshop.duckdns.org"
    username = email.split("@")[0]

    user, _ = User.objects.get_or_create(
        email=email,
        defaults={
            "username": username,
            "nickname": f"{provider}_user",
            "is_active": True,
        },
    )
    return user


# ----- /social/{provider}/authorize/ -----
class SocialAuthorizeView(generics.GenericAPIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    @extend_schema(
        operation_id="RedirectToSocialAuthorize",
        summary="소셜 로그인 인가 페이지로 리다이렉트",
        description="provider(google/naver/kakao)의 인가 페이지로 302 리다이렉트합니다.",
        tags=["Authentication"],
        parameters=[
            OpenApiParameter(
                name="provider",
                type=str,
                location=OpenApiParameter.PATH,
                enum=["google", "naver", "kakao"],
                description="OAuth 제공자"
            )
        ],
        responses={302: {"description": "리다이렉트"}},
    )
    def get(self, request, provider: str):
        provider = (provider or "").lower()
        keys = _provider_config(provider)
        if not keys or not keys.get("client_id"):
            return Response({"detail": f"{provider} provider keys not configured"}, status=400)
        try:
            url = generate_authorize_url(provider, request)
            return HttpResponseRedirect(url)
        except SocialAuthError as e:
            return Response({"detail": f"{provider} authorize error: {e}"}, status=400)


# ----- /social/{provider}/callback/ -----
class SocialCallbackView(generics.GenericAPIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    FRONT_CALLBACK = getattr(settings, "FRONTEND_OAUTH_CALLBACK",
                             "http://localhost:5173/oauth/callback")

    def get(self, request, provider: str):
        if (err := request.GET.get("error")):
            return Response({"error": f"OAuth error: {err}"}, status=400)

        code = request.GET.get("code")
        if not code:
            return Response({"error": "No authorization code"}, status=400)

        state = request.GET.get("state", "")
        p = (provider or "").lower()

        # 쿼리 + 경로 둘 다 만족시키도록 리다이렉트
        base = self.FRONT_CALLBACK.rstrip("/")
        qs = urlencode({"provider": p, "code": code, "state": state})
        # 경로 스타일(/oauth/callback/{provider}) + 쿼리(provider=..., code=..., state=...)
        location = f"{base}/{p}?{qs}"

        return HttpResponseRedirect(location)


# ----- /social/{provider}/login/ -----
class SocialLoginView(generics.GenericAPIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    serializer_class = SocialLoginSerializer
    # Browsable API가 폼 그리려고 serializer를 찾다가 터지는 걸 방지 + JSON만 반환
    renderer_classes = [renderers.JSONRenderer]

    @extend_schema(
        operation_id="SocialLogin",
        summary="소셜 로그인 (코드 교환 → JWT 발급)",
        description="프론트에서 받은 authorization code/state로 JWT를 발급하고 refresh 쿠키를 굽습니다.",
        request=SocialLoginSerializer,
        tags=["Authentication"],
        responses={200: {"type": "object"}},
    )
    def post(self, request, provider: str):
        provider = (provider or "").lower()
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)

        code = ser.validated_data["code"]
        state = ser.validated_data.get("state", "")
        redirect_uri = ser.validated_data.get("redirect_uri", "")

        try:
            # 1) code -> provider access_token
            provider_access = _exchange_token(provider, code, redirect_uri, state)

            # 2) provider access_token -> profile
            profile = _fetch_profile(provider, provider_access)

            # 3) profile -> user 매핑/생성
            user = _get_or_create_user(provider, profile)

            # 4) JWT 발급 + refresh 쿠키 굽기
            refresh = RefreshToken.for_user(user)
            access_token = str(refresh.access_token)

            resp = Response({"access": access_token}, status=200)
            # 프로젝트 공통 쿠키정책 사용
            resp.set_cookie("refresh", str(refresh), **refresh_cookie_kwargs(settings.DEBUG))
            return resp

        except requests.HTTPError as e:
            # provider API 호출 실패
            return Response(
                {"detail": f"{provider} token/profile http error", "info": str(e)},
                status=400,
            )
        except Exception as e:
            # 기타 오류 (500 대신 400으로 내려 프론트 디버깅 용이)
            return Response(
                {"detail": f"social-login error: {e.__class__.__name__}: {e}"},
                status=400,
            )


# ----- /social/{provider}/unlink/ -----
class SocialUnlinkView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = []

    @extend_schema(
        operation_id="SocialUnlink",
        summary="소셜 계정 연동 해제",
        tags=["Authentication"],
        responses={200: {"type": "object"}},
    )
    def delete(self, request, provider: str):
        return Response({"message": f"{provider} 계정 연동이 해제되었습니다."}, status=200)

