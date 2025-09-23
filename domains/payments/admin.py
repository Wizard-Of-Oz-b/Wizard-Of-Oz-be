from django.contrib import admin
# ✅ 그냥 로컬 모델에서 바로 import 하세요
from .models import Payment, PaymentEvent, PaymentCancel


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("payment_id", "order", "provider", "status", "amount_total",
                    "approved_at", "canceled_at")
    list_filter = ("provider", "status", "created_at")
    search_fields = ("payment_id", "provider_payment_key", "order_number")


@admin.register(PaymentEvent)
class PaymentEventAdmin(admin.ModelAdmin):
    list_display = ("event_id", "payment", "source", "event_type",
                    "provider_status", "created_at")
    list_filter = ("source", "event_type", "provider_status")


@admin.register(PaymentCancel)
class PaymentCancelAdmin(admin.ModelAdmin):
    list_display = ("cancel_id", "payment", "cancel_amount",
                    "status", "approved_at", "created_at")
    list_filter = ("status",)
