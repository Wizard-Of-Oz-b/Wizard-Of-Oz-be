from django.contrib import admin
from .models import Category, Product

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("category_id", "name", "parent")
    list_filter = ("parent",)
    search_fields = ("name",)
    # 대량 카테고리일 때 속도 개선
    raw_id_fields = ("parent",)

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("product_id", "name", "price", "category", "is_active", "created_at")
    list_filter = ("is_active", "category")
    search_fields = ("name", "description")
    # select2 자동완성 사용
    autocomplete_fields = ("category",)
