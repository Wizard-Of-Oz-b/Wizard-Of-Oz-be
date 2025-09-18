# domains/shipments/urls.py  <-- 전체 교체
from django.urls import path
from .views import (
    ShipmentsListAPI,
    ShipmentDetailAPI,
    ShipmentSyncAPI,
    ShipmentWebhookAPI,
    RegisterShipmentAPI,  # 선택
)

urlpatterns = [
    # 여기서는 prefix를 전혀 붙이지 않는다. (config에서 api/v1/shipments/로 include됨)
    path("", ShipmentsListAPI.as_view(), name="shipment-list"),
    path("<uuid:id>/", ShipmentDetailAPI.as_view(), name="shipment-detail"),
    path("sync/", ShipmentSyncAPI.as_view(), name="shipment-sync"),

    # 임시: /api/v1/shipments/webhooks/<carrier>/ (최종은 /api/v1/webhooks/shipments/<carrier>)
    path("webhooks/<str:carrier>/", ShipmentWebhookAPI.as_view(), name="shipment-webhook"),

    # 선택: 사용자 등록용
    path("register/", RegisterShipmentAPI.as_view(), name="shipment-register"),
]
