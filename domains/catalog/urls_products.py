from django.urls import path
from .views_products import ProductListCreateAPI, ProductDetailAPI, ProductImagesAPI
from ..reviews.views import ProductReviewListCreateAPI

app_name = "catalog_products"

urlpatterns = [
    # GET  /api/v1/products/?q=&min_price=&max_price=&category_id=&is_active=&ordering=
    # POST /api/v1/products/
    path("", ProductListCreateAPI.as_view(), name="list-create"),

    # GET    /api/v1/products/<product_id>/
    # PATCH  /api/v1/products/<product_id>/
    # DELETE /api/v1/products/<product_id>/
    # ⚠️ UUID PK 사용 → <uuid:product_id>
    path("<uuid:product_id>/", ProductDetailAPI.as_view(), name="detail"),
    path("products/<uuid:product_id>/images/", ProductImagesAPI.as_view(), name="product-images"),

    # 상품 리뷰 (상품별 목록/작성)
    # GET/POST /api/v1/products/<product_id>/reviews/
    path(
        "products/<uuid:product_id>/reviews/",
        ProductReviewListCreateAPI.as_view(),
        name="product-reviews",
    ),
]
