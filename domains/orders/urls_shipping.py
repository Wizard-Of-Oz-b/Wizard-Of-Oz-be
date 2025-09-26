from django.urls import path
from .views_shipping import UpdatePurchaseAddressAPI, BulkUpdateShippingAddressAPI
from .views import CheckoutAPI  # 올바른 CheckoutAPI import

urlpatterns = [
    path("checkout/", CheckoutAPI.as_view(), name="checkout"),  # 올바른 CheckoutAPI 사용
    path("purchases/<uuid:purchase_id>/shipping-address/", UpdatePurchaseAddressAPI.as_view(), name="purchase-address"),
    path("purchases/bulk-shipping-address/", BulkUpdateShippingAddressAPI.as_view(), name="bulk-shipping-address"),
]
