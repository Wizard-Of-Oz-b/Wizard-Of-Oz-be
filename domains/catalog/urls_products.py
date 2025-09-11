from django.urls import path
from .views_products import ProductListCreateAPI, ProductDetailAPI
from ..reviews.views import ProductReviewListCreateAPI

app_name = "catalog_products"

urlpatterns = [
    # GET /api/v1/products?q=&min_price=&max_price=&category_id=&is_active=&ordering=
    # POST /api/v1/products
    path("", ProductListCreateAPI.as_view(), name="list-create"),

    # GET /api/v1/products/{id}
    # PATCH /api/v1/products/{id}
    # DELETE /api/v1/products/{id}
    path("<int:product_id>/", ProductDetailAPI.as_view(), name="detail"),
    path("<int:product_id>/reviews/", ProductReviewListCreateAPI.as_view()),  # ← 추가

]
