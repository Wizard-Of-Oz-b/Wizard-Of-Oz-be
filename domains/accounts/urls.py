from django.urls import path


from .views import LoginView, LogoutView, MeView, RefreshView, RegisterView
from .views_social import SocialLoginView, SocialUnlinkView


urlpatterns = [
    # 기존 인증
    path("auth/register", RegisterView.as_view()),

    path("auth/login", LoginView.as_view()),
    path("auth/refresh", RefreshView.as_view()),
    path("auth/logout", LogoutView.as_view()),
    path("users/me", MeView.as_view()),


