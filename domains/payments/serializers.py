from decimal import Decimal

from django.apps import apps
from django.core.exceptions import ObjectDoesNotExist

from rest_framework import serializers

from .models import Payment, PaymentCancel, PaymentEvent


class PaymentReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = (
            "payment_id",
            "order_id",  # 모델에 없다면 지우세요
            "order_number",
            "status",
            "amount_total",
            "vat",
            "method",
            "provider",
            "provider_payment_key",
            "approved_at",
            "canceled_at",
            "created_at",
            "updated_at",
        )


class PaymentCancelRequestSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True)
    cancel_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    tax_free_amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, default=Decimal("0.00")
    )
    order_item_id = serializers.UUIDField(required=False, allow_null=True)

    def save(self, *, payment: Payment, status: str) -> PaymentCancel:  # type: ignore[override]
        data = self.validated_data

        cancel = PaymentCancel(
            payment=payment,
            reason=data.get("reason") or "",
            cancel_amount=data["cancel_amount"],
            tax_free_amount=data.get("tax_free_amount") or Decimal("0.00"),
            status=status,
        )

        # ✅ 모델에 order_item 필드가 실제로 존재하고, order_item_id가 주어진 경우만 처리
        model_fields = {f.name for f in PaymentCancel._meta.get_fields()}
        if "order_item" in model_fields and data.get("order_item_id"):
            try:
                OrderItem = apps.get_model("orders", "OrderItem")
                cancel.order_item = OrderItem.objects.get(id=data["order_item_id"])  # type: ignore[attr-defined]
            except ObjectDoesNotExist:
                raise serializers.ValidationError(
                    {"order_item_id": "Invalid OrderItem ID"}
                )

        cancel.save()
        return cancel


class PaymentEventReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentEvent
        fields = (
            "event_id",
            "payment",
            "source",
            "event_type",
            "provider_status",
            "payload",
            "occurred_at",
            "created_at",
        )
        read_only_fields = fields
