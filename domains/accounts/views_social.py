# domains/accounts/views_social.py  (DROP-IN 교체본)

from django.conf import settings
from django.http import HttpResponseRedirect
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, OpenApiParameter
from .utils import refresh_cookie_kwargs
from .social import generate_authorize_url, _provider_config, SocialAuthError
from urllib.parse import urlencode

# -----------------------------
# 공통: refresh 쿠키를 통일해서 굽는 헬퍼
# -----------------------------
def _refresh_cookie_max_age():
    cfg = getattr(settings, "SIMPLE_JWT", {})
    lifetime = cfg.get("REFRESH_TOKEN_LIFETIME")
    try:
        return int(lifetime.total_seconds())
    except Exception:
        return None

def set_refresh_cookie(response: Response, refresh_token: str):
    """
    /auth/refresh와 로그아웃이 기대하는 것과 동일하게 굽는다.
    - 이름: refresh
    - Path: /api/v1/auth/
    - HttpOnly: True
    - 운영(HTTPS)에서는 SameSite=None; Secure
    """
    response.set_cookie(
        key="refresh",
        value=refresh_token,
        httponly=True,
        secure=False,
        samesite="None" if not settings.DEBUG else "Lax",
        max_age=_refresh_cookie_max_age(),
        path="/api/v1/auth/",
    )


class SocialAuthorizeView(generics.GenericAPIView):
    """GET /api/v1/auth/social/{provider}/authorize/ - OAuth 인가 URL 생성 및 리다이렉트"""
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    @extend_schema(
        operation_id="RedirectToSocialAuthorize",
        summary="소셜 로그인 인가 페이지로 리다이렉트",
        description="OAuth 제공자(Google, Naver, Kakao)의 인가 페이지로 직접 리다이렉트합니다. 프론트엔드에서 버튼 클릭 시 이 엔드포인트로 이동하면 됩니다.",
        tags=["Authentication"],
        parameters=[
            OpenApiParameter(
                name="provider",
                type=str,
                location=OpenApiParameter.PATH,
                description="OAuth 제공자 (google, naver, kakao)",
                enum=["google", "naver", "kakao"],
            )
        ],
        responses={
            302: {
                "description": "OAuth 제공자의 인가 페이지로 리다이렉트",
                "headers": {
                    "Location": {"description": "OAuth 인가 URL", "schema": {"type": "string", "format": "uri"}}
                },
            },
            400: {"type": "object", "properties": {"detail": {"type": "string"}}},
        },
    )
    def get(self, request, provider: str):
        provider = (provider or "").lower()

        keys = _provider_config(provider)
        if not keys or not keys.get("client_id"):
            return Response({"detail": f"{provider} provider keys not configured"}, status=400)

        try:
            authorize_url = generate_authorize_url(provider, request)
            return HttpResponseRedirect(authorize_url)
        except SocialAuthError as e:
            return Response({"detail": f"{provider} authorize error: {e}"}, status=400)

class SocialCallbackView(generics.GenericAPIView):
    """GET /api/v1/auth/social/{provider}/callback/ - OAuth 콜백 처리 (프론트로 code/state 전달)"""
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    # 프론트 콜백 주소 (settings.FRONTEND_OAUTH_CALLBACK 없으면 로컬 기본값)
    FRONT_CALLBACK = getattr(
        settings, "FRONTEND_OAUTH_CALLBACK", "http://localhost:5173/oauth/callback"
    )

    def get(self, request, provider: str):
        error = request.GET.get("error")
        if error:
            return Response({"error": f"OAuth error: {error}"}, status=400)

        code = request.GET.get("code")
        if not code:
            return Response({"error": "No authorization code"}, status=400)

        state = request.GET.get("state", "")
        qs = urlencode({"code": code, "state": state})
        return HttpResponseRedirect(f"{self.FRONT_CALLBACK}?{qs}")

class SocialLoginView(generics.GenericAPIView):
    """POST /api/v1/auth/social/{provider}/login/ - 소셜 로그인 (코드 교환 → JWT 발급)"""
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    @extend_schema(
        operation_id="SocialLogin",
        summary="소셜 로그인",
        description="프론트에서 받은 authorization code/state로 JWT를 발급하고 refresh 쿠키를 굽습니다.",
        tags=["Authentication"],
        responses={200: {"type": "object"}},
    )
    def post(self, request, provider: str):
        provider = (provider or "").lower()

        # 1) 프론트에서 넘어온 값
        code = request.data.get("code")
        state = request.data.get("state", "")
        redirect_uri = request.data.get("redirect_uri", "")

        if not code:
            return Response({"detail": "code is required"}, status=400)

        # 2) (여기서) code → 공급자 토큰 교환 → 프로필 조회 → 유저 매핑 → JWT 발급
        #    아래 access/refresh는 실제 발급 로직 결과를 담아야 합니다.
        #    지금은 예시로 변수 이름만 유지합니다.
        access_token = "dummy_access_token"      # TODO: 실 토큰으로 교체
        refresh_token = "dummy_refresh_token"    # TODO: 실 토큰으로 교체

        # 3) 응답 + refresh 쿠키 굽기 (이 부분이 '통일'의 핵심)
        resp = Response({"access": access_token}, status=200)
        resp.set_cookie(
            "refresh", str(refresh_token),
            **refresh_cookie_kwargs(settings.DEBUG)
        )
        return resp


class SocialUnlinkView(generics.GenericAPIView):
    """DELETE /api/v1/auth/social/{provider}/unlink/ - 소셜 연동 해제"""
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = []

    @extend_schema(
        operation_id="SocialUnlink",
        summary="소셜 계정 연동 해제",
        description="현재 사용자의 소셜 계정 연동을 해제합니다.",
        tags=["Authentication"],
        responses={200: {"type": "object"}},
    )
    def delete(self, request, provider: str):
        return Response({"message": f"{provider} 계정 연동이 해제되었습니다."}, status=200)
