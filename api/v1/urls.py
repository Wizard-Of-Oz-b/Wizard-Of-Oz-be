# api/v1/urls.py
from django.urls import path, include
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

urlpatterns = [
    # Auth
    path("auth/", include(("domains.accounts.urls_auth", "accounts_auth"))),
    path("auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),

    # Users
    path("users/", include(("domains.accounts.urls_users", "accounts_users"))),

    # Catalog
    path("categories/", include(("domains.catalog.urls_categories", "catalog_categories"))),
    path("products/",   include(("domains.catalog.urls_products", "catalog_products"))),

    # Reviews
    path("reviews/", include(("domains.reviews.urls", "reviews"))),

    # Orders
    path("orders/", include(("domains.orders.urls", "orders"))),

    # Staff/Admin (API용 관리 엔드포인트)  → /api/v1/admin/...
    path("admin/", include(("domains.staff.urls", "staff"))),
]
