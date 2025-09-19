# domains/orders/admin.py
from .models import Purchase, PurchaseStatus, OrderItem
from django.contrib import admin


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
    readonly_fields = ()  # 필요하면 ("purchased_at",) 등 추가


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ("item_id", "order", "product", "option_key", "quantity", "unit_price", "created_at")

