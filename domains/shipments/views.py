# domains/shipments/views.py
from typing import Any, Dict, List
import os, logging, requests
from rest_framework import views
from django.shortcuts import get_object_or_404
from django.db.models import Q
from rest_framework import status, parsers, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiParameter

from domains.orders.models import Purchase  # Shipment.order FK 대상
from .models import Shipment
from .serializers import (
    RegisterShipmentSerializer,  # POST /register 입력
    WebhookInSerializer,         # 어댑터 이벤트 입력
    ShipmentSerializer,          # 공통 출력
)
from .services import (
    register_tracking_with_sweettracker,
    upsert_events_from_adapter,
    sync_by_tracking,
)


# --------------------------------------------------------------------
# 공통: role 권한
# --------------------------------------------------------------------
class IsManagerOrAbove(permissions.BasePermission):
    def has_permission(self, request, view):
        u = request.user
        if not u or not u.is_authenticated:
            return False
        return getattr(u, "role", "user") in ("admin", "manager", "cs")


# --------------------------------------------------------------------
# GET /api/v1/shipments  (목록)  page, size 지원
# 응답 형태: { "total": n, "page": p, "size": s, "results": [...] }
# --------------------------------------------------------------------
class ShipmentsListAPI(APIView):
    parser_classes = [parsers.JSONParser]
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        parameters=[
            OpenApiParameter(name="page", required=False, type=int, description="page number (1-base)"),
            OpenApiParameter(name="size", required=False, type=int, description="page size"),
        ],
        responses={200: ShipmentSerializer(many=True)},
    )
    def get(self, request):
        page = int(request.query_params.get("page") or 1)
        size = int(request.query_params.get("size") or 10)
        page = max(page, 1)
        size = max(min(size, 100), 1)

        user = request.user
        role = getattr(user, "role", "user")

        qs = Shipment.objects.select_related("order").order_by("-created_at")
        if role not in ("admin", "manager", "cs"):
            qs = qs.filter(Q(user=user) | Q(order__user=user))

        total = qs.count()
        start = (page - 1) * size
        end = start + size
        rows = qs[start:end]

        data = ShipmentSerializer(rows, many=True).data
        return Response(
            {"total": total, "page": page, "size": size, "results": data},
            status=status.HTTP_200_OK,
        )


# --------------------------------------------------------------------
# GET /api/v1/shipments/{id}  (상세)
# --------------------------------------------------------------------
class ShipmentDetailAPI(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses={200: ShipmentSerializer})
    def get(self, request, id: str):
        """
        id는 UUID가 기본. (urls에 문자열 백업 라우트도 있음)
        """
        # 권한: admin/manager/cs 전체, 일반 유저는 소유분만
        user = request.user
        role = getattr(user, "role", "user")

        base_qs = Shipment.objects.select_related("order")
        if role in ("admin", "manager", "cs"):
            obj = get_object_or_404(base_qs, id=id)
        else:
            obj = get_object_or_404(
                base_qs.filter(Q(user=user) | Q(order__user=user)),
                id=id,
            )
        return Response(ShipmentSerializer(obj).data, status=status.HTTP_200_OK)


# --------------------------------------------------------------------
# POST /api/v1/shipments/register/  (추가 등록용 - 선택)
# body: {purchase_id, tracking_number, carrier}
# --------------------------------------------------------------------
class RegisterShipmentAPI(APIView):
    parser_classes = [parsers.JSONParser]
    permission_classes = [IsManagerOrAbove]

    @extend_schema(request=RegisterShipmentSerializer, responses={201: ShipmentSerializer})
    def post(self, request):
        ser = RegisterShipmentSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        purchase_id = ser.validated_data.get("purchase_id")
        tracking_number = ser.validated_data["tracking_number"]
        carrier = ser.validated_data["carrier"]

        user = request.user
        role = getattr(user, "role", "user")

        if role in ("admin", "manager", "cs"):
            purchase = get_object_or_404(Purchase, pk=purchase_id)
            owner = getattr(purchase, "user", user)
        else:
            purchase = get_object_or_404(Purchase, pk=purchase_id, user=user)
            owner = user

        shipment = register_tracking_with_sweettracker(
            tracking_number=tracking_number,
            carrier=carrier,
            user=owner,
            order=purchase,
        )
        return Response(ShipmentSerializer(shipment).data, status=status.HTTP_201_CREATED)


