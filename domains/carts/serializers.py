# domains/carts/serializers.py
from __future__ import annotations

from typing import Dict, Any, Optional
from uuid import UUID
from rest_framework import serializers

from .models import Cart, CartItem
from domains.catalog.models import Product
from .services import add_or_update_item, make_option_key
from domains.orders.utils import parse_option_key_safe


def _abs_url(request, url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    return request.build_absolute_uri(url) if request else url


def _validate_option_key_value(v: str) -> str:
    v = (v or "").strip()
    if not v:
        return ""
    if not parse_option_key_safe(v):
        raise serializers.ValidationError("옵션 형식이 잘못되었습니다. 예: size=L&color=red")
    return v


# ---------------------------
# Read serializers
# ---------------------------
class CartItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        fields = (
            "id",
            "product",
            "product_name",
            "option_key",
            "options",
            "quantity",
            "unit_price",
            "image_url",
            "added_at",
        )
        read_only_fields = ("id", "product_name", "option_key", "image_url", "added_at")

    def get_image_url(self, obj) -> Optional[str]:
        request = self.context.get("request")
        thumb = getattr(obj.product, "thumbnail_url", None)
        if thumb:
            return _abs_url(request, thumb)
        imgs = None
        if hasattr(obj.product, "images"):
            imgs = getattr(obj.product, "images").all()
        elif hasattr(obj.product, "productimage_set"):
            imgs = getattr(obj.product, "productimage_set").all()
        if imgs:
            first = next(iter(imgs), None)
            if first is not None:
                image_field = getattr(first, "image", None)
                raw_url = getattr(image_field, "url", None) if image_field else None
                return _abs_url(request, raw_url)
        return None


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    items_total = serializers.SerializerMethodField()
    item_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Cart
        fields = ("id", "user", "expires_at", "updated_at", "items", "items_total", "item_count")
        read_only_fields = ("id", "user", "expires_at", "updated_at", "items", "items_total", "item_count")

    def get_items_total(self, instance: Cart) -> str:
        return str(instance.total_price)


# ---------------------------
# Write serializer (add item)
# ---------------------------
class AddCartItemSerializer(serializers.Serializer):
    """
    장바구니에 아이템 추가
    - product 또는 product_id 중 하나는 필수
    - 아래 중 하나만 보내세요:
      1) option_key: "size=L&color=red"
      2) options: {"size":"L", "color":"red"}
    - 둘 다 비우면 '옵션 없음'
    """
    # 유연성 확보: 둘 다 문자열(UUID)로 받고 직접 조회
    product = serializers.CharField(required=False)      # UUID 문자열
    product_id = serializers.CharField(required=False)   # UUID 문자열 (alias)

    quantity = serializers.IntegerField(min_value=1, default=1)

    option_key = serializers.CharField(required=False, allow_blank=True)
    # 어떤 JSON도 허용 (문자/숫자 혼재 허용)
    options = serializers.JSONField(required=False)

    def _resolve_product(self, value: Optional[str]) -> Product:
        if not value:
            raise serializers.ValidationError({"product": "product 또는 product_id는 필수입니다."})
        try:
            pk = UUID(str(value))
        except Exception:
            raise serializers.ValidationError({"product": "유효한 UUID가 아닙니다."})
        try:
            return Product.objects.get(pk=pk)
        except Product.DoesNotExist:
            raise serializers.ValidationError({"product": "해당 product를 찾을 수 없습니다."})

    def validate_option_key(self, v: str) -> str:
        return _validate_option_key_value(v)

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        # product / product_id 정규화
        prod_raw = attrs.get("product") or attrs.get("product_id")
        attrs["product_obj"] = self._resolve_product(prod_raw)

        ok = attrs.get("option_key", None)
        od = attrs.get("options", None)

        if ok is not None and od is not None:
            raise serializers.ValidationError({"option_key": "option_key와 options는 동시에 보낼 수 없습니다."})

        if ok is None and od is None:
            attrs["option_key"] = ""  # 옵션 없음

        return attrs

    def create(self, validated: Dict[str, Any]) -> CartItem:
        request = self.context.get("request")
        user = getattr(request, "user", None)
        product: Product = validated["product_obj"]
        quantity: int = validated.get("quantity", 1)

        option_key: Optional[str] = validated.get("option_key", None)
        options: Optional[Dict[str, Any]] = validated.get("options", None)

        # option_key -> options
        if option_key is not None:
            if option_key.strip():
                parsed = parse_option_key_safe(option_key)
                if parsed is None:
                    raise serializers.ValidationError({"option_key": "옵션 형식이 잘못되었습니다."})
                options = parsed
            else:
                options = {}

        # options -> option_key
        if options is not None and option_key is None:
            option_key = make_option_key(options)

        base_kwargs = dict(
            user=user,
            product=product,           # 서비스가 product 객체를 받는 구현
            options=options or {},
            quantity=quantity,
            unit_price=product.price,
        )

        # 서비스 시그니처 편차 흡수 (option_key 요구/불요)
        try:
            cart, item = add_or_update_item(option_key=option_key or "", **base_kwargs)
        except TypeError:
            cart, item = add_or_update_item(**base_kwargs)

        return item

    def to_representation(self, instance: CartItem) -> Dict[str, Any]:
        return CartItemSerializer(instance, context=self.context).data


# ---------------------------
# Update serializers
# ---------------------------
class UpdateCartQtySerializer(serializers.Serializer):
    """장바구니 아이템 수량 변경용 시리얼라이저"""
    quantity = serializers.IntegerField(min_value=1)


class UpdateCartItemSerializer(serializers.Serializer):
    """장바구니 아이템 수량 및 옵션 변경용 시리얼라이저"""
    quantity = serializers.IntegerField(min_value=1, required=False)
    option_key = serializers.CharField(required=False, allow_blank=True, default="")
    options = serializers.JSONField(required=False, default=dict)