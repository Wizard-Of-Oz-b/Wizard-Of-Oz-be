# domains/carts/models.py
from __future__ import annotations

import uuid
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import F, Sum, DecimalField, ExpressionWrapper
from django.utils import timezone

from domains.catalog.models import Product


def default_expires_at():
    return timezone.now() + timedelta(days=90)


class Cart(models.Model):
    id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False, db_column="cart_id"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="carts",
        db_column="user_id",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # 생성 +90일 만료
    expires_at = models.DateTimeField(default=default_expires_at, db_index=True)

    class Meta:
        db_table = "carts"
        indexes = [models.Index(fields=["user"]), models.Index(fields=["expires_at"])]
        # 한 유저 1카트 정책이면 아래 주석 해제
        # constraints = [models.UniqueConstraint(fields=["user"], name="uq_user_single_cart")]

    def __str__(self) -> str:  # pragma: no cover
        return f"Cart({self.pk}) of {self.user_id}"

    # ✅ 합계/개수 프로퍼티 (필드 아님)
    @property
    def total_price(self) -> Decimal:
        """
        items.quantity * items.unit_price 의 합계.
        아이템이 없으면 0.00 반환.
        """
        expr = ExpressionWrapper(
            F("quantity") * F("unit_price"),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        )
        agg = self.items.aggregate(total=Sum(expr))
        return agg["total"] or Decimal("0.00")

    @property
    def item_count(self) -> int:
        return self.items.aggregate(n=Sum("quantity"))["n"] or 0


class CartItem(models.Model):
    id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False, db_column="item_id"
    )
    cart = models.ForeignKey(
        Cart, on_delete=models.CASCADE, related_name="items", db_column="cart_id"
    )
    product = models.ForeignKey(
        Product, on_delete=models.PROTECT, related_name="cart_items", db_column="product_id"
    )
    # ✅ 옵션 없는 상품도 지원: 공백 허용 + 기본값 ""
    option_key = models.CharField(
        max_length=64, blank=True, default="", help_text="예: size=L&color=red"
    )
    options = models.JSONField(default=dict, blank=True)
    quantity = models.PositiveIntegerField(default=1)
    # 담을 당시 가격 스냅샷(필수)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "cart_items"
        constraints = [
            # (cart, product, option_key) 기준 중복 방지
            models.UniqueConstraint(
                fields=["cart", "product", "option_key"], name="uq_cart_product_option"
            ),
        ]
        indexes = [
            models.Index(fields=["cart"]),
            models.Index(fields=["product"]),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"CartItem({self.pk}) cart={self.cart_id} product={self.product_id}"
