from django.urls import path
from .views import (
    PurchaseListCreateAPI, PurchaseMeListAPI, PurchaseDetailAPI,
    PurchaseCancelAPI, PurchaseRefundAPI
)

urlpatterns = [
    path("purchases", PurchaseListCreateAPI.as_view()),                 # GET(Admin) / POST(Auth)
    path("purchases/me", PurchaseMeListAPI.as_view()),                  # GET(Auth)
    path("purchases/<int:purchase_id>", PurchaseDetailAPI.as_view()),   # GET(Owner/Admin)
    path("purchases/<int:purchase_id>/cancel", PurchaseCancelAPI.as_view()),  # PATCH(Owner/Admin)
    path("purchases/<int:purchase_id>/refund", PurchaseRefundAPI.as_view()),  # PATCH(Admin)
]
