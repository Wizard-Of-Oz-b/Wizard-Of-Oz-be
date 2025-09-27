from django.urls import path
from .views import (
    PurchaseListCreateAPI,
    PurchaseCreateAPI,
    PurchaseMeListAPI,
    PurchaseMeReadyListAPI,
    PurchaseDetailAPI,
    PurchaseCancelAPI,
    PurchaseRefundAPI,
    CheckoutView, CheckoutAPI, OrderItemDetailAPI, OrderItemListAPI,
)
from .views_shipping import UpdateAllReadyOrdersShippingAddressAPI

urlpatterns = [
    # Purchases
    path("purchases/",                      PurchaseListCreateAPI.as_view(),  name="purchase-list"),
    path("purchases/create/",               PurchaseCreateAPI.as_view(),      name="purchase-create"),
    path("purchases/me/",                   PurchaseMeListAPI.as_view(),      name="purchase-me"),
    path("purchases/me/ready/",             PurchaseMeReadyListAPI.as_view(), name="purchase-me-ready"),
    path("purchases/<uuid:purchase_id>/",   PurchaseDetailAPI.as_view(),       name="purchase-detail"),
    path("purchases/<uuid:purchase_id>/cancel/", PurchaseCancelAPI.as_view(), name="purchase-cancel"),
    path("purchases/<uuid:purchase_id>/refund/", PurchaseRefundAPI.as_view(), name="purchase-refund"),

    # Checkout (moved to urls_shipping.py)
    
    # Shipping Address
    path("purchases/update-all-ready-shipping-address/", UpdateAllReadyOrdersShippingAddressAPI.as_view(), name="update-all-ready-shipping-address"),
    
# OrderItem 조회
    path("purchases/<uuid:purchase_id>/items/", OrderItemListAPI.as_view(), name="orderitem-list-by-order"),
    path("order-items/<uuid:item_id>/", OrderItemDetailAPI.as_view(), name="orderitem-detail"),
]
