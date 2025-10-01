from __future__ import annotations

import uuid
from django.db import models
from django.core.exceptions import ValidationError


# ------------------------
# Category (대/중/소)
# ------------------------
class CategoryLevel(models.TextChoices):
    L1 = "l1", "대분류"
    L2 = "l2", "중분류"
    L3 = "l3", "소분류"


class Category(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column="category_id",
    )
    name = models.CharField(max_length=255)

    # 계층 (부모가 없으면 L1)
    parent = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,   # 상위가 있으면 삭제 금지(데이터 보전)
        null=True,
        blank=True,
        related_name="children",
        db_index=True,
    )
    level = models.CharField(
        max_length=2,
        choices=CategoryLevel.choices,
        default=CategoryLevel.L1,
        db_index=True,
    )

    # 사용자에게 보이는 풀 경로 (예: "상의 > 티셔츠 > 반팔")
    path = models.CharField(max_length=255, blank=True, default="", db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "categories"
        verbose_name = "Category"
        verbose_name_plural = "Categories"
        indexes = [
            models.Index(fields=["level", "name"]),
            models.Index(fields=["parent", "name"]),
            models.Index(fields=["path"]),
        ]
        constraints = [
            # 같은 부모 아래에서 이름 중복 금지
            models.UniqueConstraint(
                fields=["parent", "name"],
                name="uq_category_parent_name",
            ),
            # 루트(L1, parent is NULL)에서는 name 고유
            models.UniqueConstraint(
                fields=["name"],
                name="uq_category_root_name",
                condition=models.Q(parent__isnull=True),
            ),
        ]

    # ---- 유효성 ----
    def clean(self):
        # L3(소분류)의 자식은 금지
        if self.parent and self.parent.level == CategoryLevel.L3:
            raise ValidationError("소분류(L3) 아래에는 하위 분류를 만들 수 없습니다.")

        # 기대 레벨 자동/검증
        if self.parent is None:
            expected = CategoryLevel.L1
        else:
            expected = CategoryLevel.L2 if self.parent.level == CategoryLevel.L1 else CategoryLevel.L3

        # 입력된 level이 달라도 자동으로 맞춰줌
        self.level = expected

    # ---- 저장 시 경로/레벨 동기화 ----
    def save(self, *args, **kwargs):
        self.clean()

        if self.parent:
            base = self.parent.path or self.parent.name
            self.path = f"{base} > {self.name}"
        else:
            self.path = self.name

        super().save(*args, **kwargs)
        # 이름/부모가 바뀌면 하위 경로도 재계산
        self.rebuild_descendant_paths()

    def rebuild_descendant_paths(self):
        """
        현재 노드 기준 하위 요소들의 path/level을 재계산.
        (깊이 3단계라 부하 적음)
        """
        for child in self.children.all():
            child.path = f"{self.path} > {child.name}"
            child.level = CategoryLevel.L2 if self.level == CategoryLevel.L1 else CategoryLevel.L3
            child.save(update_fields=["path", "level", "updated_at"])
            child.rebuild_descendant_paths()

    @property
    def is_leaf(self) -> bool:
        return self.level == CategoryLevel.L3

    def __str__(self) -> str:
        return self.path or self.name or f"Category {self.pk}"


# ------------------------
# Products
# ------------------------
class Product(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column="product_id",
    )

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=12, decimal_places=2)

    # 카테고리: 필요 시 L3만 연결하도록 정책을 정해도 되고, 현재는 자유롭게 허용
    category = models.ForeignKey(
        Category,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,    # 또는 PROTECT
        db_column="category_id",
        related_name="products",
    )

    options = models.JSONField(default=dict, blank=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "products"
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["category", "is_active"]),
        ]

    def __str__(self) -> str:
        return self.name or f"Product {self.pk}"


# ------------------------
# 옵션(variant)별 재고
# ------------------------
class ProductStock(models.Model):
    """
    옵션 조합(option_key)별 재고.
    예: "size=L&color=red"
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column="stock_id",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="stocks",
        db_column="product_id",
    )
    option_key = models.CharField(max_length=64, blank=True, default="")
    options    = models.JSONField(blank=True, default=dict)    # 표시/검증용 옵션 스냅샷
    stock_quantity = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "product_stock"
        constraints = [
            models.UniqueConstraint(
                fields=["product", "option_key"],
                name="uq_product_option",
            ),
        ]
        indexes = [
            models.Index(fields=["product", "stock_quantity"]),
        ]

    def __str__(self) -> str:
        return f"{self.product_id} / {self.option_key} = {self.stock_quantity}"


def product_image_upload_to(instance: "ProductImage", filename: str) -> str:
    """
    /media/products/<product_id>/<랜덤>.확장자 경로로 저장
    """
    ext = (filename.rsplit(".", 1)[-1] or "").lower()
    return f"products/{instance.product_id}/{uuid.uuid4().hex}.{ext}"


class ProductImage(models.Model):
    """
    상품 이미지
    - 파일은 스토리지(로컬/S3)에 저장, DB에는 메타 정보 저장
    - 특정 옵션(variant) 이미지에 매핑하려면 stock 사용(선택)
    - is_remote=True 이면 remote_url만 참조(다운로드 X)
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column="image_id",
    )

    product = models.ForeignKey(
        "Product",
        on_delete=models.CASCADE,
        related_name="images",
        db_column="product_id",
    )

    stock = models.ForeignKey(
        "ProductStock",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="images",
        db_column="stock_id",
    )

    # 파일 저장(기존) — URL 참조 케이스를 위해 blank/null 허용
    image = models.ImageField(upload_to=product_image_upload_to, blank=True, null=True)

    # URL만 참조(다운로드 X)
    remote_url = models.URLField(blank=True, null=True)
    is_remote  = models.BooleanField(default=False)

    alt_text = models.CharField(max_length=255, blank=True, default="")
    caption  = models.CharField(max_length=255, blank=True, default="")

    is_main = models.BooleanField(default=False)
    display_order = models.IntegerField(default=0, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "product_images"
        indexes = [
            models.Index(fields=["product", "display_order"]),
            models.Index(fields=["product", "is_main"]),
        ]
        constraints = [
            models.CheckConstraint(
                name="ck_product_image_display_order_ge_0",
                check=models.Q(display_order__gte=0),
            ),
        ]

    def __str__(self) -> str:
        mode = "REMOTE" if self.is_remote else "FILE"
        return f"ProductImage({self.id}) {self.product_id} [{mode}] main={self.is_main}"

    # 통합 접근 URL (파일이면 MEDIA_URL 기반, 원격이면 원격 URL)
    @property
    def url(self) -> str | None:
        if self.image:
            try:
                return self.image.url
            except Exception:
                return None
        return self.remote_url

    # 한쪽만 필수(파일 or 원격)
    def clean(self):
        from django.core.exceptions import ValidationError
        if self.is_remote:
            if not self.remote_url:
                raise ValidationError({"remote_url": "is_remote=True면 remote_url이 필요합니다."})
        else:
            if not self.image:
                raise ValidationError({"image": "is_remote=False면 image 파일이 필요합니다."})