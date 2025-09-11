from django.urls import path
from .views import MeView

app_name = "accounts_users"

urlpatterns = [
    path("me", MeView.as_view(), name="me"),
]
