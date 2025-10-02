from django.urls import path

from .views import (
    RegisterShipmentAPI,
    ShipmentDetailAPI,
    ShipmentsListAPI,
    ShipmentSyncAPI,
    ShipmentTrackAPI,
    ShipmentWebhookAPI,
)

app_name = "shipments"

urlpatterns = [
    # 목록
    path("", ShipmentsListAPI.as_view(), name="shipment-list"),
    # 정적(POST) 엔드포인트들: 트레일링 슬래시 필수!
    path("sync/", ShipmentSyncAPI.as_view(), name="shipment-sync"),
    path("register/", RegisterShipmentAPI.as_view(), name="shipment-register"),
    path(
        "webhooks/<str:carrier>/", ShipmentWebhookAPI.as_view(), name="shipment-webhook"
    ),
    # 상세
    path("<uuid:id>/", ShipmentDetailAPI.as_view(), name="shipment-detail"),
    # (옵션) 문자열 PK 백업 라우트 — 반드시 맨 끝 (충돌 방지)
    path("<str:id>/", ShipmentDetailAPI.as_view(), name="shipment-detail-str"),
    path("shipments/track/", ShipmentTrackAPI.as_view(), name="shipments-track"),
]
