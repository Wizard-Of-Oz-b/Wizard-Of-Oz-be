# domains/orders/models.py
from __future__ import annotations
import uuid
from django.db import models
from django.contrib.auth import get_user_model
from domains.catalog.models import Product

User = get_user_model()

class PurchaseStatus(models.TextChoices):
    PAID = "paid", "Paid"
    CANCELED = "canceled", "Canceled"
    REFUNDED = "refunded", "Refunded"

class Purchase(models.Model):
    # --- 상태 Enum ---
    STATUS_PAID = "paid"
    STATUS_CANCELED = "canceled"
    STATUS_REFUNDED = "refunded"
    STATUS_CHOICES = [
        (STATUS_PAID, "Paid"),
        (STATUS_CANCELED, "Canceled"),
        (STATUS_REFUNDED, "Refunded"),
    ]

    # --- PK ---
    purchase_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, db_column="purchase_id")


    # --- FK ---
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        db_column="user_id",
        related_name="purchases",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,  # 제품은 삭제 방지(기록 보존)
        db_column="product_id",
        related_name="purchases",
    )

    # --- 주문 스냅샷/수량 ---
    amount = models.PositiveIntegerField(default=1)  # CHECK: >= 1
    unit_price = models.DecimalField(  # 결제 시 단가 스냅샷
        max_digits=12, decimal_places=2
    )
    options = models.JSONField(  # 옵션 스냅샷(표시/CS용)
        default=dict, blank=True
    )
    option_key = models.CharField(   # 예: "size=L&color=red"
        max_length=64, blank=True, default="", db_index=True
    )

    status = models.CharField(
        max_length=20,
        choices=PurchaseStatus.choices,
        default=PurchaseStatus.PAID,
    )
    purchased_at = models.DateTimeField(auto_now_add=True)

    # --- 결제사/거래 키 (운영 권장) ---
    pg = models.CharField(
        max_length=20, blank=True, null=True, default=None
    )
    pg_tid = models.CharField(  # 멱등성/중복 방지
        max_length=100, blank=True, null=True, unique=True, default=None
    )

    class Meta:
        db_table = "purchases"
        indexes = [
            models.Index(fields=["user", "purchased_at"]),
            models.Index(fields=["product", "purchased_at"]),
            models.Index(fields=["status"]),
            models.Index(fields=["option_key"]),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(amount__gte=1), name="ck_purchase_amount_ge_1"
            ),
        ]

    def __str__(self) -> str:
        return f"Purchase({self.purchase_id}) {self.user_id}->{self.product_id} {self.status}"

    @property
    def line_total(self):
        """amount × unit_price 편의 속성"""
        return (self.unit_price or 0) * (self.amount or 0)
