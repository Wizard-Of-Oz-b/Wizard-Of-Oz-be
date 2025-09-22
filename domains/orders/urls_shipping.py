from django.urls import path
from .views_shipping import CheckoutAPI, UpdatePurchaseAddressAPI

urlpatterns = [
    path("orders/checkout/", CheckoutAPI.as_view(), name="checkout"),
    path("orders/purchases/<uuid:purchase_id>/shipping-address/", UpdatePurchaseAddressAPI.as_view(), name="purchase-address"),
]
