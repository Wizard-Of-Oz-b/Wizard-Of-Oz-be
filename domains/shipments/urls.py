from django.urls import path
from .views import (
    CarrierListAPI,
    ShipmentsListAPI,
    ShipmentDetailAPI,
    ShipmentSyncAPI,
    ShipmentWebhookAPI,
    RegisterShipmentAPI,
    ShipmentTrackAPI,
)

app_name = "shipments"

urlpatterns = [
    path("", ShipmentsListAPI.as_view(), name="shipment-list"),
    path("carriers/", CarrierListAPI.as_view(), name="carrier-list"),
    path("sync/", ShipmentSyncAPI.as_view(), name="shipment-sync"),
    path("register/", RegisterShipmentAPI.as_view(), name="shipment-register"),
    path("webhooks/<str:carrier>/", ShipmentWebhookAPI.as_view(), name="shipment-webhook"),
    path("track/", ShipmentTrackAPI.as_view(), name="shipments-track"),
    path("<uuid:id>/", ShipmentDetailAPI.as_view(), name="shipment-detail"),
]
