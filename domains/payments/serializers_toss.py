from rest_framework import serializers

class TossConfirmRequestSerializer(serializers.Serializer):
    paymentKey = serializers.CharField()
    orderId    = serializers.CharField()
    amount     = serializers.IntegerField(min_value=0)

class TossCancelRequestSerializer(serializers.Serializer):
    purchase_id   = serializers.IntegerField()
    cancel_reason = serializers.CharField(required=False, allow_blank=True)
    amount        = serializers.IntegerField(required=False, min_value=0)  # 부분환불용
