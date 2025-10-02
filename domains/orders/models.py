from __future__ import annotations

import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import models

from domains.catalog.models import Product

User = get_user_model()


class PurchaseStatus(models.TextChoices):
    READY = "ready", "Ready"  # ✅ 결제 전(헤더 생성 시)
    PAID = "paid", "Paid"
    CANCELED = "canceled", "Canceled"
    REFUNDED = "refunded", "Refunded"
    MERGED = "merged", "Merged"  # ✅ 다른 주문으로 통합됨


class Purchase(models.Model):
    # --- 상태 상수(기존 호환) ---
    STATUS_READY = "ready"
    STATUS_PAID = "paid"
    STATUS_CANCELED = "canceled"
    STATUS_REFUNDED = "refunded"
    STATUS_MERGED = "merged"
    STATUS_CHOICES = [
        (STATUS_READY, "Ready"),
        (STATUS_PAID, "Paid"),
        (STATUS_CANCELED, "Canceled"),
        (STATUS_REFUNDED, "Refunded"),
        (STATUS_MERGED, "Merged"),
    ]

    # --- PK ---
    purchase_id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False, db_column="purchase_id"
    )

    # --- FK ---
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        db_column="user_id",
        related_name="purchases",
    )
    # 헤더 레코드(합계만 갖는 주문)도 허용하기 위해 null/blank 허용
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        db_column="product_id",
        related_name="purchases",
        null=True,
        blank=True,
    )

    # --- 주문 스냅샷/수량 (라인 전용; 헤더는 기본값 사용) ---
    # 헤더에서도 유효하도록 기본값/제약을 완화(>=0)
    amount = models.PositiveIntegerField(default=0)
    unit_price = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    options = models.JSONField(default=dict, blank=True)
    option_key = models.CharField(max_length=64, blank=True, default="", db_index=True)

    # --- 헤더 합계(지금 추가한 필드) ---
    items_total = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    grand_total = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )

    # --- 배송지 스냅샷 (주문 시점 복사본; 이후 주소 변경이 과거 주문에 영향 X) ---
    shipping_recipient = models.CharField(max_length=50, blank=True, default="")
    shipping_phone = models.CharField(max_length=20, blank=True, default="")
    shipping_postcode = models.CharField(max_length=10, blank=True, default="")
    shipping_address1 = models.CharField(max_length=200, blank=True, default="")
    shipping_address2 = models.CharField(max_length=200, blank=True, default="")
    shipping_memo = models.CharField(max_length=200, blank=True, default="")

    status = models.CharField(
        max_length=20,
        choices=PurchaseStatus.choices,
        default=PurchaseStatus.PAID,  # 기존 기본값 유지; 헤더 생성 시 코드에서 ready로 지정
    )
    purchased_at = models.DateTimeField(auto_now_add=True)

    # --- 결제사/거래 키 ---
    pg = models.CharField(max_length=20, blank=True, null=True, default=None)
    pg_tid = models.CharField(
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
            # 헤더 허용을 위해 amount >= 0 로 완화
            models.CheckConstraint(
                check=models.Q(amount__gte=0), name="ck_purchase_amount_ge_0"
            ),
        ]

    def __str__(self) -> str:
        return f"Purchase({self.purchase_id}) user={self.user_id} product={self.product_id} status={self.status}"

    @property
    def line_total(self) -> Decimal:
        """amount × unit_price (라인 전용; 헤더는 0)"""
        return (self.unit_price or Decimal("0.00")) * Decimal(self.amount or 0)


class OrderItem(models.Model):
    item_id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False, db_column="item_id"
    )
    order = models.ForeignKey(
        Purchase, on_delete=models.CASCADE, related_name="items", db_column="order_id"
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="order_items",
        db_column="product_id",
    )
    stock = models.ForeignKey(
        "catalog.ProductStock",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="order_items",
        db_column="stock_id",
    )

    # 스냅샷(표시/CS)
    product_name = models.CharField(max_length=80)
    thumbnail_url = models.CharField(max_length=255, blank=True, null=True)
    sku = models.CharField(max_length=64, blank=True, null=True)
    option_key = models.CharField(max_length=64, default="", db_index=True)
    options = models.JSONField(default=dict, blank=True)

    # 금액/수량
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)
    line_discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    line_tax = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default="KRW")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "order_items"
        indexes = [
            models.Index(fields=["order"]),
            models.Index(fields=["product"]),
            models.Index(fields=["stock"]),
            models.Index(fields=["sku"]),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(quantity__gte=1), name="ck_orderitem_qty_ge_1"
            ),
        ]

    @property
    def line_total(self):
        return (
            (self.unit_price or 0) * (self.quantity or 0)
            - (self.line_discount or 0)
            + (self.line_tax or 0)
        )
