# domains/payments/services.py
from __future__ import annotations

from domains.payments.models import Payment, PaymentStatus

def create_payment_stub(order, *, amount=None) -> Payment:
    """
    결제 전 주문 헤더가 생성된 직후 호출.
    - order_number는 토스 orderId로 사용할 값 (현재는 purchase_id 사용)
    """
    return Payment.objects.create(
        order=order,
        order_number=str(getattr(order, "purchase_id")),  # ✅ 기존 order_id → purchase_id 로 수정
        status=PaymentStatus.READY,
        amount_total=amount if amount is not None else getattr(order, "grand_total", 0),
    )
