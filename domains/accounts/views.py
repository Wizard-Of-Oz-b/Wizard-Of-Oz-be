# domains/accounts/views.py
from django.contrib.auth import get_user_model
from django.conf import settings

import django_filters as df
from django_filters.rest_framework import DjangoFilterBackend

from rest_framework import generics, permissions, status, filters, serializers
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiExample

from .models import SocialAccount
from .utils import refresh_cookie_kwargs
from .serializers import (
    RegisterSerializer,
    LoginSerializer,
    LoginRequestSerializer,
    TokenPairResponseSerializer,
    EmptySerializer,
    MeSerializer,
    MeUpdateSerializer,
    SocialAccountSerializer,
)

User = get_user_model()


# ---------- 인증/토큰 ----------
@extend_schema(
    request=RegisterSerializer,
    responses={201: OpenApiResponse(description="회원가입 완료")},
)
class RegisterView(generics.CreateAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = RegisterSerializer


@extend_schema(
    request=LoginRequestSerializer,
    responses={200: TokenPairResponseSerializer},  # access + refresh
)
class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        ser = LoginSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user = ser.validated_data["user"]

        refresh = RefreshToken.for_user(user)
        access = str(refresh.access_token)

        resp = Response({"access": access, "refresh": str(refresh)}, status=status.HTTP_200_OK)
        resp.set_cookie("refresh", str(refresh), **refresh_cookie_kwargs(settings.DEBUG))
        return resp


@extend_schema(
    request=EmptySerializer,
    responses={200: TokenPairResponseSerializer},  # access + refresh
)
class RefreshView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        token = request.COOKIES.get("refresh")
        if not token:
            return Response({"detail": "No refresh cookie"}, status=400)
        try:
            refresh = RefreshToken(token)
            new_access = str(refresh.access_token)

            # ✅ Fixed 방식: 새로운 Access Token만 발급 (Refresh Token은 그대로 유지)
            resp = Response({"access": new_access}, status=200)

            # ✅ 쿠키 재설정 없음 (기존 Refresh Token 그대로 유지)
            # resp.set_cookie(...) 제거

            return resp
        except Exception:
            return Response({"detail": "Invalid refresh"}, status=401)


@extend_schema(
    request=EmptySerializer,
    responses={204: OpenApiResponse(description="로그아웃 완료")},
)
class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        token = request.COOKIES.get("refresh")
        if token:
            try:
                refresh = RefreshToken(token)
                refresh.blacklist()
            except Exception:
                pass
        resp = Response(status=204)
        # refresh_cookie_kwargs에서 path를 "/api/v1/auth/"로 설정했다는 가정 하에 동일 경로로 삭제
        resp.delete_cookie("refresh", path="/api/v1/auth/")
        return resp


# ---------- 내 프로필 ----------
class MeView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET    /api/v1/users/me/      내 프로필 조회
    PATCH  /api/v1/users/me/      이름/닉네임/전화/주소 수정 & (옵션) 비밀번호 변경
    DELETE /api/v1/users/me/      소프트 삭제(status=deleted, is_active=False)
    """
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "patch", "delete", "head", "options"]

    def get_object(self):
        return self.request.user

    def get_serializer_class(self):
        return MeUpdateSerializer if self.request.method == "PATCH" else MeSerializer

    @extend_schema(operation_id="GetMe", responses={200: MeSerializer})
    def get(self, *args, **kwargs):
        return super().get(*args, **kwargs)

    @extend_schema(operation_id="UpdateMe", request=MeUpdateSerializer, responses={200: MeSerializer})
    def patch(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return super().patch(request, *args, **kwargs)

    @extend_schema(operation_id="DeleteMe", responses={204: None})
    def delete(self, request, *args, **kwargs):
        user = self.get_object()
        user.status = "deleted"
        if hasattr(user, "is_active"):
            user.is_active = False
        update_fields = ["status", "updated_at"]
        if hasattr(user, "is_active"):
            update_fields.insert(1, "is_active")
        user.save(update_fields=update_fields)
        return Response(status=status.HTTP_204_NO_CONTENT)


# ---------- 내 소셜 연동 ----------
class MySocialAccountListAPI(generics.ListAPIView):
    """
    GET /api/v1/users/me/social-accounts/
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = SocialAccountSerializer
    queryset = SocialAccount.objects.none()

    def get_queryset(self):
        return SocialAccount.objects.filter(user=self.request.user).order_by("provider", "created_at")


class MySocialAccountDeleteAPI(generics.DestroyAPIView):
    """
    DELETE /api/v1/users/me/social-accounts/{social_id}/
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = SocialAccountSerializer
    lookup_url_kwarg = "social_id"

    def get_queryset(self):
        # 내 것만 삭제 가능
        return SocialAccount.objects.filter(user=self.request.user)


# ---------- 관리자용: 사용자 목록/조회 ----------
class UserFilter(df.FilterSet):
    email = df.CharFilter(field_name="email", lookup_expr="icontains")
    nickname = df.CharFilter(field_name="nickname", lookup_expr="icontains")
    status = df.CharFilter(field_name="status")
    created_from = df.IsoDateTimeFilter(field_name="created_at", lookup_expr="gte")
    created_to = df.IsoDateTimeFilter(field_name="created_at", lookup_expr="lte")

    class Meta:
        model = User
        fields = ["email", "nickname", "status", "created_from", "created_to"]


class UserListAdminAPI(generics.ListAPIView):
    """
    GET /api/v1/users/   (Admin)
      - ?email=, ?nickname=, ?status=, ?created_from=, ?created_to=
    """
    permission_classes = [permissions.IsAdminUser]  # is_staff=True(=admin)만 접근
    queryset = User.objects.all().order_by("-created_at")
    serializer_class = MeSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter, filters.SearchFilter]
    filterset_class = UserFilter
    search_fields = ["email", "nickname"]
    ordering_fields = ["created_at", "email"]


class UserDetailAdminAPI(generics.RetrieveAPIView):
    """
    GET /api/v1/users/{user_id}  (Admin)
    """
    permission_classes = [permissions.IsAdminUser]
    queryset = User.objects.all()
    serializer_class = MeSerializer
    lookup_url_kwarg = "user_id"




