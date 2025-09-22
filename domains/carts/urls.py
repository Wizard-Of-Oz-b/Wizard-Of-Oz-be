from django.urls import path
from .views import MyCartView, CartItemAddView, CartItemDeleteByProductOptionAPI, CartItemDetailView

urlpatterns = [
    path("me/", MyCartView.as_view(), name="cart-me"),
    path("items/", CartItemAddView.as_view(), name="cartitem-add"),
    path("items/<uuid:item_id>/", CartItemDetailView.as_view(), name="cartitem-detail"),
    path(
        "items/by-product/<uuid:product_id>/",
        CartItemDeleteByProductOptionAPI.as_view(),
        name="cart-item-delete-by-product-option",
    ),
]
