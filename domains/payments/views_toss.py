# domains/payments/views_toss.py
import hmac
import hashlib
import base64
import json
import requests

from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiResponse

from domains.orders.models import Purchase
from domains.payments.serializers_toss import (
    TossConfirmRequestSerializer,
    TossCancelRequestSerializer,
)

TOSS_SECRET_KEY = getattr(settings, "TOSS_SECRET_KEY", "")
TOSS_CLIENT_KEY = getattr(settings, "TOSS_CLIENT_KEY", "")

# ---------------------------------------------------------------------
# 유틸: 모델에 존재하는 필드만 안전하게 저장
# ---------------------------------------------------------------------
def _purchase_model_fields():
    return {
        f.name
        for f in Purchase._meta.get_fields()
        if getattr(f, "concrete", False) and not getattr(f, "many_to_many", False)
    }


def _assign_and_save_purchase(purchase, *, status_value, pg_value=None, pg_tid_value=None):
    fields = _purchase_model_fields()
    update_fields = []

    # status는 있다고 가정
    purchase.status = status_value
    update_fields.append("status")

    if "pg" in fields and pg_value is not None:
        purchase.pg = pg_value
        update_fields.append("pg")

    if "pg_tid" in fields and pg_tid_value is not None:
        purchase.pg_tid = pg_tid_value
        update_fields.append("pg_tid")

    purchase.save(update_fields=update_fields)


# ---------------------------------------------------------------------
# 프론트에 Toss clientKey 내려주기
# ---------------------------------------------------------------------
class TossClientKeyAPI(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        return Response({"clientKey": TOSS_CLIENT_KEY})


# ---------------------------------------------------------------------
# 결제 승인(Confirm) - successUrl에서 받은 값을 서버로 전달해 승인 처리
#   - orderId: 숫자 PK(purchase_id) 사용 권장
#   - PG_FAKE_MODE=1 이면 실제 호출 없이 바로 paid 처리
# ---------------------------------------------------------------------
class TossConfirmAPI(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        request=TossConfirmRequestSerializer,
        responses={
            200: OpenApiResponse(description="결제 승인 성공"),
            400: OpenApiResponse(description="승인 실패"),
        },
    )
    def post(self, request):
        payment_key = request.data.get("paymentKey")
        order_id_in = request.data.get("orderId")  # 예: "5" (purchase_id)
        amount_in = request.data.get("amount")

        if not all([payment_key, order_id_in, amount_in]):
            return Response(
                {"detail": "paymentKey, orderId, amount required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 구매 조회: 숫자면 PK(purchase_id)로 조회
        if not str(order_id_in).isdigit():
            return Response(
                {"detail": "orderId must be numeric purchase_id"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        purchase = get_object_or_404(Purchase, pk=int(order_id_in), user=request.user)

        # 금액 검증
        try:
            req_amount = int(amount_in)
        except (TypeError, ValueError):
            return Response(
                {"detail": "amount must be integer"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if req_amount != int(purchase.amount):
            return Response(
                {"detail": "amount mismatch"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if purchase.status == "paid":
            return Response({"detail": "already paid"}, status=status.HTTP_409_CONFLICT)

        # 실제 Toss 승인 호출
        try:
            r = requests.post(
                "https://api.tosspayments.com/v1/payments/confirm",
                auth=(TOSS_SECRET_KEY, ""),  # Basic auth: <secretKey>:
                json={"paymentKey": payment_key, "orderId": str(order_id_in), "amount": req_amount},
                timeout=10,
            )
            data = r.json()
        except requests.RequestException as e:
            return Response(
                {"ok": False, "error": {"message": str(e)}},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        if r.status_code == 200:
            _assign_and_save_purchase(
                purchase,
                status_value="paid",
                pg_value="toss",
                pg_tid_value=data.get("paymentKey"),
            )
            return Response({"ok": True, "payment": data}, status=status.HTTP_200_OK)

        return Response({"ok": False, "error": data}, status=status.HTTP_400_BAD_REQUEST)





# ---------------------------------------------------------------------
# 취소/환불 (운영에선 관리자 권한으로 보호 권장)
#   - PG_FAKE_MODE=1 이면 로컬에서 상태만 변경하여 에뮬레이션
#   - 실제 취소는 구매에 pg_tid가 저장되어 있을 때만 가능
# ---------------------------------------------------------------------
class TossCancelAPI(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        request=TossCancelRequestSerializer,
        responses={
            200: OpenApiResponse(description="취소/환불 성공"),
            400: OpenApiResponse(description="취소/환불 실패"),
        },
    )
    def post(self, request):
        purchase_id = request.data.get("purchase_id")
        cancel_reason = request.data.get("cancel_reason") or "requested by user"
        amount = request.data.get("amount")  # 부분 환불 시 정수

        if not purchase_id:
            return Response({"detail": "purchase_id required"}, status=status.HTTP_400_BAD_REQUEST)
        purchase = get_object_or_404(Purchase, pk=int(purchase_id), user=request.user)



        fields = _purchase_model_fields()
        pg_tid = getattr(purchase, "pg_tid", None) if "pg_tid" in fields else None
        if not pg_tid:
            return Response(
                {"detail": "Payment key (pg_tid) not stored. Cannot cancel."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        url = f"https://api.tosspayments.com/v1/payments/{pg_tid}/cancel"
        payload = {"cancelReason": cancel_reason}
        if amount:
            payload["cancelAmount"] = int(amount)

        try:
            r = requests.post(url, auth=(TOSS_SECRET_KEY, ""), json=payload, timeout=10)
            data = r.json()
        except requests.RequestException as e:
            return Response({"ok": False, "error": {"message": str(e)}}, status=status.HTTP_502_BAD_GATEWAY)

        if r.status_code == 200:
            new_status = "refunded" if amount else "canceled"
            _assign_and_save_purchase(purchase, status_value=new_status)
            return Response({"ok": True, "payment": data}, status=status.HTTP_200_OK)

        return Response({"ok": False, "error": data}, status=status.HTTP_400_BAD_REQUEST)


# ---------------------------------------------------------------------
# 웹훅(선택): 가상계좌 등 비동기 이벤트 처리
# ---------------------------------------------------------------------
class TossWebhookAPI(APIView):
    """
    토스 대시보드에서 웹훅 URL로 설정.
    헤더 'Toss-Signature' 검증(HMAC-SHA256 with secretKey)
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        body = request.body  # bytes
        signature = request.headers.get("Toss-Signature")

        mac = hmac.new(TOSS_SECRET_KEY.encode(), body, hashlib.sha256).digest()
        expected = base64.b64encode(mac).decode()

        if signature != expected:
            return Response({"detail": "invalid signature"}, status=status.HTTP_401_UNAUTHORIZED)

        event = json.loads(body.decode("utf-8"))
        # TODO: event["eventType"] 별로 purchase 갱신 필요 시 구현
        return Response({"ok": True}, status=status.HTTP_200_OK)
