
from django.contrib import admin
from .models import Cart, CartItem

@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "expires_at", "updated_at")
    search_fields = ("user__email",)

@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ("id", "cart", "product", "option_key", "quantity", "unit_price", "added_at")
    autocomplete_fields = ("cart", "product")
    list_select_related = ("cart", "product")
