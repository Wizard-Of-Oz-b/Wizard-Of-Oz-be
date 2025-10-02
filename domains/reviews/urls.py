# domains/reviews/urls.py
from django.urls import path

from .views import ReviewDetailAPI

app_name = "reviews"

urlpatterns = [
    # /api/v1/reviews/<review_id>/
    path("<uuid:review_id>/", ReviewDetailAPI.as_view(), name="detail"),
]
