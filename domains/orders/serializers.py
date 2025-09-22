# domains/orders/serializers.py
from __future__ import annotations
from domains.orders.utils import parse_option_key_safe
from rest_framework import serializers
from .models import Purchase, OrderItem

class PurchaseReadSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)

    class Meta:
        model = Purchase
        fields = (
            "purchase_id", "user", "product", "product_name",
            "amount", "unit_price", "options", "option_key",
            "status", "purchased_at", "pg", "pg_tid",
        )
        read_only_fields = ("purchase_id", "status", "purchased_at", "product_name")

class PurchaseWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Purchase
        fields = (
            "user", "product", "amount", "unit_price",
            "options", "option_key", "pg", "pg_tid",
        )

    def validate_amount(self, v):
        if v < 1:
            raise serializers.ValidationError("amount must be >= 1")
        return v

# 호환용 별칭 (기존 코드에서 PurchaseSerializer를 임포트해도 동작)
PurchaseSerializer = PurchaseReadSerializer

class OrderItemReadSerializer(serializers.ModelSerializer):
    item_id = serializers.UUIDField(read_only=True)
    product_id = serializers.UUIDField(read_only=True)  # FK의 *_id 속성은 자동 노출 가능
    order_id = serializers.UUIDField(source="order.purchase_id", read_only=True)
    line_total = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = (
            "item_id",
            "order_id",
            "product_id",
            "product_name",
            "thumbnail_url",
            "sku",
            "option_key",
            "options",
            "unit_price",
            "quantity",
            "line_discount",
            "line_tax",
            "currency",
            "line_total",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_line_total(self, obj):
        # 모델 프로퍼티 있어도 직렬화에서 보장
        return (obj.unit_price or 0) * (obj.quantity or 0) - (obj.line_discount or 0) + (obj.line_tax or 0)
