# domains/catalog/serializers.py
from __future__ import annotations

from rest_framework import serializers
from .models import Category,ProductStock, Product




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
            "created_at",
            "updated_at",
        )
        read_only_fields = ("product_id", "category_id", "category_name", "created_at", "updated_at")


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



class ProductStockReadSerializer(serializers.ModelSerializer):
    stock_id = serializers.UUIDField(source="id", read_only=True)
    product_id = serializers.UUIDField( read_only=True)

    class Meta:
        model = ProductStock
        fields = ("stock_id", "product_id", "option_key", "options",
                  "stock_quantity", "created_at", "updated_at")

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
