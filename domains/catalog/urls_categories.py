from django.urls import path
from .views_categories import CategoryListCreateAPI, CategoryDetailAPI

app_name = "catalog_categories"

urlpatterns = [
    # GET /api/v1/categories?parent_id=&tree=
    # POST /api/v1/categories
    path("", CategoryListCreateAPI.as_view(), name="list-create"),

    # GET /api/v1/categories/{id}
    # PATCH /api/v1/categories/{id}
    # DELETE /api/v1/categories/{id}
    path("<int:category_id>/", CategoryDetailAPI.as_view(), name="detail"),
]
