from django.db import models

class Category(models.Model):
    category_id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=255)
    parent = models.ForeignKey("self", null=True, blank=True,
                               on_delete=models.SET_NULL, db_column="parent_id",
                               related_name="children")
    def __str__(self) -> str:            # ← 추가
        return self.name or f"Category {self.pk}"

    class Meta:
        db_table = "categories"
        verbose_name = "Category"         # ← 선택(사이드바 표기 교정)
        verbose_name_plural = "Categories"  # ← "Categorys" → "Categories"
        indexes = [
            models.Index(fields=["parent"]),
            models.Index(fields=["name"]),
        ]

class Product(models.Model):
    product_id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    price = models.IntegerField()
    category = models.ForeignKey(Category, null=True, blank=True,
                                 on_delete=models.SET_NULL, db_column="category_id",
                                 related_name="products")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = "products"
        indexes = [models.Index(fields=["name"]), models.Index(fields=["price"])]
