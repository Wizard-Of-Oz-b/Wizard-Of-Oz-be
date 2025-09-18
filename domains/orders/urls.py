from django.urls import path
from .views import (
    PurchaseListCreateAPI,
    PurchaseCreateAPI,
    PurchaseMeListAPI,
    PurchaseDetailAPI,
    PurchaseCancelAPI,
    PurchaseRefundAPI,
    CheckoutView,
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
    path("orders/checkout/", CheckoutView.as_view(), name="checkout"),
]
