from django.urls import path
from .views import AdminListCreateAPI, AdminDetailAPI

app_name = "staff_admins"

urlpatterns = [
    path("", AdminListCreateAPI.as_view()),               # /api/v1/admins
    path("<int:admin_id>/", AdminDetailAPI.as_view()),    # /api/v1/admins/{admin_id}
]
