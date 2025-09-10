from django.urls import path, include
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

urlpatterns = [
    # JWT
    path("auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),

    path("auth/", include("domains.accounts.urls")),
    path("users/", include("domains.accounts.urls")),      # 초기엔 같은 urls에 두셔도 돼요
    path("categories/", include("domains.catalog.urls_categories")),
    path("products/", include("domains.catalog.urls_products")),
    path("products/", include("domains.catalog.urls")),
    path("reviews/", include("domains.reviews.urls")),
    path("purchases/", include("domains.orders.urls")),
    path("admins/", include("domains.staff.urls")),
    path("admin-logs/", include("domains.staff.urls")),
    path("categories/", include("domains.catalog.urls_categories")),
    path("products/", include("domains.catalog.urls_products")),
    path("", include("domains.reviews.urls")),   # products/{id}/reviews, reviews/{id}
    path("", include("domains.orders.urls")),    # purchases...
]
