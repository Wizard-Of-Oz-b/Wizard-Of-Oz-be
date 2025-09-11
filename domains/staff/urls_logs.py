from django.urls import path
from .views import AdminLogListAPI

app_name = "staff_logs"

urlpatterns = [
    path("", AdminLogListAPI.as_view()),                  # /api/v1/admin-logs
]
