# domains/accounts/urls.py
from django.urls import path
from .views_social import SocialLoginView, SocialUnlinkView
from .views import RegisterView, LoginView, RefreshView, LogoutView, MeView

urlpatterns = [
    # 기존 인증
    path("auth/register", RegisterView.as_view()),
    path("auth/login",    LoginView.as_view()),
    path("auth/refresh",  RefreshView.as_view()),
    path("auth/logout",   LogoutView.as_view()),
    path("users/me",      MeView.as_view()),

]
