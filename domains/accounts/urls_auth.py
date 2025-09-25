from django.urls import path
from .views import RegisterView, LoginView, LogoutView, RefreshView
from .views_social import SocialLoginView, SocialUnlinkView

app_name = "accounts_auth"

urlpatterns = [
    # 회원가입
    path("register", RegisterView.as_view(), name="register"),
    path("register/", RegisterView.as_view(), name="register_slash"),

    # 로그인
    path("login", LoginView.as_view(), name="login"),
    path("login/", LoginView.as_view(), name="login_slash"),

    # 토큰 갱신
    path("refresh", RefreshView.as_view(), name="refresh"),
    path("refresh/", RefreshView.as_view(), name="refresh_slash"),

    # 로그아웃
    path("logout", LogoutView.as_view(), name="logout"),
    path("logout/", LogoutView.as_view(), name="logout_slash"),

    # 소셜 로그인
    path("social/<str:provider>/login",  SocialLoginView.as_view(),  name="social-login"),
    path("social/<str:provider>/unlink", SocialUnlinkView.as_view(), name="social-unlink"),
]
