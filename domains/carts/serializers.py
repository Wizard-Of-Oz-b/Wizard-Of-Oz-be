from __future__ import annotations
from decimal import Decimal
from rest_framework import serializers
from .models import Cart, CartItem
from domains.catalog.models import Product
from .services import add_or_update_item, make_option_key


class CartItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)

    class Meta:
        model = CartItem
        fields = (
            "id", "product", "product_name",
            "option_key", "options", "quantity",
            "unit_price", "added_at",
        )
        read_only_fields = ("id", "option_key", "added_at")


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)

    class Meta:
        model = Cart
        fields = ("id", "user", "expires_at", "updated_at", "items")
        read_only_fields = ("id", "user", "expires_at", "updated_at", "items")


class AddCartItemSerializer(serializers.Serializer):
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())
    options = serializers.JSONField(required=False, default=dict)
    quantity = serializers.IntegerField(min_value=1, default=1)

    def create(self, validated_data):
        user = self.context["request"].user
        product: Product = validated_data["product"]
        options = validated_data.get("options", {})
        quantity = validated_data.get("quantity", 1)

        cart, item = add_or_update_item(
            user=user,
            product=product,
            options=options,
            quantity=quantity,
            unit_price=product.price,  # 서버가 단가 스냅샷 결정
        )
        return item

    def to_representation(self, instance: CartItem):
        return CartItemSerializer(instance).data
