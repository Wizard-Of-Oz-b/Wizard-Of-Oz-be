from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models


class ShipmentStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    IN_TRANSIT = "in_transit", "In Transit"
    OUT_FOR_DELIVERY = "out_for_delivery", "Out For Delivery"
    DELIVERED = "delivered", "Delivered"
    CANCELED = "canceled", "Canceled"
    RETURNED = "returned", "Returned"


class Shipment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    carrier = models.CharField(max_length=40)
    tracking_number = models.CharField(max_length=64)

    status = models.CharField(
        max_length=24,
        choices=ShipmentStatus.choices,
        default=ShipmentStatus.PENDING,
    )

    shipped_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    canceled_at = models.DateTimeField(null=True, blank=True)

    last_event_at = models.DateTimeField(null=True, blank=True)
    last_event_status = models.CharField(
        max_length=24, choices=ShipmentStatus.choices, null=True, blank=True
    )
    last_event_loc = models.CharField(max_length=120, blank=True)
    last_event_desc = models.CharField(max_length=200, blank=True)

    last_synced_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    order = models.ForeignKey(
        "orders.Purchase", on_delete=models.CASCADE, related_name="shipments"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="shipments"
    )

    class Meta:
        indexes = [
            models.Index(
                fields=["carrier", "tracking_number"],
                name="shipments_s_carrier_4f3ab4_idx",
            ),
            models.Index(
                fields=["user", "created_at"], name="shipments_s_user_id_a5db8b_idx"
            ),
            models.Index(
                fields=["status", "last_event_at"], name="shipments_s_status_576ef0_idx"
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=("carrier", "tracking_number"), name="uq_carrier_tracking"
            )
        ]

    def __str__(self) -> str:
        return f"{self.carrier}:{self.tracking_number}"


class ShipmentEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    shipment = models.ForeignKey(
        Shipment, on_delete=models.CASCADE, related_name="events"
    )
    occurred_at = models.DateTimeField()
    status = models.CharField(max_length=24, choices=ShipmentStatus.choices)
    location = models.CharField(max_length=120, blank=True)
    description = models.TextField(blank=True)

    provider_code = models.CharField(max_length=80, blank=True)
    raw_payload = models.JSONField(null=True, blank=True)
    source = models.CharField(max_length=20, blank=True)
    dedupe_key = models.CharField(max_length=128, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(
                fields=["shipment", "occurred_at"],
                name="shipments_s_shipmen_0b12ad_idx",
            ),
            models.Index(
                fields=["shipment", "status"], name="shipments_s_shipmen_0c2d4c_idx"
            ),
            models.Index(fields=["dedupe_key"], name="shipments_s_dedupe__a71a08_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.shipment_id}@{self.occurred_at}"
