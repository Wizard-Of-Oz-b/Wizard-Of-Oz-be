# domains/shipments/views.py
from typing import Any, Dict, List

from django.shortcuts import get_object_or_404
from rest_framework import status, parsers, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiParameter

from domains.orders.models import Purchase  # Shipment.order FK 대상
from .models import Shipment, ShipmentEvent  # 모델 참조
from .serializers import (
    RegisterShipmentSerializer,  # 등록 입력용 (필요 시 유지)
    WebhookInSerializer,         # 웹훅/동기화 입력용
    ShipmentSerializer,          # 공통 출력용
)
from .services import register_tracking_with_sweettracker, upsert_events_from_adapter


# --------------------------------------------------------------------
# GET /api/v1/shipments  (내 배송 목록 조회)  page, size 지원
# --------------------------------------------------------------------
class ShipmentsListAPI(APIView):
    parser_classes = [parsers.JSONParser]
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        parameters=[
            OpenApiParameter(name="page", description="페이지(1부터)", required=False, type=int, default=1),
            OpenApiParameter(name="size", description="페이지 크기(1~100)", required=False, type=int, default=20),
        ],
        responses={200: ShipmentSerializer(many=True)},
    )
    def get(self, request):
        try:
            page = int(request.query_params.get("page", 1))
        except ValueError:
            page = 1
        try:
            size = int(request.query_params.get("size", 20))
        except ValueError:
            size = 20

        page = max(1, page)
        size = min(max(1, size), 100)

        qs = (
            Shipment.objects
            .filter(user=request.user)
            .order_by("-created_at")
        )
        total = qs.count()
        start = (page - 1) * size
        end = start + size
        items = qs[start:end]

        data = ShipmentSerializer(items, many=True).data
        return Response(
            {"total": total, "page": page, "size": size, "results": data},
            status=status.HTTP_200_OK,
        )


# --------------------------------------------------------------------
# GET /api/v1/shipments/{id}  (배송 상세 조회)
# 이벤트 간단 포함(정렬: 발생시각 오름차순)
# --------------------------------------------------------------------
class ShipmentDetailAPI(APIView):
    parser_classes = [parsers.JSONParser]
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses=ShipmentSerializer)
    def get(self, request, id):
        shipment = get_object_or_404(Shipment, id=id, user=request.user)
        data = ShipmentSerializer(shipment).data

        # 허용된 필드만 강제 (유령 키 차단)
        allowed = set(ShipmentSerializer.Meta.fields)
        data = {k: data.get(k) for k in allowed}

        # 이벤트를 직렬화해서 붙이기
        events_qs = shipment.events.order_by("occurred_at")
        data["events"] = [
            {
                "id": str(e.id),
                "occurred_at": e.occurred_at,
                "status": e.status,
                "location": e.location,
                "description": e.description,
                "provider_code": e.provider_code,
                "source": e.source,
            }
            for e in events_qs
        ]

        return Response(data, status=status.HTTP_200_OK)



# --------------------------------------------------------------------
# POST /api/v1/shipments/sync  (운송장 동기화 - Manager)
# 바디: WebhookInSerializer 스키마 재사용
# ex) {"carrier":"kr.cjlogistics","tracking_number":"123","events":[...]}
# --------------------------------------------------------------------
class ShipmentSyncAPI(APIView):
    parser_classes = [parsers.JSONParser]
    permission_classes = [permissions.IsAdminUser]  # Manager 전용으로 가정

    @extend_schema(request=WebhookInSerializer, responses={200: dict})
    def post(self, request):
        ser = WebhookInSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        created = upsert_events_from_adapter(ser.validated_data)
        return Response({"created": created}, status=status.HTTP_200_OK)


# --------------------------------------------------------------------
# POST /api/v1/webhooks/shipments/{carrier}  (웹훅 수신 - Public)
# path param의 carrier를 payload에 주입한 뒤 upsert
# --------------------------------------------------------------------
class ShipmentWebhookAPI(APIView):
    parser_classes = [parsers.JSONParser]
    permission_classes = [permissions.AllowAny]

    @extend_schema(request=WebhookInSerializer, responses={200: dict})
    def post(self, request, carrier: str):
        payload = dict(request.data) if isinstance(request.data, dict) else {}
        payload.setdefault("carrier", carrier)

        ser = WebhookInSerializer(data=payload)
        ser.is_valid(raise_exception=True)

        data = ser.validated_data
        # ✅ 검증 후 주입: serializer가 source 필드를 몰라도 여기선 들어간다
        for ev in data.get("events", []):
            ev["source"] = "webhook"

        created = upsert_events_from_adapter(data)
        return Response({"created": created}, status=status.HTTP_200_OK)


# --------------------------------------------------------------------
# (선택) 기존 사용자 등록 API를 유지하고 싶다면 그대로 사용 가능
# 명세서에는 없지만, 프론트에서 등록 트리거가 필요할 수 있으니 남겨둠.
# --------------------------------------------------------------------
class RegisterShipmentAPI(APIView):
    parser_classes = [parsers.JSONParser]
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = RegisterShipmentSerializer

    @extend_schema(request=RegisterShipmentSerializer, responses=ShipmentSerializer)
    def post(self, request):
        ser = self.serializer_class(data=request.data)
        ser.is_valid(raise_exception=True)

        purchase_id = ser.validated_data.get("purchase_id")
        purchase = get_object_or_404(Purchase, purchase_id=purchase_id, user=request.user)

        shipment = register_tracking_with_sweettracker(
            tracking_number=ser.validated_data["tracking_number"],
            carrier=ser.validated_data["carrier"],  # 내부 모델 필드는 carrier 사용
            user=request.user,
            order=purchase,  # Shipment.order = Purchase FK
        )
        return Response(ShipmentSerializer(shipment).data, status=status.HTTP_201_CREATED)
