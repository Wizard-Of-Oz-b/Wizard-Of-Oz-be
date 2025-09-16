# domains/orders/urls.py
from django.urls import path
from .views import (
    PurchaseListCreateAPI,
    PurchaseMeListAPI,
    PurchaseDetailAPI,
    PurchaseCancelAPI,
    PurchaseRefundAPI,
    CheckoutView,
    # PurchaseCreateAPI,  # ← 별도 POST 전용 엔드포인트가 필요하면 주석 해제하고 아래에 추가하세요.
)

app_name = "orders"

urlpatterns = [
    # GET (admin) / POST (auth): /api/v1/orders/
    path("", PurchaseListCreateAPI.as_view(), name="list-create"),

    # GET (auth): /api/v1/orders/me/
    path("me/", PurchaseMeListAPI.as_view(), name="me"),

    # GET (owner/admin): /api/v1/orders/<purchase_id>/
    path("<int:purchase_id>/", PurchaseDetailAPI.as_view(), name="detail"),

    # PATCH (owner/admin): /api/v1/orders/<purchase_id>/cancel/
    path("<int:purchase_id>/cancel/", PurchaseCancelAPI.as_view(), name="cancel"),

    # PATCH (admin): /api/v1/orders/<purchase_id>/refund/
    path("<int:purchase_id>/refund/", PurchaseRefundAPI.as_view(), name="refund"),

    path("checkout/", CheckoutView.as_view(), name="orders-checkout"),
]

# 필요 시 별도 POST 전용 경로
# urlpatterns += [
#     path("create/", PurchaseCreateAPI.as_view(), name="create"),
# ]