# --------------------------------------------------------------------
# POST /api/v1/shipments/sync/
# 모드 A) {purchase_id, tracking_number, carrier}  → 등록(+fetch) / created:0|1
# 모드 B) WebhookInSerializer 스키마 재사용(이벤트 직접 upsert)
# --------------------------------------------------------------------
class ShipmentSyncAPI(APIView):
    parser_classes = [parsers.JSONParser]
    permission_classes = [IsManagerOrAbove]

    @extend_schema(request=WebhookInSerializer, responses={200: dict})
    def post(self, request):
        data: Dict[str, Any] = request.data or {}

        # ----- 모드 A: 등록 + 즉시 동기화 -----
        if {"purchase_id", "tracking_number", "carrier"} <= set(data.keys()):
            purchase_id = data.get("purchase_id")
            tracking_number = str(data.get("tracking_number"))
            carrier = str(data.get("carrier"))

            user = request.user
            role = getattr(user, "role", "user")
            if role in ("admin", "manager", "cs"):
                purchase = get_object_or_404(Purchase, pk=purchase_id)
                owner = getattr(purchase, "user", user)
            else:
                purchase = get_object_or_404(Purchase, pk=purchase_id, user=user)
                owner = user

            existed = Shipment.objects.filter(order=purchase, tracking_number=tracking_number).exists()

            register_tracking_with_sweettracker(
                tracking_number=tracking_number,
                carrier=carrier,
                user=owner,
                order=purchase,
            )
            created_events = sync_by_tracking(carrier=carrier, tracking_number=tracking_number)
            # 외부 계약: "created"는 shipment 기준 idempotent 의미로 반환
            return Response({"created": 0 if existed else 1}, status=status.HTTP_200_OK)

        # ----- 모드 B: 이벤트 payload로 동기화 -----
        ser = WebhookInSerializer(data=data)
        ser.is_valid(raise_exception=True)
        created_cnt = upsert_events_from_adapter(ser.validated_data)
        return Response({"created": created_cnt}, status=status.HTTP_200_OK)


# --------------------------------------------------------------------
# POST /api/v1/shipments/webhooks/{carrier}/
#  -> 어댑터 이벤트 입력: WebhookInSerializer로 정규화 후 upsert
# --------------------------------------------------------------------
class ShipmentWebhookAPI(APIView):
    permission_classes = [permissions.AllowAny]
    parser_classes = [parsers.JSONParser]

    @extend_schema(request=WebhookInSerializer, responses={200: dict})
    def post(self, request, carrier: str):
        # URL 경로의 carrier를 payload에 주입해 어댑터가 식별 가능하도록
        data = dict(request.data or {})
        data.setdefault("carrier", carrier)
        ser = WebhookInSerializer(data=data)
        ser.is_valid(raise_exception=True)

        created_cnt = upsert_events_from_adapter(ser.validated_data)
        return Response({"created": created_cnt}, status=status.HTTP_200_OK)

class ShipmentTrackAPI(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        parameters=[
            OpenApiParameter(name="carrier", required=False, type=str, description="택배사 코드(예: 04)"),
            OpenApiParameter(name="invoice", required=True, type=str, description="운송장 번호"),
        ],
        responses={200: dict},
    )
    def get(self, request):
        carrier = request.query_params.get("carrier")
        invoice = request.query_params.get("invoice")

        if not invoice:
            return Response({"detail": "invoice는 필수입니다."}, status=status.HTTP_400_BAD_REQUEST)

        host = os.getenv("SMARTPARCEL_HOST", "").rstrip("/")
        if not host:
            logging.error("SMARTPARCEL_HOST not set")
            return Response({"detail": "연동 설정 누락(SMARTPARCEL_HOST)"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        url = f"{host}/track"
        params = {"invoice": invoice}
        if carrier:
            params["carrier"] = carrier

        try:
            resp = requests.get(url, params=params, timeout=8)
        except requests.Timeout:
            logging.exception("sweettracker_timeout")
            return Response({"detail": "연동 타임아웃"}, status=status.HTTP_504_GATEWAY_TIMEOUT)
        except Exception:
            logging.exception("sweettracker_unhandled")
            return Response({"detail": "연동 중 알 수 없는 오류"}, status=status.HTTP_502_BAD_GATEWAY)

        if resp.status_code != 200:
            logging.warning("sweettracker_non200 status=%s body_head=%r", resp.status_code, resp.text[:300])
            return Response(
                {"detail": "연동 실패", "upstream_status": resp.status_code},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        # JSON 방어
        try:
            data = resp.json()
        except Exception:
            logging.exception("sweettracker_invalid_json")
            return Response({"detail": "연동 응답이 JSON이 아닙니다."}, status=status.HTTP_502_BAD_GATEWAY)

        # 가공 없이 패스스루
        return Response(data, status=status.HTTP_200_OK)