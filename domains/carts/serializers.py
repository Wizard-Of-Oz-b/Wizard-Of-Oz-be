# domains/carts/serializers.py
from __future__ import annotations

from typing import Dict, Any

from rest_framework import serializers

from .models import Cart, CartItem
from domains.catalog.models import Product
from .services import add_or_update_item, make_option_key
from domains.orders.utils import parse_option_key_safe


def _validate_option_key_value(v: str) -> str:
    """
    'size=L&color=red' 형식의 문자열을 간단 검증.
    빈 문자열은 '옵션 없음'으로 허용.
    """
    v = (v or "").strip()
    if not v:
        return ""  # 옵션 없이 담는 것을 허용
    if not parse_option_key_safe(v):
        raise serializers.ValidationError("옵션 형식이 잘못되었습니다. 예: size=L&color=red")
    return v


# ---------------------------
# Read serializers
# ---------------------------
class CartItemSerializer(serializers.ModelSerializer):
    """장바구니 아이템 읽기용 직렬화기 (상품 썸네일 포함)"""
    product_name = serializers.CharField(source="product.name", read_only=True)
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        fields = (
            "id",
            "product",        # UUID(pk)
            "product_name",
            "option_key",
            "options",
            "quantity",
            "unit_price",
            "image_url",      # 👈 추가: 대표 이미지 URL
            "added_at",
        )
        read_only_fields = (
            "id",
            "option_key",
            "added_at",
            "image_url",
            "product_name",
        )

    def get_image_url(self, obj) -> str | None:
        """
        대표 이미지 선택 규칙:
        1) Product.thumbnail_url 필드가 있으면 그 값을 사용
        2) Product.images (related_name='images')가 있으면 첫 번째 이미지의 image_url 사용
        3) 없으면 None
        """
        # 1) 직접 필드 우선
        url = getattr(obj.product, "thumbnail_url", None)
        if url:
            return url

        # 2) 관련 이미지가 프리패치 되어 있다면 첫 번째를 사용
        images = getattr(obj.product, "images", None)
        # images가 RelatedManager면 .all() 호출 가능
        if images is not None and hasattr(images, "all"):
            first = next(iter(images.all()), None)
            if first is not None:
                return getattr(first, "image_url", None)

        return None


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)

    class Meta:
        model = Cart
        fields = ("id", "user", "expires_at", "updated_at", "items")
        read_only_fields = ("id", "user", "expires_at", "updated_at", "items")


# ---------------------------
# Write serializer (add item)
# ---------------------------
class AddCartItemSerializer(serializers.Serializer):
    """
    장바구니에 아이템 추가
    - 아래 중 하나만 보내세요:
      1) option_key: "size=L&color=red"
      2) options: {"size":"L", "color":"red"}
    """
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())
    quantity = serializers.IntegerField(min_value=1, default=1)

    # 둘 중 하나만 사용
    option_key = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text='옵션 문자열 (예: "size=L&color=red")',
    )
    options = serializers.DictField(
        child=serializers.CharField(allow_blank=True),
        required=False,
        help_text='옵션 딕셔너리 (예: {"size":"L","color":"red"})',
    )

    # --- field-level validator (option_key) ---
    def validate_option_key(self, v: str) -> str:
        return _validate_option_key_value(v)

    # --- object-level validator ---
    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        ok = attrs.get("option_key", None)
        od = attrs.get("options", None)

        # 둘 다 보낸 경우 금지
        if ok is not None and od is not None:
            raise serializers.ValidationError(
                {"option_key": "option_key와 options는 동시에 보낼 수 없습니다."}
            )

        # 둘 다 안 보낸 경우: 옵션 없이 담는 것을 허용 (option_key="")
        if ok is None and od is None:
            attrs["option_key"] = ""  # 옵션 없음으로 취급

        return attrs

    def create(self, validated_data: Dict[str, Any]) -> CartItem:
        user = self.context["request"].user
        product: Product = validated_data["product"]
        quantity: int = validated_data.get("quantity", 1)

        option_key: str | None = validated_data.get("option_key", None)
        options: Dict[str, Any] | None = validated_data.get("options", None)

        # option_key가 오면 파싱해서 dict로 변환 (빈 문자열이면 옵션 없음)
        if option_key is not None:
            if option_key.strip():
                parsed = parse_option_key_safe(option_key)
                # validate_option_key에서 1차 검증하지만, 혹시 몰라 다시 방어
                if parsed is None:
                    raise serializers.ValidationError(
                        {"option_key": "옵션 형식이 잘못되었습니다."}
                    )
                options = parsed
            else:
                options = {}

        # options가 오면 표준화된 option_key를 생성 (DB에는 item.options도 함께 저장됨)
        if options is not None and option_key is None:
            option_key = make_option_key(options)

        # 서비스 호출
        cart, item = add_or_update_item(
            user=user,
            product=product,
            options=options or {},           # 서비스는 dict 기대
            quantity=quantity,
            unit_price=product.price,        # 서버가 단가 스냅샷 결정
        )
        return item

    # 응답은 읽기용 serializer로 통일(이미지 포함)
    def to_representation(self, instance: CartItem) -> Dict[str, Any]:
        return CartItemSerializer(instance).data
