# domains/orders/urls.py
from django.urls import path
from .views import (
    PurchaseListCreateAPI, PurchaseMeListAPI, PurchaseDetailAPI,
    PurchaseCancelAPI, PurchaseRefundAPI
)

app_name = "orders"

urlpatterns = [
    # GET(Admin) / POST(Auth) : /api/v1/orders/
    path("", PurchaseListCreateAPI.as_view(), name="list-create"),

    # GET(Auth) : /api/v1/orders/me/
    path("me/", PurchaseMeListAPI.as_view(), name="me"),

    # GET(Owner/Admin) : /api/v1/orders/<id>/
    path("<int:purchase_id>/", PurchaseDetailAPI.as_view(), name="detail"),

    # PATCH(Owner/Admin) : /api/v1/orders/<id>/cancel/
    path("<int:purchase_id>/cancel/", PurchaseCancelAPI.as_view(), name="cancel"),

    # PATCH(Admin) : /api/v1/orders/<id>/refund/
    path("<int:purchase_id>/refund/", PurchaseRefundAPI.as_view(), name="refund"),
]
