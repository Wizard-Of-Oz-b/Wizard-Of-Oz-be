from django.urls import path
from .views import UserListAdminAPI, UserDetailAdminAPI

app_name = "accounts_admin"

urlpatterns = [
    path("users/", UserListAdminAPI.as_view(), name="admin-user-list"),
    path("users/<int:user_id>/", UserDetailAdminAPI.as_view(), name="admin-user-detail"),
]
