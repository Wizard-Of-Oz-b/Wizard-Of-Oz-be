# domains/orders/serializers.py
from __future__ import annotations
from rest_framework import serializers
from .models import Purchase

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
