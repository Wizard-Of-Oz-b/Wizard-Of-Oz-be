# domains/accounts/urls_users.py
from django.urls import path
from .views import MeView, MySocialAccountListAPI, MySocialAccountDeleteAPI

app_name = "accounts_users"

urlpatterns = [
    # 내 정보
    path("me/", MeView.as_view(), name="me"),

    # 내 소셜 연동
    path("me/social-accounts/", MySocialAccountListAPI.as_view(), name="my-social-accounts"),
    path("me/social-accounts/<int:social_id>/", MySocialAccountDeleteAPI.as_view(), name="my-social-account-delete"),
]
