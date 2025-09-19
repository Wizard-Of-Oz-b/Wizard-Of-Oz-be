from django.urls import path
from .views import (
    PurchaseListCreateAPI,
    PurchaseCreateAPI,
    PurchaseMeListAPI,
    PurchaseDetailAPI,
    PurchaseCancelAPI,
    PurchaseRefundAPI,
    CheckoutView, CheckoutAPI, OrderItemDetailAPI, OrderItemListAPI,
)

urlpatterns = [
    # Purchases
    path("purchases/",                      PurchaseListCreateAPI.as_view(),  name="purchase-list"),
    path("purchases/create/",               PurchaseCreateAPI.as_view(),      name="purchase-create"),
    path("purchases/me/",                   PurchaseMeListAPI.as_view(),      name="purchase-me"),
    path("purchases/<uuid:purchase_id>/",   PurchaseDetailAPI.as_view(),       name="purchase-detail"),
    path("purchases/<uuid:purchase_id>/cancel/", PurchaseCancelAPI.as_view(), name="purchase-cancel"),
    path("purchases/<uuid:purchase_id>/refund/", PurchaseRefundAPI.as_view(), name="purchase-refund"),

    # Checkout
    path("checkout/", CheckoutAPI.as_view(), name="checkout"),
# OrderItem 조회
    path("purchases/<uuid:purchase_id>/items/", OrderItemListAPI.as_view(), name="orderitem-list-by-order"),
    path("order-items/<uuid:item_id>/", OrderItemDetailAPI.as_view(), name="orderitem-detail"),
]
