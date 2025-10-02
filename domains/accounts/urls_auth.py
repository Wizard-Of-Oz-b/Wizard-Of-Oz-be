from django.urls import path

from .views import LoginView, LogoutView, RefreshView, RegisterView
from .views_social import (
    SocialAuthorizeView,
    SocialCallbackView,
    SocialLoginView,
    SocialUnlinkView,
)

app_name = "accounts_auth"

urlpatterns = [
    # 회원가입
    path("register/", RegisterView.as_view(), name="register"),
    # 로그인
    path("login/", LoginView.as_view(), name="login"),
    # 토큰 갱신
    path("refresh/", RefreshView.as_view(), name="refresh"),
    # 로그아웃
    path("logout/", LogoutView.as_view(), name="logout"),
    # 소셜 로그인 (기존 + 프론트엔드 요구사항 OAuth 플로우)
    path(
        "social/<str:provider>/authorize/",
        SocialAuthorizeView.as_view(),
        name="social-authorize",
    ),
    path(
        "social/<str:provider>/callback/",
        SocialCallbackView.as_view(),
        name="social-callback",
    ),
    path(
        "social/<str:provider>/login/", SocialLoginView.as_view(), name="social-login"
    ),
    path(
        "social/<str:provider>/unlink/",
        SocialUnlinkView.as_view(),
        name="social-unlink",
    ),
]
