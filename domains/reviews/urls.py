from django.urls import path
from .views import ProductReviewListCreateAPI, ReviewDetailAPI

urlpatterns = [
    path("products/<int:product_id>/reviews", ProductReviewListCreateAPI.as_view()),
    path("reviews/<int:review_id>", ReviewDetailAPI.as_view()),
]
