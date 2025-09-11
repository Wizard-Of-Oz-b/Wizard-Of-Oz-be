# api/v1/urls.py
from django.urls import path, include

urlpatterns = [
    path("", include("domains.accounts.urls")),          # /auth..., /users/me...
    path("categories/", include("domains.catalog.urls")),# ← 하나로
    path("products/",   include("domains.catalog.urls")),# ← 하나로
    path("reviews/", include("domains.reviews.urls")),
    path("purchases/", include("domains.orders.urls")),
    path("admins/",     include("domains.staff.urls")),
    path("admin-logs/", include("domains.staff.urls")),
]
