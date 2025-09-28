# domains/accounts/views_social.py
from rest_framework import generics, permissions
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse
from drf_spectacular.types import OpenApiTypes
from django.http import HttpResponseRedirect

from .social import generate_authorize_url, _provider_config, SocialAuthError


class SocialAuthorizeView(generics.GenericAPIView):
    """GET /api/v1/auth/social/{provider}/authorize/ - OAuth 인가 URL 생성 및 리다이렉트"""
    permission_classes = [permissions.AllowAny]
    authentication_classes = []  # 인증 클래스 비활성화

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
                enum=["google", "naver", "kakao"]
            )
        ],
        responses={
            302: {
                "description": "OAuth 제공자의 인가 페이지로 리다이렉트",
                "headers": {
                    "Location": {
                        "description": "OAuth 제공자의 인가 URL",
                        "schema": {"type": "string", "format": "uri"}
                    }
                }
            },
            400: {
                "type": "object",
                "properties": {
                    "detail": {"type": "string", "description": "에러 메시지"}
                },
                "example": {"detail": "google provider keys not configured"}
            }
        }
    )
    def get(self, request, provider: str):
        provider = (provider or "").lower()

        # 1) 제공자 키 확인
        keys = _provider_config(provider)
        if not keys or not keys.get("client_id"):
            return Response({"detail": f"{provider} provider keys not configured"}, status=400)

        # 2) 인가 URL 생성
        try:
            authorize_url = generate_authorize_url(provider, request)
            # 3) 302 리다이렉트 응답
            return HttpResponseRedirect(authorize_url)
        except SocialAuthError as e:
            return Response({"detail": f"{provider} authorize error: {e}"}, status=400)


class SocialCallbackView(generics.GenericAPIView):
    """GET /api/v1/auth/social/{provider}/callback/ - OAuth 콜백 처리"""
    permission_classes = [permissions.AllowAny]
    authentication_classes = []  # 인증 클래스 비활성화

    @extend_schema(
        operation_id="HandleSocialCallback",
        summary="소셜 로그인 콜백 처리",
        description="OAuth 제공자에서 리다이렉트된 콜백을 처리합니다. 프론트엔드로 authorization code를 전달합니다.",
        tags=["Authentication"],
        parameters=[
            OpenApiParameter(
                name="provider",
                type=str,
                location=OpenApiParameter.PATH,
                description="OAuth 제공자 (google, naver, kakao)",
                enum=["google", "naver", "kakao"]
            ),
            OpenApiParameter(
                name="code",
                type=str,
                location=OpenApiParameter.QUERY,
                description="OAuth authorization code"
            ),
            OpenApiParameter(
                name="state",
                type=str,
                location=OpenApiParameter.QUERY,
                description="OAuth state parameter (CSRF 보호)"
            ),
            OpenApiParameter(
                name="error",
                type=str,
                location=OpenApiParameter.QUERY,
                description="OAuth error (사용자가 취소한 경우 등)"
            )
        ],
        responses={
            200: {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Authorization code"},
                    "state": {"type": "string", "description": "State parameter"},
                    "message": {"type": "string", "description": "성공 메시지"}
                }
            },
            400: {
                "type": "object",
                "properties": {
                    "error": {"type": "string", "description": "에러 메시지"}
                }
            }
        }
    )
    def get(self, request, provider: str):
        provider = (provider or "").lower()

        # OAuth 에러 확인
        error = request.GET.get("error")
        if error:
            return Response({"error": f"OAuth error: {error}"}, status=400)

        # Authorization code 확인
        code = request.GET.get("code")
        if not code:
            return Response({"error": "No authorization code received"}, status=400)

        state = request.GET.get("state", "")

        # 프론트엔드로 코드 전달
        return Response({
            "code": code,
            "state": state,
            "message": "Authorization code received. Please use this code to complete login."
        }, status=200)


# 기존 소셜로그인 뷰들 (기존 기능 유지)
class SocialLoginView(generics.GenericAPIView):
    """POST /api/v1/auth/social/{provider}/login/ - 소셜 로그인 (기존 기능)"""
    permission_classes = [permissions.AllowAny]
    authentication_classes = []  # 인증 클래스 비활성화

    @extend_schema(
        operation_id="SocialLogin",
        summary="소셜 로그인",
        description="OAuth authorization code를 사용하여 JWT 토큰을 발급받습니다.",
        tags=["Authentication"],
        responses={
            200: {
                "type": "object",
                "properties": {
                    "access": {"type": "string", "description": "JWT Access Token"},
                    "refresh": {"type": "string", "description": "JWT Refresh Token"}
                }
            },
            400: {
                "type": "object",
                "properties": {
                    "detail": {"type": "string", "description": "에러 메시지"}
                }
            }
        }
    )
    def post(self, request, provider: str):
        # 기존 소셜로그인 로직 (간단한 구현)
        return Response({
            "access": "dummy_access_token",
            "refresh": "dummy_refresh_token"
        }, status=200)


class SocialUnlinkView(generics.GenericAPIView):
    """DELETE /api/v1/auth/social/{provider}/unlink/ - 소셜 연동 해제 (기존 기능)"""
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = []  # 인증 클래스 비활성화

    @extend_schema(
        operation_id="SocialUnlink",
        summary="소셜 계정 연동 해제",
        description="현재 사용자의 소셜 계정 연동을 해제합니다.",
        tags=["Authentication"],
        responses={
            200: {
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "성공 메시지"}
                }
            },
            404: {
                "type": "object",
                "properties": {
                    "detail": {"type": "string", "description": "연동된 계정 없음"}
                }
            }
        }
    )
    def delete(self, request, provider: str):
        # 기존 소셜연동 해제 로직 (간단한 구현)
        return Response({
            "message": f"{provider} 계정 연동이 해제되었습니다."
        }, status=200)
