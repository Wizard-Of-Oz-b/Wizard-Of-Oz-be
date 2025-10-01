from __future__ import annotations

import uuid
from django.db import models
from django.utils import timezone


# ─────────────────────────────────────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────────────────────────────────────
class PaymentProvider(models.TextChoices):
    TOSS = "toss", "Toss"


class PaymentMethod(models.TextChoices):
    CARD = "card", "Card"
    VIRTUAL_ACCOUNT = "virtual_account", "Virtual Account"
    ACCOUNT_TRANSFER = "account_transfer", "Account Transfer"
    MOBILE_PHONE = "mobile_phone", "Mobile Phone"
    EASY_PAY = "easy_pay", "Easy Pay"
    GIFT_CERT = "gift_certificate", "Gift Certificate"


class PaymentStatus(models.TextChoices):
    READY = "ready", "Ready"
    IN_PROGRESS = "in_progress", "In Progress"
    WAITING_FOR_DEPOSIT = "waiting_for_deposit", "Waiting for Deposit"
    PAID = "paid", "Paid"
    PARTIAL_CANCELED = "partial_canceled", "Partial Canceled"
    CANCELED = "canceled", "Canceled"
    FAILED = "failed", "Failed"
    EXPIRED = "expired", "Expired"


class CancelStatus(models.TextChoices):
    REQUESTED = "requested", "Requested"
    PROCESSING = "processing", "Processing"
    DONE = "done", "Done"
    FAILED = "failed", "Failed"


# ─────────────────────────────────────────────────────────────────────────────
# 결제 헤더 (주문 1 : N 결제 허용)
# ─────────────────────────────────────────────────────────────────────────────
class Payment(models.Model):
    payment_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # 주문 헤더는 domains.orders.models.Purchase
    order = models.ForeignKey(
        "orders.Purchase",
        on_delete=models.CASCADE,
        related_name="payments",
    )

    provider = models.CharField(
        max_length=20, choices=PaymentProvider.choices, default=PaymentProvider.TOSS
    )
    provider_payment_key = models.CharField(  # Toss paymentKey
        max_length=200, unique=True, null=True, blank=True
    )
    order_number = models.CharField(          # Toss orderId 로 사용
        max_length=100, unique=True, null=True, blank=True
    )

    method = models.CharField(
        max_length=30, choices=PaymentMethod.choices, null=True, blank=True
    )
    status = models.CharField(
        max_length=32, choices=PaymentStatus.choices, default=PaymentStatus.READY
    )

    currency = models.CharField(max_length=3, default="KRW")
    amount_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    amount_tax_free = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    vat = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    requested_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    canceled_at = models.DateTimeField(null=True, blank=True)

    failure_code = models.CharField(max_length=60, null=True, blank=True)
    failure_message = models.TextField(null=True, blank=True)
    receipt_url = models.CharField(max_length=255, null=True, blank=True)

    # 수단별 스냅샷
    card_info = models.JSONField(null=True, blank=True)
    virtual_account = models.JSONField(null=True, blank=True)
    easy_pay = models.JSONField(null=True, blank=True)

    last_synced_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "payments"
        indexes = [
            models.Index(fields=["order", "created_at"]),
            models.Index(fields=["status"]),
        ]

    def touch(self):
        self.updated_at = timezone.now()

    def __str__(self) -> str:  # optional
        return f"{self.payment_id} ({self.status})"


# ─────────────────────────────────────────────────────────────────────────────
# 결제 이벤트(히스토리)
# ─────────────────────────────────────────────────────────────────────────────
class PaymentEvent(models.Model):
    event_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name="events")
    source = models.CharField(max_length=20)  # webhook | sync | manual | api
    event_type = models.CharField(max_length=40)  # status_changed | approval | cancel | fail | etc
    provider_status = models.CharField(
        max_length=32, choices=PaymentStatus.choices, null=True, blank=True
    )
    payload = models.JSONField(null=True, blank=True)
    dedupe_key = models.CharField(max_length=128, null=True, blank=True, db_index=True)
    occurred_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "payment_events"
        indexes = [models.Index(fields=["payment", "created_at"])]

    def __str__(self) -> str:
        return f"{self.event_id} {self.event_type}"


# ─────────────────────────────────────────────────────────────────────────────
# 결제 취소(부분/전액)
# ─────────────────────────────────────────────────────────────────────────────
class PaymentCancel(models.Model):
    cancel_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name="cancels")

    status = models.CharField(
        max_length=16, choices=CancelStatus.choices, default=CancelStatus.REQUESTED
    )
    reason = models.TextField(null=True, blank=True)
    cancel_amount = models.DecimalField(max_digits=12, decimal_places=2)
    tax_free_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    requested_at = models.DateTimeField(default=timezone.now)
    approved_at = models.DateTimeField(null=True, blank=True)

    provider_cancel_key = models.CharField(max_length=128, null=True, blank=True)
    error_code = models.CharField(max_length=60, null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "payment_cancels"
        indexes = [models.Index(fields=["payment", "created_at"])]

    def __str__(self) -> str:
        return f"{self.cancel_id} ({self.status})"
