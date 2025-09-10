from django.urls import path
from .views_categories import CategoryListCreateAPI, CategoryDetailAPI

urlpatterns = [
    path("", CategoryListCreateAPI.as_view()),
    path("<int:category_id>", CategoryDetailAPI.as_view()),
]
