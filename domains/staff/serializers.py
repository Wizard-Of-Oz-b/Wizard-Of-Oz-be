# domains/staff/serializers.py
from django.contrib.auth import get_user_model
from rest_framework import serializers

from domains.catalog.models import (
    Category, Product, ProductStock,
    CategoryLevel, ProductImage,
)
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


# --- Catalog: Category (대/중/소) ---
class CategoryAdminSerializer(serializers.ModelSerializer):
    parent = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(), allow_null=True, required=False
    )
    level = serializers.ChoiceField(choices=CategoryLevel.choices, read_only=True)  # parent로 자동
    path = serializers.CharField(read_only=True)
    children_count = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Category
        fields = [
            "id", "name", "parent", "level", "path", "children_count",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "level", "path", "children_count", "created_at", "updated_at"]

    def get_children_count(self, obj) -> int:
        return obj.children.count()

    def update(self, instance, validated_data):
        res = super().update(instance, validated_data)
        # 이름/부모 변경 시 하위 path 재계산
        try:
            res.rebuild_descendant_paths()
        except AttributeError:
            pass
        return res


# --- Catalog: Product ---
class ProductAdminSerializer(serializers.ModelSerializer):
    category = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(), allow_null=True, required=False
    )
    category_path = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Product
        fields = [
            "id", "name", "price", "category", "category_path",
            "options", "is_active", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "category_path", "created_at", "updated_at"]

    def get_category_path(self, obj) -> str | None:
        if obj.category_id:
            return obj.category.path or obj.category.name
        return None


# --- Catalog: Product Stock ---
class ProductStockAdminSerializer(serializers.ModelSerializer):
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())
    product_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = ProductStock
        fields = [
            "id", "product", "product_name",
            "option_key", "options", "stock_quantity",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "product_name", "created_at", "updated_at"]

    def get_product_name(self, obj) -> str:
        return getattr(obj.product, "name", "")


# --- Orders ---
class PurchaseAdminSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = Purchase
        # PK가 purchase_id가 아니라 id라면 여기서 교체하세요.
        fields = [
            "purchase_id", "user", "user_email",
            "status", "purchased_at", "pg", "pg_tid", "amount",
        ]
        read_only_fields = ["purchase_id", "user_email", "purchased_at"]


class OrderActionResponseSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    status = serializers.CharField()


# --- Product Images (Admin) ---
class ProductImageAdminSerializer(serializers.ModelSerializer):
    # 파일이면 절대경로, 원격이면 그 URL
    file_url = serializers.SerializerMethodField(read_only=True)
    # (호환용) 기존 image_url 이름도 그대로 제공
    image_url = serializers.SerializerMethodField(read_only=True)
    product_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = ProductImage
        fields = [
            "id", "product", "stock",
            "image", "remote_url", "is_remote",
            "file_url", "image_url",
            "alt_text", "caption",
            "is_main", "display_order",
            "product_name",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "file_url", "image_url", "product_name", "created_at", "updated_at"
        ]

    def get_file_url(self, obj):
        # 모델의 obj.url 속성(파일이면 MEDIA URL, 원격이면 remote_url)을 사용
        url = getattr(obj, "url", None)
        if not url:
            return None
        # 파일이면 절대 URL로 변환
        if getattr(obj, "image", None):
            request = self.context.get("request")
            if request is not None:
                try:
                    return request.build_absolute_uri(url)
                except Exception:
                    pass
        return url

    def get_image_url(self, obj):
        # 호환용: file_url과 동일하게 반환
        return self.get_file_url(obj)

    def get_product_name(self, obj):
        return getattr(obj.product, "name", None)

    def validate(self, attrs):
        """
        대표 이미지는 제품 당 1장만 허용 + is_remote에 따른 필수값 점검
        """
        # 대표 이미지 중복 방지
        is_main = attrs.get("is_main", getattr(self.instance, "is_main", False))
        product = attrs.get("product") or getattr(self.instance, "product", None)
        if is_main and product:
            qs = ProductImage.objects.filter(product=product, is_main=True)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError({"is_main": "이미 대표 이미지가 존재합니다."})

        # 파일/원격 입력 유효성
        is_remote = attrs.get("is_remote", getattr(self.instance, "is_remote", False))
        has_image = "image" in attrs and attrs.get("image") is not None
        has_remote = "remote_url" in attrs and attrs.get("remote_url")

        if is_remote:
            if not (has_remote or (self.instance and getattr(self.instance, "remote_url", None))):
                raise serializers.ValidationError({"remote_url": "is_remote=True면 remote_url이 필요합니다."})
            # 원격 모드에서는 image를 굳이 요구하지 않음
        else:
            if not (has_image or (self.instance and getattr(self.instance, "image", None))):
                raise serializers.ValidationError({"image": "is_remote=False면 image 파일이 필요합니다."})

        return attrs


class ProductImagesUploadSerializer(serializers.Serializer):
    # 파일 업로드(선택)
    images = serializers.ListField(child=serializers.ImageField(), required=False)

    # URL 업로드(선택) - save_remote에 따라 저장/참조 결정
    image_urls = serializers.ListField(child=serializers.URLField(), required=False)

    # True → URL만 참조(다운로드 X), False → URL을 다운로드해서 파일 저장
    save_remote = serializers.BooleanField(required=False, default=False)

    main_index   = serializers.IntegerField(required=False, default=-1, help_text="대표로 지정할 업로드 파일 인덱스(0부터)")
    replace_main = serializers.BooleanField(required=False, default=False)
    start_order  = serializers.IntegerField(required=False, default=0)
    alt_texts    = serializers.ListField(child=serializers.CharField(allow_blank=True), required=False)
    captions     = serializers.ListField(child=serializers.CharField(allow_blank=True), required=False)

    def validate(self, data):
        images = data.get("images") or []
        urls   = data.get("image_urls") or []
        if not images and not urls:
            raise serializers.ValidationError("images 또는 image_urls 중 최소 하나는 필요합니다.")
        return data
