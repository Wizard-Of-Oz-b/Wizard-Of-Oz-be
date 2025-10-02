from django.urls import path
from .views import RegisterView, LoginView, RefreshView, LogoutView, MeView
from .views_social import (  # ⬅️ 추가
    SocialAuthorizeView,
    SocialCallbackView,
    SocialLoginView,
    SocialUnlinkView,
)

urlpatterns = [
    # 기존 인증
    path("auth/register", RegisterView.as_view()),
    path("auth/login",    LoginView.as_view()),
    path("auth/refresh",  RefreshView.as_view()),
    path("auth/logout",   LogoutView.as_view()),
    path("users/me",      MeView.as_view()),

    # ✅ 소셜 인증 라우트 추가
    path("auth/social/<str:provider>/authorize/", SocialAuthorizeView.as_view()),
    path("auth/social/<str:provider>/callback/",  SocialCallbackView.as_view()),
    path("auth/social/<str:provider>/login/",     SocialLoginView.as_view()),
    path("auth/social/<str:provider>/unlink/",    SocialUnlinkView.as_view()),
]

