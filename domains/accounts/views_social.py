# domains/accounts/views_social.py

from django.conf import settings
from django.http import HttpResponseRedirect
from rest_framework import generics, permissions, status, renderers, serializers
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiParameter
from urllib.parse import urlencode

from .utils import refresh_cookie_kwargs
from .social import generate_authorize_url, _provider_config, SocialAuthError


# ----- Serializer for POST /social/{provider}/login/ -----
class SocialLoginSerializer(serializers.Serializer):
    code = serializers.CharField()
    state = serializers.CharField(required=False, allow_blank=True)
    redirect_uri = serializers.CharField(required=False, allow_blank=True)


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

        # TODO: 여기서 실제로 provider 별 토큰 교환 + 프로필 조회 + 유저 매핑 + JWT 발급
        access_token = "dummy_access_token"      # 실제 access로 대체
        refresh_token = "dummy_refresh_token"    # 실제 refresh로 대체

        resp = Response({"access": access_token}, status=200)
        # 우리 프로젝트의 쿠키 정책과 동일하게 굽기
        resp.set_cookie("refresh", str(refresh_token), **refresh_cookie_kwargs(settings.DEBUG))
        return resp


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

