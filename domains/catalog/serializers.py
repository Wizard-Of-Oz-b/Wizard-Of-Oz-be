from rest_framework import serializers
from .models import Category, Product


class CategorySerializer(serializers.ModelSerializer):
    # 읽기용: model 객체의 attribute `parent_id`를 그대로 노출 (source 지정 X)
    parent_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = Category
        fields = ["category_id", "name", "parent_id"]


class CategoryWriteSerializer(serializers.ModelSerializer):
    # 쓰기용: 숫자 parent_id로 받기
    parent_id = serializers.IntegerField(required=False, allow_null=True)

    class Meta:
        model = Category
        # model 필드는 name/parent 이지만, 입력은 parent_id 로 받음
        fields = ["name", "parent_id"]

    def validate_parent_id(self, value):
        if value is None:
            return value
        if not Category.objects.filter(pk=value).exists():
            raise serializers.ValidationError("parent category not found")

        # 사이클 방지(자기 자신/자손을 부모로 지정 금지)
        inst = getattr(self, "instance", None)
        if inst is not None:
            pid = value
            while pid:
                if pid == inst.pk:
                    raise serializers.ValidationError("cannot set parent to its descendant/self")
                pid = Category.objects.filter(pk=pid).values_list("parent_id", flat=True).first()
        return value

    def create(self, validated_data):
        # parent_id -> model.parent_id 로 명시적 매핑
        parent_id = validated_data.pop("parent_id", None)
        obj = Category(name=validated_data.get("name", ""), parent_id=parent_id)
        obj.save()
        return obj

    def update(self, instance, validated_data):
        # 부분 수정 지원
        if "name" in validated_data:
            instance.name = validated_data["name"]
        if "parent_id" in validated_data:
            instance.parent_id = validated_data["parent_id"]
        instance.save()
        return instance


class CategoryNodeSerializer(serializers.ModelSerializer):
    # 트리 응답용 (children 재귀)
    parent_id = serializers.IntegerField(read_only=True)
    children = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ["category_id", "name", "parent_id", "children"]

    def get_children(self, obj):
        qs = obj.children.all().order_by("name")
        return CategoryNodeSerializer(qs, many=True).data


# (참고) ProductSerializer는 그대로 사용하시던 버전 쓰시면 됩니다.
class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ["product_id", "name", "description", "price", "category", "is_active", "created_at"]

class ProductReadSerializer(serializers.ModelSerializer):
    # 외부로는 category_id를 숫자로 노출 (주의: source 지정 X)
    category_id = serializers.IntegerField(read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True)

    class Meta:
        model = Product
        fields = [
            "product_id", "name", "description", "price",
            "category_id", "category_name", "is_active", "created_at"
        ]

class ProductWriteSerializer(serializers.ModelSerializer):
    # 입력은 category_id 숫자로 받음
    category_id = serializers.IntegerField(required=False, allow_null=True)
    price = serializers.IntegerField(min_value=0)

    class Meta:
        model = Product
        # model 필드엔 category가 있지만, 입력은 category_id로 받는다
        fields = ["name", "description", "price", "category_id", "is_active"]

    def validate_category_id(self, value):
        if value is None:
            return value
        if not Category.objects.filter(pk=value).exists():
            raise serializers.ValidationError("category not found")
        return value

    def create(self, validated_data):
        category_id = validated_data.pop("category_id", None)
        obj = Product(**validated_data)
        obj.category_id = category_id
        obj.save()
        return obj

    def update(self, instance, validated_data):
        if "name" in validated_data:
            instance.name = validated_data["name"]
        if "description" in validated_data:
            instance.description = validated_data["description"]
        if "price" in validated_data:
            instance.price = validated_data["price"]
        if "is_active" in validated_data:
            instance.is_active = validated_data["is_active"]
        if "category_id" in validated_data:
            instance.category_id = validated_data["category_id"]
        instance.save()
        return instance
