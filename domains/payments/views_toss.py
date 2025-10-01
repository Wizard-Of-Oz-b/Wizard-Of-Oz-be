# domains/payments/views_toss.py
from __future__ import annotations

from decimal import Decimal
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.utils import timezone
from rest_framework import permissions, status, views
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from drf_spectacular.utils import extend_schema

from .models import Payment, PaymentEvent, PaymentStatus, CancelStatus
from .serializers import PaymentReadSerializer, PaymentCancelRequestSerializer
from .serializers_toss import TossConfirmRequestSerializer
from .toss_client import confirm as toss_confirm, retrieve_by_key, cancel as toss_cancel
from domains.orders.models import PurchaseStatus  # 주문 헤더 상태 동기화용

from domains.carts.models import CartItem


# ─────────────────────────────────────────────────────────────────────────────
# 승인(Confirm): paymentKey, orderId(=Payment.order_number), amount
# ─────────────────────────────────────────────────────────────────────────────
class TossConfirmAPI(views.APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        operation_id="TossConfirm",
        request=TossConfirmRequestSerializer,
        responses={200: PaymentReadSerializer, 400: dict, 404: dict},
    )
    def post(self, request):
        ser = TossConfirmRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        payment_key: str = ser.validated_data["paymentKey"]
        order_id: str = ser.validated_data["orderId"]          # = Payment.order_number
        amount: Decimal = ser.validated_data["amount"]

        # 1) 스텁 조회 & 락 (트랜잭션 밖에서 처리)
        with transaction.atomic():
            payment = (
                Payment.objects.select_for_update()
                .filter(order_number=order_id)
                .first()
            )
            if not payment:
                return Response({"detail": "payment stub not found (order_number)"}, status=404)

            # 2) 중복 컨펌 방지
            if payment.status == PaymentStatus.PAID:
                return Response({"detail": "already confirmed"}, status=400)

            # 3) 금액 일치 검증(있다면)
            if payment.amount_total and Decimal(str(payment.amount_total)) != Decimal(str(amount)):
                return Response(
                    {"detail": "amount mismatch", "expected": str(payment.amount_total), "got": str(amount)},
                    status=400,
                )

        # 4) Toss confirm 호출 (재고 검증은 checkout 단계에서 이미 완료)
        data = toss_confirm(payment_key, order_id, amount)

        # 6) Payment 상태/스냅샷 반영 (트랜잭션 밖에서 처리)
        provider_done = (data.get("status") == "DONE")
        with transaction.atomic():
            payment.provider_payment_key = data.get("paymentKey") or payment.provider_payment_key
            payment.method = (data.get("method") or "").lower() or payment.method
            if provider_done:
                payment.status = PaymentStatus.PAID
            payment.amount_total = data.get("totalAmount") or payment.amount_total
            payment.vat = data.get("vat") or payment.vat or 0
            payment.approved_at = timezone.now()
            payment.receipt_url = (data.get("receipt") or {}).get("url") or payment.receipt_url
            payment.card_info = data.get("card") or payment.card_info
            payment.easy_pay = data.get("easyPay") or payment.easy_pay
            payment.touch()
            payment.save()
        
        # ✅ 7) OrderItem은 이미 체크아웃에서 생성됨 (confirm에서는 장바구니 확인 안함)
        if provider_done:
            # OrderItem이 없으면 체크아웃 과정에서 문제가 있었던 것
            from domains.orders.models import OrderItem
            if not OrderItem.objects.filter(order=payment.order).exists():
                # 🚨 체크아웃 과정에서 OrderItem이 생성되지 않았음
                # 토스 결제 취소 시도
                try:
                    toss_cancel(data.get("paymentKey"), "주문 정보 누락으로 인한 결제 취소")
                except Exception as cancel_error:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"토스 결제 취소 실패: {cancel_error}, Payment ID: {payment.id}")
                
                # Payment 상태를 READY로 롤백
                with transaction.atomic():
                    payment.status = PaymentStatus.READY
                    payment.save(update_fields=["status"])
                
                return Response({"detail": "주문 정보가 누락되었습니다. 다시 주문해주세요."}, status=500)

        # 8) 이벤트 로그 (별도 트랜잭션)
        with transaction.atomic():
            PaymentEvent.objects.create(
                payment=payment,
                source="api",
                event_type="approval",
                provider_status=payment.status,
                payload=data,
                occurred_at=timezone.now(),
            )

        # 9) 주문 헤더 상태 동기화 (ready -> paid) (별도 트랜잭션)
        with transaction.atomic():
            try:
                order = payment.order  # FK: Payment -> Purchase
            except Exception:
                order = None
            if order and order.status != PurchaseStatus.PAID:
                order.status = PurchaseStatus.PAID
                order.save(update_fields=["status"])

                # ✅ 장바구니 비우기는 checkout에서 이미 처리됨

        return Response(PaymentReadSerializer(payment).data, status=status.HTTP_200_OK)


