# domains/catalog/urls_products.py
from django.urls import path
from .views_products import ProductListCreateAPI, ProductDetailAPI

urlpatterns = [
    path("", ProductListCreateAPI.as_view()),                 # /api/v1/products
    path("<int:product_id>", ProductDetailAPI.as_view()),     # /api/v1/products/{id}
]
