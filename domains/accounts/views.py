# domains/accounts/views.py
from django.contrib.auth import get_user_model
from rest_framework import permissions, status, generics
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from drf_spectacular.utils import extend_schema, OpenApiResponse

from .serializers import (
    RegisterSerializer, LoginSerializer, MeSerializer,
    EmptySerializer, LoginRequestSerializer,
    TokenPairResponseSerializer,
)
from .utils import refresh_cookie_kwargs  # ✅ 여기서 가져옴

User = get_user_model()


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

        from django.conf import settings
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
            user = User.objects.get(id=refresh["user_id"])
            new_refresh = RefreshToken.for_user(user)

            from django.conf import settings
            resp = Response({"access": new_access, "refresh": str(new_refresh)}, status=200)
            resp.set_cookie("refresh", str(new_refresh), **refresh_cookie_kwargs(settings.DEBUG))
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
        resp.delete_cookie("refresh", path="/api/v1/auth/")
        return resp


@extend_schema(responses={200: MeSerializer})
class MeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(MeSerializer(request.user).data)

    @extend_schema(request=MeSerializer, responses={200: MeSerializer})
    def patch(self, request):
        ser = MeSerializer(instance=request.user, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ser.data)

    @extend_schema(request=EmptySerializer, responses={204: OpenApiResponse(description="탈퇴 완료")})
    def delete(self, request):
        u = request.user
        if hasattr(u, "status"):
            u.status = "deleted"
        u.is_active = False
        u.save(update_fields=["is_active"] + (["status"] if hasattr(u, "status") else []))
        resp = Response(status=204)
        resp.delete_cookie("refresh", path="/api/v1/auth/")
        return resp
