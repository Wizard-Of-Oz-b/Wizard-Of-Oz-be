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
        max_digits=12, decimal_places=2, required=False, default=0
    )
    # 모델에 order_item FK가 있을 때만 쓰도록 ID로 받음(선택)
    order_item_id = serializers.UUIDField(required=False, allow_null=True)

    def save(self, *, payment: Payment, status: str) -> PaymentCancel:
        data = self.validated_data
        cancel = PaymentCancel(
            payment=payment,
            reason=data.get("reason") or "",
            cancel_amount=data["cancel_amount"],
            tax_free_amount=data.get("tax_free_amount") or 0,
            status=status,
        )
        # 모델에 order_item 필드가 실제로 있을 때만 세팅
        if hasattr(PaymentCancel, "order_item") and data.get("order_item_id"):
            cancel.order_item_id = data["order_item_id"]
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
