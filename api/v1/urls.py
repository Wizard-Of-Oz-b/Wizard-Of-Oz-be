from django.urls import path, include

urlpatterns = [
    path("auth/", include("domains.accounts.urls")),
    path("users/", include("domains.accounts.urls")),      # 초기엔 같은 urls에 두셔도 돼요
    path("categories/", include("domains.catalog.urls_categories")),
    path("products/", include("domains.catalog.urls")),
    path("reviews/", include("domains.reviews.urls")),
    path("purchases/", include("domains.orders.urls")),
    path("admins/", include("domains.staff.urls")),
    path("admin-logs/", include("domains.staff.urls")),
]
