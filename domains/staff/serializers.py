# api/staff/serializers.py
from django.contrib.auth import get_user_model
from rest_framework import serializers

from domains.catalog.models import Category, Product, ProductStock, CategoryLevel
from domains.orders.models import Purchase

User = get_user_model()


# --- Users ---
class UserMinSerializer(serializers.ModelSerializer):
    user_id = serializers.UUIDField(source="id", read_only=True)

    class Meta:
        model = User
        fields = ["user_id", "email", "role", "status", "is_active", "created_at"]


class UserRoleUpdateSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=[c[0] for c in User.Role.choices])


# --- Catalog ---
class CategoryAdminSerializer(serializers.ModelSerializer):
    # 계층형 카테고리용 필드
    parent = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(), allow_null=True, required=False
    )
    level = serializers.ChoiceField(choices=CategoryLevel.choices, read_only=True)  # parent에 따라 자동 결정
    path = serializers.CharField(read_only=True)
    children_count = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Category
        fields = [
            "id",
            "name",
            "parent",
            "level",
            "path",
            "children_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "level", "path", "children_count", "created_at", "updated_at"]

    def get_children_count(self, obj) -> int:
        # related_name="children"
        return obj.children.count()

    def update(self, instance, validated_data):
        """
        이름/부모 변경 시 모델의 save()가 path/level을 동기화하고,
        후손 경로도 재계산하도록 모델에서 호출합니다.
        """
        res = super().update(instance, validated_data)
        # 모델 save()에서 이미 후손 경로 재계산을 호출하지만,
        # 외부에서 update_fields로 저장될 수도 있어 한 번 더 안전하게 호출.
        try:
            res.rebuild_descendant_paths()
        except AttributeError:
            pass
        return res


class ProductAdminSerializer(serializers.ModelSerializer):
    category = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(), allow_null=True, required=False
    )
    category_path = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "price",
            "category",
            "category_path",
            "options",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "category_path", "created_at", "updated_at"]

    def get_category_path(self, obj) -> str | None:
        if obj.category_id:
            return obj.category.path or obj.category.name
        return None


class ProductStockAdminSerializer(serializers.ModelSerializer):
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())
    product_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = ProductStock
        fields = ["id", "product", "product_name", "option_key", "options", "stock_quantity", "created_at", "updated_at"]
        read_only_fields = ["id", "product_name", "created_at", "updated_at"]

    def get_product_name(self, obj) -> str:
        return getattr(obj.product, "name", "")


# --- Orders ---
class PurchaseAdminSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = Purchase
        # 프로젝트 모델에 맞춰 필드 구성 (purchase_id가 PK라면 아래처럼 사용)
        fields = [
            "purchase_id",  # PK 필드명이 id라면 "id"로 바꾸세요.
            "user",
            "user_email",
            "status",
            "purchased_at",
            "pg",
            "pg_tid",
            "amount",
        ]
        read_only_fields = ["purchase_id", "user_email", "purchased_at"]


class OrderActionResponseSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    status = serializers.CharField()
