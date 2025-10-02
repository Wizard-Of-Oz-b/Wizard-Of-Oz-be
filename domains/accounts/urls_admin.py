# domains/accounts/urls_admin.py
from django.urls import path

from .views import UserDetailAdminAPI, UserListAdminAPI

app_name = "accounts_admin"

urlpatterns = [
    path("users/", UserListAdminAPI.as_view(), name="admin-user-list"),
    path(
        "users/<int:user_id>/", UserDetailAdminAPI.as_view(), name="admin-user-detail"
    ),
]
