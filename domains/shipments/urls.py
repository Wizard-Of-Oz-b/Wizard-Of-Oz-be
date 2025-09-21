from django.urls import path
from .views import (
    ShipmentsListAPI, ShipmentDetailAPI, ShipmentSyncAPI,
    ShipmentWebhookAPI, RegisterShipmentAPI
)

app_name = "shipments"

urlpatterns = [
    path("", ShipmentsListAPI.as_view(), name="shipment-list"),

    # ✅ 정적 경로들 먼저
    path("sync/", ShipmentSyncAPI.as_view(), name="shipment-sync"),
    path("register/", RegisterShipmentAPI.as_view(), name="shipment-register"),
    path("webhooks/<str:carrier>/", ShipmentWebhookAPI.as_view(), name="shipment-webhook"),

    # ✅ 그 다음에 동적 경로
    path("<uuid:id>/", ShipmentDetailAPI.as_view(), name="shipment-detail"),

    # ✅ 제일 마지막: 임시 백업 패턴(문제 원인이던 catch-all이므로 맨 끝)
    path("<str:id>/",  ShipmentDetailAPI.as_view(), name="shipment-detail-str"),
]