# ─────────────────────────────────────────────────────────────────────────────
# 조회: payment_id로 조회
# ─────────────────────────────────────────────────────────────────────────────
class PaymentRetrieveAPI(views.APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(operation_id="PaymentRetrieve", responses={200: PaymentReadSerializer, 404: dict})
    def get(self, request, payment_id):
        payment = get_object_or_404(Payment, pk=payment_id)
        return Response(PaymentReadSerializer(payment).data)


# ─────────────────────────────────────────────────────────────────────────────
# 싱크: Toss 최신 상태 반영
# ─────────────────────────────────────────────────────────────────────────────
class TossSyncAPI(views.APIView):
    permission_classes = [permissions.IsAdminUser]

    @extend_schema(operation_id="TossSync", responses={200: PaymentReadSerializer, 400: dict, 404: dict})
    @transaction.atomic
    def post(self, request, payment_id):
        payment = get_object_or_404(Payment, pk=payment_id)
        if not payment.provider_payment_key:
            return Response({"detail": "provider_payment_key is empty"}, status=400)

        data = retrieve_by_key(payment.provider_payment_key)

        toss_status = data.get("status")
        if toss_status == "DONE":
            payment.status = PaymentStatus.PAID
        elif toss_status == "CANCELED":
            payment.status = PaymentStatus.CANCELED
        # 필요 시 추가 매핑

        payment.last_synced_at = timezone.now()
        payment.touch()
        payment.save()

        PaymentEvent.objects.create(
            payment=payment,
            source="sync",
            event_type="status_changed",
            provider_status=payment.status,
            payload=data,
            occurred_at=timezone.now(),
        )
        return Response(PaymentReadSerializer(payment).data)


# ─────────────────────────────────────────────────────────────────────────────
# 취소(부분/전액)
# ─────────────────────────────────────────────────────────────────────────────
class TossCancelAPI(views.APIView):
    permission_classes = [permissions.IsAdminUser]

    @extend_schema(
        operation_id="TossCancel",
        request=PaymentCancelRequestSerializer,
        responses={200: PaymentReadSerializer, 400: dict, 404: dict},
    )
    @transaction.atomic
    def post(self, request, payment_id):
        payment = get_object_or_404(Payment, pk=payment_id)
        if not payment.provider_payment_key:
            return Response({"detail": "provider_payment_key is empty"}, status=400)

        ser = PaymentCancelRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        cancel = ser.save(payment=payment, status=CancelStatus.REQUESTED)

        data = toss_cancel(
            payment_key=payment.provider_payment_key,
            amount=cancel.cancel_amount,
            reason=cancel.reason or "cancel by admin",
            tax_free_amount=cancel.tax_free_amount or 0,
        )

        # Payment 반영
        is_partial = data.get("status") == "PARTIAL_CANCELED"
        payment.status = PaymentStatus.PARTIAL_CANCELED if is_partial else PaymentStatus.CANCELED
        payment.canceled_at = timezone.now()
        payment.touch()
        payment.save()

        # 이벤트 로그
        cancel.status = CancelStatus.DONE
        cancel.approved_at = timezone.now()
        cancel.save()

        PaymentEvent.objects.create(
            payment=payment,
            source="api",
            event_type="cancel",
            provider_status=payment.status,
            payload=data,
            occurred_at=timezone.now(),
        )

        # 주문 헤더 상태 동기화: 전액 취소일 때만 canceled 로 전환
        try:
            order = payment.order
        except Exception:
            order = None
        if order:
            total = Decimal(str(payment.amount_total or 0))
            canceled_amt = Decimal(str(cancel.cancel_amount or 0))
            if canceled_amt >= total and order.status != PurchaseStatus.CANCELED:
                order.status = PurchaseStatus.CANCELED
                order.save(update_fields=["status"])
            # 부분취소는 정책상 헤더 유지(필요 시 별도 상태 추가)

        return Response(PaymentReadSerializer(payment).data, status=200)
