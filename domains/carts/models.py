# domains/carts/models.py
from __future__ import annotations
import uuid
from datetime import timedelta
from django.db import models
from django.conf import settings
from django.utils import timezone
from domains.catalog.models import Product

def default_expires_at():
    return timezone.now() + timedelta(days=90)

class Cart(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, db_column="cart_id")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name="carts", db_column="user_id")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # 생성 +90일 만료 (파이썬 기본; 필요하면 DB default도 추가)
    expires_at = models.DateTimeField(default=default_expires_at, db_index=True)

    class Meta:
        db_table = "carts"
        indexes = [models.Index(fields=["user"])]
        # 한 유저 1카트 정책이면 주석 해제
        # constraints = [models.UniqueConstraint(fields=["user"], name="uq_user_single_cart")]

    def __str__(self):
        return f"Cart({self.pk}) of {self.user_id}"

class CartItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, db_column="item_id")
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items", db_column="cart_id")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="cart_items", db_column="product_id")
    option_key = models.CharField(max_length=64, help_text="예: size=L&color=red")
    options = models.JSONField(default=dict, blank=True)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "cart_items"
        constraints = [
            models.UniqueConstraint(fields=["cart", "product", "option_key"], name="uq_cart_product_option"),
        ]
        indexes = [
            models.Index(fields=["cart"]),
            models.Index(fields=["product"]),
        ]

    def __str__(self):
        return f"CartItem({self.pk}) cart={self.cart_id} product={self.product_id}"
