# domains/orders/services.py
from __future__ import annotations

from typing import List
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError  # ✅ DRF 예외로 통일

from domains.carts.models import Cart
from domains.carts.services import clear_cart as clear_cart_items  # ✅ 장바구니 비우기 헬퍼
from domains.catalog.services import (
    reserve_stock,
    release_stock,
    OutOfStockError,
    StockRowMissing,
)
from .models import Purchase


@transaction.atomic
def checkout_user_cart(user, *, clear_cart: bool = True) -> List[Purchase]:
    """
    유저의 장바구니를 주문(Purchase)으로 전환.
    - 모든 아이템에 대해 재고 확보가 성공해야만 주문 생성 (원자적)
    - 실패 시 전체 롤백
    - 성공 시 장바구니 비우기 (옵션)
    """
    # 1) 카트 로드
    cart = (
        Cart.objects.select_related("user")
        .filter(user=user)
        .first()
    )
    if not cart:
        raise ValidationError({"cart": "장바구니가 없습니다."})

    # 아이템 잠금 + 순서 고정(데드락 예방)
    items = (
        cart.items.select_related("product")
        .select_for_update()
        .order_by("product_id", "option_key")
    )
    if not items.exists():
        raise ValidationError({"cart": "장바구니가 비어 있습니다."})

    # 2) 재고 확보(모두 성공해야 진행)
    try:
        for it in items:
            # 옵션 없는 상품이면 option_key는 빈 문자열("")일 수 있음
            reserve_stock(it.product_id, it.option_key or "", it.quantity)
    except (OutOfStockError, StockRowMissing) as e:
        # 트랜잭션 롤백 → 클라이언트에 깔끔한 메시지 전달
        raise ValidationError({"stock": str(e)})

    # 3) 구매 레코드 생성 (스냅샷 저장: unit_price / options / option_key)
    now = timezone.now()
    purchases_to_create: List[Purchase] = []
    for it in items:
        purchases_to_create.append(
            Purchase(
                user=user,
                product_id=it.product_id,
                amount=it.quantity,        # ⚠️ 너의 모델에서 amount=수량(정수)로 사용 중
                unit_price=it.unit_price,  # 단가 스냅샷
                options=it.options or {},  # 옵션 스냅샷(JSON)
                option_key=it.option_key or "",
                status=Purchase.STATUS_PAID,
                purchased_at=now,          # 모델에서 auto_now_add면 생략 가능
            )
        )
    Purchase.objects.bulk_create(purchases_to_create)

    # 4) (옵션) 장바구니 비우기
    if clear_cart:
        clear_cart_items(cart)

    return purchases_to_create


@transaction.atomic
def cancel_purchase(purchase: Purchase) -> Purchase:
    """
    paid → canceled (재고 복원)
    """
    if purchase.status == Purchase.STATUS_CANCELED:
        return purchase
    release_stock(purchase.product_id, purchase.option_key or "", purchase.amount)
    purchase.status = Purchase.STATUS_CANCELED
    purchase.save(update_fields=["status"])
    return purchase


@transaction.atomic
def refund_purchase(purchase: Purchase) -> Purchase:
    """
    any → refunded (재고 복원)
    """
    if purchase.status == Purchase.STATUS_REFUNDED:
        return purchase
    release_stock(purchase.product_id, purchase.option_key or "", purchase.amount)
    purchase.status = Purchase.STATUS_REFUNDED
    purchase.save(update_fields=["status"])
    return purchase
