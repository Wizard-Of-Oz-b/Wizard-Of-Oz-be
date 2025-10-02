from __future__ import annotations

from rest_framework import serializers

from .models import Shipment, ShipmentEvent


# ---------------------------
# 출력용: ShipmentSerializer
# ---------------------------
class ShipmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shipment
        fields = (
            "id",
            "carrier",
            "tracking_number",
            "status",
            "shipped_at",
            "delivered_at",
            "canceled_at",
            "last_event_at",
            "last_event_status",
            "last_event_loc",
            "last_event_desc",
            "last_synced_at",
            "created_at",
            "updated_at",
        )


# ---------------------------
# 입력용: 등록 요청
# carrier / carrier_code 둘 다 받되
# validate에서 carrier 로 정규화
# ---------------------------
class RegisterShipmentSerializer(serializers.Serializer):
    purchase_id = serializers.UUIDField()
    tracking_number = serializers.CharField(max_length=64)
    carrier = serializers.CharField(required=False, allow_blank=True)
    carrier_code = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        tracking_number = attrs.get("tracking_number")
        carrier = attrs.get("carrier")
        carrier_code = attrs.get("carrier_code")

        if not tracking_number:
            raise serializers.ValidationError({"tracking_number": "필수 값입니다."})

        normalized_carrier = carrier or carrier_code
        if not normalized_carrier:
            raise serializers.ValidationError(
                "carrier 또는 carrier_code 중 하나는 필수입니다."
            )

        # 내부 표준 키로 정규화
        attrs["carrier"] = normalized_carrier
        attrs.pop("carrier_code", None)
        return attrs


# ---------------------------
# (웹훅/어댑터) 입력용
# 넉넉히 받고 carrier 로 정규화
# ---------------------------
class WebhookInSerializer(serializers.Serializer):
    # 흔히 오는 키들 가정 (없어도 동작 가능)
    tracking_number = serializers.CharField(required=False, allow_blank=True)
    carrier = serializers.CharField(required=False, allow_blank=True)
    carrier_code = serializers.CharField(required=False, allow_blank=True)

    # 이벤트들의 리스트가 올 수 있음
    # 각 아이템에서 발생 시각/상태/위치/설명/공급자코드/원본페이로드 등을 추출
    events = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        allow_empty=True,
    )

    # 원본 그대로 보관할 수도 있음
    payload = serializers.DictField(required=False)

    def validate(self, attrs):
        # carrier/carrier_code 정규화
        attrs["carrier"] = attrs.get("carrier") or attrs.get("carrier_code") or ""
        attrs.pop("carrier_code", None)
        return attrs
