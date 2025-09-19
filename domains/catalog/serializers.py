# domains/catalog/serializers.py
from __future__ import annotations

from typing import Iterable
from rest_framework import serializers
from .models import Category, Product, ProductStock

# ─────────────────────────────────────────────────────────────────────────────
# 공용 유틸
# ─────────────────────────────────────────────────────────────────────────────
def _abs_url(request, url: str) -> str:
    """request가 있으면 절대 URL, 없으면 상대 URL을 반환."""
    if not url:
        return url
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
    """
    id = serializers.CharField()
    url = serializers.CharField()

    @staticmethod
    def from_instance(img, request=None) -> dict:
        # img.image.url 이라고 가정 (일반적인 ImageField 이름)
        # 필드명이 다르면 필요 시 여기만 수정하면 됨.
        url = getattr(getattr(img, "image", None), "url", "")
        return {
            "id": str(getattr(img, "pk", getattr(img, "id", ""))),
            "url": _abs_url(request, url),
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
            "primary_image",  # 대표 이미지(첫 번째)
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

    def get_images(self, obj: Product):
        request = self.context.get("request")
        imgs = self._iter_product_images(obj)
        return [ProductImageSlim.from_instance(img, request) for img in imgs]

    def get_primary_image(self, obj: Product):
        all_images = self.get_images(obj)
        return all_images[0] if all_images else None


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

    class Meta:
        model = ProductStock
        fields = ("product_id", "option_key", "options", "stock_quantity")

    def validate_product_id(self, v):
        if not Product.objects.filter(pk=v).exists():
            raise serializers.ValidationError("product not found")
        return v

    def create(self, validated):
        pid = validated.pop("product_id")
        return ProductStock.objects.create(product_id=pid, **validated)

    def update(self, inst, validated):
        # 필요 시 수정 허용 필드만 제한
        for f in ("option_key", "options", "stock_quantity"):
            if f in validated:
                setattr(inst, f, validated[f])
        inst.save()
        return inst
