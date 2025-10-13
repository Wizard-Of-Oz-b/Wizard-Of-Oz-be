from typing import Any
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import HttpResponseRedirect

from drf_spectacular.utils import OpenApiParameter, extend_schema
from requests.exceptions import RequestException
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from .models import SocialAccount
from .social import (
    SocialAuthError,
    _provider_config,
    exchange_code_for_tokens,
    fetch_userinfo,
    generate_authorize_url,
)
User = get_user_model()


# ───────────────────────────────────────────────
# refresh 쿠키 유틸
# ───────────────────────────────────────────────
def _refresh_cookie_max_age() -> int | None:
    cfg = getattr(settings, "SIMPLE_JWT", {})
    lifetime = cfg.get("REFRESH_TOKEN_LIFETIME")
    try:
        return int(lifetime.total_seconds())
    except Exception:
        return None


def set_refresh_cookie(response: Response, refresh_token: str) -> None:
    response.set_cookie(
        key="refresh",
        value=refresh_token,
        httponly=True,
        secure=not settings.DEBUG,
        samesite="None" if not settings.DEBUG else "Lax",
        max_age=_refresh_cookie_max_age(),
        path="/api/v1/auth/",
    )


# ───────────────────────────────────────────────
# 인가 URL
# ───────────────────────────────────────────────
class SocialAuthorizeView(generics.GenericAPIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes: list[Any] = []

    @extend_schema(
        operation_id="RedirectToSocialAuthorize",
        summary="소셜 로그인 인가 URL로 리다이렉트",
        parameters=[
            OpenApiParameter(
                name="provider",
                type=str,
                location=OpenApiParameter.PATH,
                enum=["google", "naver", "kakao"],
            )
        ],
    )
    def get(self, request, provider: str):
        provider = (provider or "").lower()
        keys = _provider_config(provider)
        if not keys or not keys.get("client_id"):
            return Response(
                {"detail": f"{provider} provider keys not configured"}, status=400
            )

        try:
            authorize_url = generate_authorize_url(provider, request)
            return HttpResponseRedirect(authorize_url)
        except SocialAuthError as e:
            return Response({"detail": f"{provider} authorize error: {e}"}, status=400)


# ───────────────────────────────────────────────
# 콜백 처리
# ───────────────────────────────────────────────
class SocialCallbackView(generics.GenericAPIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes: list[Any] = []

    FRONT_CALLBACK = getattr(
        settings, "FRONTEND_OAUTH_CALLBACK", "http://localhost:5173/oauth/callback"
    )

    def get(self, request, provider: str):
        if request.GET.get("error"):
            return Response(
                {"error": f"OAuth error: {request.GET.get('error')}"}, status=400
            )
        code = request.GET.get("code")
        if not code:
            return Response({"error": "No authorization code"}, status=400)

        state = request.GET.get("state", "")
        qs = urlencode({"code": code, "state": state})
        return HttpResponseRedirect(f"{self.FRONT_CALLBACK}?{qs}")


# ───────────────────────────────────────────────
# 소셜 로그인
# ───────────────────────────────────────────────
class SocialLoginView(generics.GenericAPIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes: list[Any] = []

    @extend_schema(
        operation_id="SocialLogin",
        summary="소셜 로그인 (JWT 발급)",
        description="authorization code/state로 소셜 로그인하고 JWT를 발급합니다.",
        tags=["Authentication"],
        responses={200: {"type": "object"}},
    )
    def post(self, request, provider: str):
        provider = (provider or "").lower()
        code = request.data.get("code")
        state = request.data.get("state", "")
        redirect_uri = request.data.get("redirect_uri", "")

        if not code:
            return Response({"detail": "code is required"}, status=400)

        # OAuth 토큰 교환
        try:
            token_data = exchange_code_for_tokens(provider, code, redirect_uri, state)
            provider_access = token_data["access_token"]
        except (SocialAuthError, RequestException) as e:
            return Response({"detail": f"OAuth token exchange failed: {e}"}, status=400)

        # 사용자 프로필 조회
        try:
            userinfo = fetch_userinfo(provider, provider_access)
        except (SocialAuthError, RequestException) as e:
            return Response({"detail": f"Failed to fetch userinfo: {e}"}, status=400)

        email = userinfo.get("email")
        if not email:
            return Response({"detail": "email not provided by provider"}, status=400)

        # 유저 매핑 / 생성
        user = User.objects.filter(email=email).first()
        if not user:
            user = User.objects.create_user(
                email=email,
                username=userinfo.get("nickname") or email.split("@")[0],
                first_name=userinfo.get("name") or "",
            )

        # SocialAccount 연결
        SocialAccount.objects.update_or_create(
            user=user,
            provider=provider,
            defaults={
                "provider_uid": userinfo.get("provider_uid", ""),
                "email": email,
            },
        )

        # JWT 발급
        refresh = RefreshToken.for_user(user)
        access = str(refresh.access_token)

        # 응답
        resp = Response({"access": access}, status=status.HTTP_200_OK)
        set_refresh_cookie(resp, str(refresh))
        return resp


# ───────────────────────────────────────────────
# 소셜 계정 연결 해제
# ───────────────────────────────────────────────
class SocialUnlinkView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes: list[Any] = []

    @extend_schema(
        operation_id="SocialUnlink",
        summary="소셜 계정 연동 해제",
        description="현재 사용자의 소셜 계정을 해제합니다.",
        tags=["Authentication"],
    )
    def delete(self, request, provider: str):
        return Response(
            {"message": f"{provider} 계정 연동이 해제되었습니다."}, status=200
        )
