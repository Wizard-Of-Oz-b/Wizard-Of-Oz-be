# domains/orders/services.py
from __future__ import annotations

from typing import List
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.core.exceptions import ValidationError

from domains.carts.models import Cart  # 앱 경로 다르면 수정
from domains.catalog.services import reserve_stock, release_stock, OutOfStockError, StockRowMissing
from .models import Purchase


@transaction.atomic
def checkout_user_cart(user, *, clear_cart: bool = True) -> List[Purchase]:
    """
    유저의 장바구니를 주문으로 전환.
    - 모든 아이템에 대해 재고 확보가 성공해야만 주문 생성 (원자적)
    - 실패 시 전체 롤백
    """
    cart = get_object_or_404(Cart.objects.select_related("user"), user=user)
    items = (
        cart.items.select_related("product")
        .order_by("product_id", "option_key")  # 잠금 순서 고정 → 데드락 예방
    )

    if not items.exists():
        raise ValidationError("장바구니가 비어 있습니다.")

    # 1) 재고 확보
    try:
        for it in items:
            reserve_stock(it.product_id, it.option_key, it.quantity)
    except (OutOfStockError, StockRowMissing) as e:
        # 예외 발생 시 트랜잭션 롤백됨
        raise ValidationError(str(e))

    # 2) 구매 레코드 생성
    now = timezone.now()
    purchases: List[Purchase] = []
    for it in items:
        purchases.append(
            Purchase(
                user=user,
                product_id=it.product_id,
                amount=it.quantity,
                unit_price=it.unit_price,   # 스냅샷
                options=it.options,         # 스냅샷
                option_key=it.option_key,   # 복원용
                status=Purchase.STATUS_PAID,
                purchased_at=now,
            )
        )
    Purchase.objects.bulk_create(purchases)

    # 3) (선택) 카트 비우기
    if clear_cart:
        cart.items.all().delete()

    return purchases


@transaction.atomic
def cancel_purchase(purchase: Purchase) -> Purchase:
    if purchase.status == Purchase.STATUS_CANCELED:
        return purchase
    release_stock(purchase.product_id, purchase.option_key, purchase.amount)
    purchase.status = Purchase.STATUS_CANCELED
    purchase.save(update_fields=["status"])
    return purchase


@transaction.atomic
def refund_purchase(purchase: Purchase) -> Purchase:
    if purchase.status == Purchase.STATUS_REFUNDED:
        return purchase
    release_stock(purchase.product_id, purchase.option_key, purchase.amount)
    purchase.status = Purchase.STATUS_REFUNDED
    purchase.save(update_fields=["status"])
    return purchase
