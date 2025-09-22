# domains/catalog/serializers.py
from __future__ import annotations

from typing import Iterable, Optional, Any
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from .models import Category, Product, ProductStock

# ─────────────────────────────────────────────────────────────────────────────
# 공용 유틸
# ─────────────────────────────────────────────────────────────────────────────
def _abs_url(request, url: Optional[str]) -> Optional[str]:
    """
    request가 있으면 절대 URL, 없으면 상대 URL을 반환.
    url이 비어있거나(None/빈 문자열) 유효하지 않으면 None을 반환한다.
    """
    if not url:
        return None
    return request.build_absolute_uri(url) if request else url


# =========================
# Categories (UUID / no parent)
# =========================
class CategorySerializer(serializers.ModelSerializer):
    # API에서 컬럼명을 category_id로 노출
    category_id = serializers.UUIDField(source="id", read_only=True)

    class Meta:
        model = Category
        fields = ("category_id", "name")  # created_at/updated_at 있으면 추가


class CategoryWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ("name",)


# =========================
# Product Images (Slim)
# =========================
class ProductImageSlim(serializers.Serializer):
    """
    모델명을 모르거나 related_name이 불확실한 상황을 위해
    순수 Serializer로 슬림 구조만 내려준다.
    - 이미지 없으면 url=None (프론트가 안전하게 분기 가능)
    """
    id = serializers.CharField()
    url = serializers.CharField(allow_blank=True, allow_null=True)

    @staticmethod
    def from_instance(img: Any, request=None) -> dict:
        """
        일반적으로 ImageField 이름이 'image'라고 가정.
        필드명이 다르면 여기만 수정하면 됨.
        """
        image_field = getattr(img, "image", None)
        raw_url = getattr(image_field, "url", None) if image_field else None
        return {
            "id": str(getattr(img, "pk", getattr(img, "id", ""))),
            "url": _abs_url(request, raw_url),  # 없으면 None
        }


# =========================
# Products (UUID, FK -> Category)
# =========================
class ProductReadSerializer(serializers.ModelSerializer):
    product_id = serializers.UUIDField(source="id", read_only=True)

    # Django는 FK에 대해 <field>_id 속성을 자동으로 제공합니다.
    # source 지정 없이 read_only로 두면 모델의 category_id 값을 그대로 읽습니다.
    category_id = serializers.UUIDField(read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True)

    price = serializers.DecimalField(max_digits=12, decimal_places=2)
    options = serializers.JSONField(required=False)

    # 이미지: 대표 1장 + 전체 목록
    primary_image = serializers.SerializerMethodField()
    images = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = (
            "product_id",
            "name",
            "description",
            "price",
            "is_active",
            "options",
            "category_id",    # 읽기 전용 FK id
            "category_name",  # 읽기 전용 FK name
            "primary_image",  # 대표 이미지(첫 번째 유효 url)
            "images",         # 모든 이미지(슬림)
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "product_id",
            "category_id",
            "category_name",
            "primary_image",
            "images",
            "created_at",
            "updated_at",
        )

    # --- 이미지 헬퍼 ---
    def _iter_product_images(self, obj: Product) -> Iterable:
        """
        related_name이 'images' 또는 기본 'productimage_set' 둘 다 지원.
        없다면 빈 리스트.
        """
        if hasattr(obj, "images"):
            return getattr(obj, "images").all()
        if hasattr(obj, "productimage_set"):
            return getattr(obj, "productimage_set").all()
        return []

    @extend_schema_field(ProductImageSlim(many=True))
    def get_images(self, obj: Product):
        request = self.context.get("request")
        imgs = self._iter_product_images(obj)
        return [ProductImageSlim.from_instance(img, request) for img in imgs]

    @extend_schema_field(ProductImageSlim)  # nullable object
    def get_primary_image(self, obj: Product):
        """
        url이 있는 첫 이미지를 대표로 선택. 하나도 없으면 None.
        """
        all_images = self.get_images(obj)
        for item in all_images:
            if item.get("url"):  # None/빈 문자열이 아닌 첫 url
                return item
        return None


class ProductWriteSerializer(serializers.ModelSerializer):
    # 입력은 category_id로 받되, 내부에서 model.category_id에 매핑
    category_id = serializers.UUIDField(required=False, allow_null=True)
    price = serializers.DecimalField(max_digits=12, decimal_places=2)
    options = serializers.JSONField(required=False)

    class Meta:
        model = Product
        fields = ("name", "description", "price", "is_active", "options", "category_id")

    def validate_category_id(self, value):
        if value is None:
            return value
        if not Category.objects.filter(pk=value).exists():
            raise serializers.ValidationError("category not found")
        return value

    def create(self, validated_data):
        cid = validated_data.pop("category_id", None)
        obj = Product(**validated_data)
        obj.category_id = cid
        obj.save()
        return obj

    def update(self, instance, validated_data):
        # 부분 업데이트
        for f in ("name", "description", "price", "is_active", "options"):
            if f in validated_data:
                setattr(instance, f, validated_data[f])
        if "category_id" in validated_data:
            instance.category_id = validated_data["category_id"]
        instance.save()
        return instance


# =========================
# Product Stock
# =========================
class ProductStockReadSerializer(serializers.ModelSerializer):
    stock_id = serializers.UUIDField(source="id", read_only=True)
    product_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = ProductStock
        fields = (
            "stock_id",
            "product_id",
            "option_key",
            "options",
            "stock_quantity",
            "created_at",
            "updated_at",
        )


class ProductStockWriteSerializer(serializers.ModelSerializer):
    product_id = serializers.UUIDField()  # 입력은 product_id로 받기
    option_key = serializers.CharField(required=False, allow_blank=True, allow_null=True, default="")
    options    = serializers.JSONField(required=False, default=dict)

    class Meta:
        model = ProductStock
        fields = ("product_id", "option_key", "options", "stock_quantity")

    def validate_product_id(self, v):
        if not Product.objects.filter(pk=v).exists():
            raise serializers.ValidationError("product not found")
        return v

    def create(self, validated):
        pid = validated.pop("product_id")
        # 옵션 없는 경우 key가 안 들어오면 "" 로 통일
        if "option_key" not in validated or validated.get("option_key") in (None,):
            validated["option_key"] = ""
        # options 생략시 {}
        if "options" not in validated or validated.get("options") is None:
            validated["options"] = {}
        return ProductStock.objects.create(product_id=pid, **validated)

    def update(self, inst, validated):
        for f in ("option_key", "options", "stock_quantity"):
            if f in validated:
                # options가 None 이면 {} 로 통일
                value = {} if f == "options" and validated[f] is None else validated[f]
                setattr(inst, f, value)
        inst.save()
        return inst
