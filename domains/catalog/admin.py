# domains/catalog/admin.py
from django.contrib import admin
from .models import Category, Product, ProductStock

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    # ❌ parent / category_id 사용 금지 → ✅ id, name 등으로
    list_display = ("id", "name", "created_at", "updated_at")
    search_fields = ("name",)
    ordering = ("name",)
    # parent 필드가 삭제되었으므로 관련 옵션 전부 제거
    # raw_id_fields = ("parent",)  # 제거
    # list_filter = ("parent",)    # 제거

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    # ❌ product_id → ✅ id / category_id → ✅ category
    list_display = ("id", "name", "category", "price", "is_active", "updated_at")
    list_filter = ("is_active", "category")
    search_fields = ("name",)
    autocomplete_fields = ("category",)
    ordering = ("-updated_at",)

@admin.register(ProductStock)
class ProductStockAdmin(admin.ModelAdmin):
    list_display = ("id", "product", "option_key", "stock_quantity", "updated_at")
    search_fields = ("product__name", "option_key")
    autocomplete_fields = ("product",)
    list_select_related = ("product",)
