# catalog/models.py
from __future__ import annotations

import uuid
from django.db import models


# ------------------------
# Categories
# ------------------------
class Category(models.Model):
    # 기존 parent 제거, UUID PK 사용 (BigAutoField 유지 원하면 아래 줄을 바꾸세요)
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column="category_id",
    )
    name = models.CharField(max_length=255, unique=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "categories"
        verbose_name = "Category"
        verbose_name_plural = "Categories"
        indexes = [
            models.Index(fields=["name"]),
        ]

    def __str__(self) -> str:
        return self.name or f"Category {self.pk}"


# ------------------------
# Products
# ------------------------
class Product(models.Model):
    # UUID PK (BigAutoField 유지 시 이 부분만 교체)
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column="product_id",
    )

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    # 정가/할인 등을 고려해 정수 대신 Decimal 권장
    price = models.DecimalField(max_digits=12, decimal_places=2)

    # 카테고리 참조는 유지(카테고리 삭제 시 제품을 보호하려면 PROTECT, 비워도 되면 SET_NULL)
    category = models.ForeignKey(
        Category,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,    # 필요에 따라 PROTECT로 변경 가능
        db_column="category_id",
        related_name="products",
    )

    # 옵션 메타(프론트 표현/선택지) — dict 기본 권장
    options = models.JSONField(default=dict, blank=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "products"
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["category", "is_active"]),
        ]

    def __str__(self) -> str:
        return self.name or f"Product {self.pk}"


# ------------------------
# 옵션(variant)별 재고
# ------------------------
class ProductStock(models.Model):
    """
    옵션 조합(option_key)별 재고.
    cart_items.option_key와 같은 규칙(예: "size=L&color=red")을 사용하세요.
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column="stock_id",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="stocks",
        db_column="product_id",
    )
    option_key = models.CharField(
        max_length=64,
        help_text="예: size=L&color=red (cart_items.option_key와 동일 규칙)",
    )
    # 표시/검증용 옵션 스냅샷(정규화 필요 없으면 그대로 사용)
    options = models.JSONField(default=dict)
    stock_quantity = models.IntegerField(default=0)  # 백오더 안 쓰면 Check>=0 권장

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "product_stock"
        constraints = [
            models.UniqueConstraint(
                fields=["product", "option_key"], name="uq_product_option"
            ),
            # 백오더를 사용하지 않을 경우 주석 해제
            # models.CheckConstraint(
            #     check=models.Q(stock_quantity__gte=0),
            #     name="ck_stock_non_negative",
            # ),
        ]
        indexes = [
            models.Index(fields=["product", "stock_quantity"]),
        ]

    def __str__(self) -> str:
        return f"{self.product_id} / {self.option_key} = {self.stock_quantity}"
