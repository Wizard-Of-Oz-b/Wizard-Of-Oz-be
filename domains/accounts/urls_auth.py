from django.urls import path
from .views import RegisterView, LoginView, LogoutView, RefreshView
from .views_social import SocialLoginView, SocialUnlinkView

app_name = "accounts_auth"

urlpatterns = [
    # 슬래시 유무 모두 허용되도록 둘 다 등록 (리다이렉트/APPEND_SLASH 환경 차단)
    path("login", LoginView.as_view(), name="login"),
    path("login/", LoginView.as_view(), name="login_slash"),

    path("refresh", RefreshView.as_view(), name="refresh"),
    path("refresh/", RefreshView.as_view(), name="refresh_slash"),

    path("logout", LogoutView.as_view(), name="logout"),
    path("logout/", LogoutView.as_view(), name="logout_slash"),
    path("social/<str:provider>/login",  SocialLoginView.as_view(),  name="social-login"),
    path("social/<str:provider>/unlink", SocialUnlinkView.as_view(), name="social-unlink"),
]
