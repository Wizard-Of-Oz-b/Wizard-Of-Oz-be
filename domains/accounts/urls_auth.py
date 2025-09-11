from django.urls import path
from .views import RegisterView, LoginView, LogoutView
from .views_social import SocialLoginView, SocialUnlinkView

app_name = "accounts_auth"

urlpatterns = [
    path("register", RegisterView.as_view(), name="register"),
    path("login",    LoginView.as_view(),    name="login"),
    path("logout",   LogoutView.as_view(),   name="logout"),
    path("social/<str:provider>/login",  SocialLoginView.as_view(),  name="social-login"),
    path("social/<str:provider>/unlink", SocialUnlinkView.as_view(), name="social-unlink"),
]
