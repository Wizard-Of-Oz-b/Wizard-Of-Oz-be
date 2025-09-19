from rest_framework import serializers

class TossConfirmRequestSerializer(serializers.Serializer):
    paymentKey = serializers.CharField(max_length=200)
    orderId    = serializers.CharField(max_length=100)
    amount     = serializers.DecimalField(max_digits=12, decimal_places=2)

class TossCancelRequestSerializer(serializers.Serializer):
    purchase_id   = serializers.IntegerField()
    cancel_reason = serializers.CharField(required=False, allow_blank=True)
    amount        = serializers.IntegerField(required=False, min_value=0)  # 부분환불용
