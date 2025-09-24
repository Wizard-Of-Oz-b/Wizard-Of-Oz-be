# domains/catalog/urls_products.py
from django.urls import path
from .views_products import ProductListCreateAPI, ProductDetailAPI, ProductImagesAPI
from ..reviews.views import ProductReviewListCreateAPI

app_name = "catalog_products"

urlpatterns = [
    # /api/v1/products/
    path("", ProductListCreateAPI.as_view(), name="list-create"),

    # /api/v1/products/<product_id>/
    path("<uuid:product_id>/", ProductDetailAPI.as_view(), name="detail"),

    # /api/v1/products/<product_id>/images/
    path("<uuid:product_id>/images/", ProductImagesAPI.as_view(), name="product-images"),

    # /api/v1/products/<product_id>/reviews/
    path("<uuid:product_id>/reviews/", ProductReviewListCreateAPI.as_view(), name="product-reviews"),
]
