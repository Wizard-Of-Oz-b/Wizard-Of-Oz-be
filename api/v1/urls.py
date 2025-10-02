# api/v1/urls.py
from django.urls import include, path

from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework_simplejwt.views import TokenRefreshView

from domains.accounts.jwt import EmailTokenObtainPairView  # ← 커스텀 토큰 뷰

urlpatterns = [
    # --- Auth ---
    path("auth/", include(("domains.accounts.urls_auth", "accounts_auth"))),
    path("auth/token/", EmailTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path(
        "auth/",
        include(
            ("domains.accounts.urls_auth", "accounts_auth"), namespace="accounts_auth"
        ),
    ),
    # --- Users ---
    path("users/", include(("domains.accounts.urls_users", "accounts_users"))),
    # --- Catalog ---
    path(
        "categories/",
        include(("domains.catalog.urls_categories", "catalog_categories")),
    ),
    path("products/", include(("domains.catalog.urls_products", "catalog_products"))),
    path("product-stocks/", include(("domains.catalog.urls_stock", "catalog_stocks"))),
    # --- Reviews ---
    # (상품별 리뷰는 products 쪽에만 등록하므로 여기선 전역 리뷰 전용 라우트만)
    path("reviews/", include(("domains.reviews.urls", "reviews"))),  # 개별 리뷰 상세용
    # --- Orders ---
    path(
        "orders/", include(("domains.orders.urls_shipping", "orders_shipping"))
    ),  # shipping URLs with orders/ prefix
    path("orders/", include(("domains.orders.urls", "orders"))),
    # --- Payments ---
    path("payments/toss/", include(("domains.payments.urls_toss", "payments_toss"))),
    # --- Carts ---
    path("carts/", include(("domains.carts.urls", "carts"))),
    # --- API Docs ---
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    # --- Admin (관리자 API) ---
    # 여기 안에 users/categories/products/product-stocks/product-images/orders 등이 라우터로 등록됨
    path("admin/", include(("domains.staff.urls_admin", "staff_admin"))),
    # --- Others ---
    path("", include("domains.wishlists.urls")),
    path("", include("domains.accounts.urls_addresses")),
]
