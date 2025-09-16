# api/v1/urls.py
from django.urls import path, include
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    # Auth
    path("auth/", include(("domains.accounts.urls_auth", "accounts_auth"))),
    path("auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),

    # Users
    path("users/", include(("domains.accounts.urls_users", "accounts_users"))),

    # Catalog
    path("categories/", include(("domains.catalog.urls_categories", "catalog_categories"))),
    path("products/", include(("domains.catalog.urls_products", "catalog_products"))),
    path("product-stocks/", include(("domains.catalog.urls_stock", "catalog_stocks"))),


    # Reviews (상품별 리뷰는 위 products urls 쪽에만 등록! 중복 금지)
    path("reviews/", include(("domains.reviews.urls", "reviews"))),

    # Orders
    path("orders/", include(("domains.orders.urls", "orders"))),


    path("payments/toss/", include(("domains.payments.urls_toss", "payments_toss"))),

    path("carts/", include("domains.carts.urls")),
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("docs/",   SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),


]
