# domains/orders/admin.py
from django.contrib import admin

from .models import OrderItem, Purchase


@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = (
        "purchase_id",
        "user",
        "product",
        "status",
        "amount",
        "unit_price",
        "items_total",
        "grand_total",
        "purchased_at",
    )
    list_filter = ("status", "purchased_at")
    search_fields = (
        "purchase_id",
        "user__email",
        "user__username",
        "product__name",
        "pg",
        "pg_tid",
    )
    ordering = ("-purchased_at",)
    # 필요 시 읽기전용 필드를 추가하세요.
    # readonly_fields = ("purchased_at",)


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = (
        "item_id",
        "order",
        "product",
        "option_key",
        "quantity",
        "unit_price",
        "created_at",
    )
    search_fields = ("order__purchase_id", "product__name")
    ordering = ("-created_at",)
