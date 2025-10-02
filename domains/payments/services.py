from __future__ import annotations

from typing import Any, Dict, Optional

from django.apps import apps
from django.db import transaction
from django.utils import timezone

from rest_framework.exceptions import ValidationError


# ===== 모델 지연 로딩 헬퍼 =====
def Payment():
    return apps.get_model("payments", "Payment")


def PaymentEvent():
    return apps.get_model("payments", "PaymentEvent")


# ===== 상태 문자열 상수(순환 방지용) =====
ORDER_STATUS_READY = "ready"
ORDER_STATUS_PAID = "paid"
ORDER_STATUS_CANCELED = "canceled"

PAYMENT_STATUS_READY = "ready"
PAYMENT_STATUS_IN_PROGRESS = "in_progress"
PAYMENT_STATUS_WAITING_FOR_DEPOSIT = "waiting_for_deposit"
PAYMENT_STATUS_PAID = "paid"
PAYMENT_STATUS_CANCELED = "canceled"


def _record_event(
    *,
    payment_obj,
    source: str,
    event_type: str,
    provider_status: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
    dedupe_key: Optional[str] = None,
    occurred_at=None,
):
    ev_model = PaymentEvent()
    ev = ev_model(
        payment=payment_obj,
        source=source,
        event_type=event_type,
        provider_status=provider_status,
        payload=payload or {},
        dedupe_key=dedupe_key,
        occurred_at=occurred_at or timezone.now(),
    )
    ev.save()
    return ev


@transaction.atomic
def create_payment_stub(order, *, amount: Optional[Any] = None):
    """
    결제 시작 전, 주문 헤더 생성 직후 호출(멱등):
    - 같은 주문에 'ready' 결제가 있으면 그대로 반환
    - amount 없으면 order.grand_total 사용
    - order_number = purchase_id
    """
    pay_model = Payment()

    ready = pay_model.objects.filter(order=order, status=PAYMENT_STATUS_READY).first()
    if ready:
        return ready

    amt = amount if amount is not None else getattr(order, "grand_total", 0)

    pay = pay_model.objects.create(
        order=order,
        status=PAYMENT_STATUS_READY,
        amount_total=amt,
        order_number=str(getattr(order, "purchase_id")),
        requested_at=timezone.now(),
    )
    _record_event(
        payment_obj=pay,
        source="api",
        event_type="stub_created",
        provider_status=pay.status,
        payload={"amount_total": str(amt)},
    )
    return pay


@transaction.atomic
def confirm_payment(
    payment_obj,
    *,
    provider_payment_key: Optional[str],
    provider_payload: Optional[Dict[str, Any]] = None,
):
    """
    승인(컨펌) 완료:
    - Payment: ready/in_progress/waiting_for_deposit -> paid
    - Purchase: ready -> paid
    - checkout에서 라인/재고 처리는 끝난 상태. 여기선 카트 정리만.
    """
    if getattr(payment_obj, "status") == PAYMENT_STATUS_PAID:
        return payment_obj

    if payment_obj.status not in (
        PAYMENT_STATUS_READY,
        PAYMENT_STATUS_IN_PROGRESS,
        PAYMENT_STATUS_WAITING_FOR_DEPOSIT,
    ):
        raise ValidationError(
            {"payment": f"invalid state to confirm: {payment_obj.status}"}
        )

    payment_obj.provider_payment_key = (
        provider_payment_key or payment_obj.provider_payment_key
    )
    payment_obj.status = PAYMENT_STATUS_PAID
    payment_obj.approved_at = timezone.now()
    payment_obj.updated_at = timezone.now()
    payment_obj.save()

    if provider_payload:
        _record_event(
            payment_obj=payment_obj,
            source="api",
            event_type="approval",
            provider_status=payment_obj.status,
            payload=provider_payload,
            dedupe_key=(
                provider_payload.get("transactionKey")
                if isinstance(provider_payload, dict)
                else None
            ),
        )

    order = payment_obj.order
    if getattr(order, "status") == ORDER_STATUS_READY:
        order.status = ORDER_STATUS_PAID
        order.save(update_fields=["status"])

    # 카트 비우기 (지연 import)
    from domains.carts.services import clear_cart as clear_cart_items, get_user_cart

    cart = get_user_cart(order.user, create=False)
    clear_cart_items(cart)

    return payment_obj


@transaction.atomic
def cancel_payment(
    payment_obj, *, reason: str = "", provider_payload: Optional[Dict[str, Any]] = None
):
    """
    승인 전 취소:
    - Payment: canceled
    - Purchase: ready였다면 canceled + 재고 복구
    """
    if getattr(payment_obj, "status") == PAYMENT_STATUS_CANCELED:
        return payment_obj

    order = payment_obj.order

    if getattr(order, "status") == ORDER_STATUS_READY:
        # 재고 복구 (지연 import)
        from domains.catalog.services import release_stock

        for oi in order.items.all():
            release_stock(oi.product_id, oi.option_key or "", oi.quantity)
        order.status = ORDER_STATUS_CANCELED
        order.save(update_fields=["status"])

    payment_obj.status = PAYMENT_STATUS_CANCELED
    payment_obj.canceled_at = timezone.now()
    payment_obj.updated_at = timezone.now()
    payment_obj.save()

    _record_event(
        payment_obj=payment_obj,
        source="api",
        event_type="cancel",
        provider_status=payment_obj.status,
        payload={"reason": reason, "provider": provider_payload or {}},
    )
    return payment_obj
