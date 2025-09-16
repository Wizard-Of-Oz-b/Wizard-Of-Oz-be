from django.urls import path
from .views import MyCartView, CartItemAddView, CartItemDetailView

urlpatterns = [
    path("me/", MyCartView.as_view(), name="cart-me"),
    path("items/", CartItemAddView.as_view(), name="cartitem-add"),
    path("items/<uuid:item_id>/", CartItemDetailView.as_view(), name="cartitem-detail"),
]
