from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from rest_framework.exceptions import ValidationError

from domains.carts.models import Cart, CartItem
from domains.carts.services import clear_cart as clear_cart_items  # 장바구니 비우기 헬퍼
from domains.catalog.services import (
    OutOfStockError,
    StockRowMissing,
    release_stock,
    reserve_stock,
)
from domains.payments.services import create_payment_stub

from .models import OrderItem, Purchase

User = get_user_model()


class EmptyCartError(ValidationError):
    """장바구니가 없거나 비어 있을 때 사용하는 호환 예외"""

    pass


# ─────────────────────────────────────────────────────────────────────────────
# 장바구니 → 다건 구매(기존 Purchase 구조 유지용)
# ─────────────────────────────────────────────────────────────────────────────
@transaction.atomic
def checkout_user_cart(user: Any, *, clear_cart: bool = True) -> List[Purchase]:
    """
    유저의 장바구니를 여러 건의 Purchase 레코드로 전환.
    - 모든 아이템 재고 확보 성공 시에만 생성(원자적)
    - 실패 시 전체 롤백
    - 성공 시 장바구니 비우기(옵션, 여기서 직접 삭제로 보증)
    """
    # 1) 카트 로드
    cart = (
        Cart.objects.select_related("user")
        .prefetch_related("items")
        .filter(user=user)
        .first()
    )
    if not cart:
        raise EmptyCartError({"cart": "장바구니가 없습니다."})
    if not cart.items.exists():
        raise EmptyCartError({"cart": "장바구니에 담긴 상품이 없습니다."})

    # 아이템 잠금 + materialize (삭제 전 고정)
    items = list(
        cart.items.select_related("product")
        .select_for_update()
        .order_by("product_id", "option_key")
    )

    # 2) 재고 확보
    try:
        for it in items:
            reserve_stock(it.product_id, it.option_key or "", it.quantity)
    except (OutOfStockError, StockRowMissing) as e:
        raise ValidationError({"stock": str(e)})

    # 3) 구매 레코드 생성 (스냅샷 저장)
    now = timezone.now()
    to_create: List[Purchase] = []
    for it in items:
        to_create.append(
            Purchase(
                user=user,
                product_id=it.product_id,
                amount=it.quantity,  # 수량 스냅샷
                unit_price=it.unit_price or it.product.price,  # 단가 스냅샷(빈 값 대비)
                options=it.options or {},  # 옵션 스냅샷(JSON)
                option_key=it.option_key or "",
                status=Purchase.STATUS_PAID,
                purchased_at=now,
            )
        )
    # DB에 반영
    Purchase.objects.bulk_create(to_create)

    # 4) 카트 비우기 (직접 삭제로 보증)
    if clear_cart:
        CartItem.objects.filter(cart_id=cart.id).delete()


    # 5) 생성된 구매 목록 재조회해서 반환 (PK 포함 보장)
    purchases = list(
        Purchase.objects.filter(user=user, purchased_at__gte=now).order_by(
            "purchased_at", "purchase_id"
        )
    )
    return purchases


# ─────────────────────────────────────────────────────────────────────────────
# 단일 주문헤더 + 결제 스텁 (새 체크아웃 엔드포인트용)
# ─────────────────────────────────────────────────────────────────────────────
@transaction.atomic
def checkout(user: Any) -> Tuple[Purchase, Any]:
    """
    단일 주문 헤더(Purchase)와 결제 스텁을 생성한다.
    - 카트가 비어있으면 EmptyCartError
    - 재고 확보 실패 시 ValidationError
    - 체크아웃 시점에 OrderItem 생성하여 스냅샷 보장
    """
    # 0) 카트 로드(+프리패치)
    cart: Optional[Cart] = (
        Cart.objects.select_related("user")
        .prefetch_related(
            "items",
            "items__product",
            "items__product__category",
        )
        .filter(user=user)
        .first()
    )
    if not cart:
        raise EmptyCartError({"cart": "장바구니가 없습니다."})
    if not cart.items.exists():
        raise EmptyCartError({"cart": "장바구니에 담긴 상품이 없습니다."})

    # 1) 헤더 생성 (ready)
    order = Purchase.objects.create(
        user=user,
        status=Purchase.STATUS_READY,
        # ↓ items_total/grand_total는 라인 생성 후 다시 업데이트
        items_total=0,
        grand_total=0,
    )

    # 2) 재고 차감 + 총액 계산 + OrderItem 생성
    items_qs = cart.items.select_related("product").order_by("product_id", "option_key")

    items_to_create = []
    line_total_sum = Decimal('0')

    for it in items_qs:
        from domains.catalog.services import reserve_stock
        from domains.orders.models import OrderItem

        # 재고 차감
        reserve_stock(it.product_id, it.option_key or "", it.quantity)

        # 총액 계산
        line_total_sum += it.unit_price * it.quantity

        # OrderItem 생성 준비
        items_to_create.append(
            OrderItem(
                order=order,
                product_id=it.product_id,
                stock_id=None,
                product_name=it.product.name,
                thumbnail_url=getattr(it.product, "thumbnail_url", "") or "",
                sku="",
                option_key=it.option_key or "",
                options=it.options or {},
                unit_price=it.unit_price,
                quantity=it.quantity,
                line_discount=0,
                line_tax=0,
                currency="KRW",
            )
        )

    # 3) OrderItem 생성
    OrderItem.objects.bulk_create(items_to_create)

    # 4) 헤더 합계 반영
    order.items_total = line_total_sum
    order.grand_total = line_total_sum  # 배송비/쿠폰 있으면 계산식 반영
    order.save(update_fields=["items_total", "grand_total"])


    # 5) 장바구니 비우기
    from domains.carts.services import clear_cart as clear_cart_items

    clear_cart_items(cart)

    # 6) 결제 스텁 생성
    from domains.payments.services import create_payment_stub

    payment = create_payment_stub(order, amount=order.grand_total)
    return order, payment


# ─────────────────────────────────────────────────────────────────────────────
# 취소/환불 (기존 구매 구조 유지)
# ─────────────────────────────────────────────────────────────────────────────
@transaction.atomic
def cancel_purchase(purchase: Purchase) -> Purchase:
    if purchase.status == Purchase.STATUS_CANCELED:
        return purchase
    release_stock(purchase.product_id, purchase.option_key or "", purchase.amount)
    purchase.status = Purchase.STATUS_CANCELED
    purchase.save(update_fields=["status"])
    return purchase


@transaction.atomic
def refund_purchase(purchase: Purchase) -> Purchase:
    if purchase.status == Purchase.STATUS_REFUNDED:
        return purchase
    release_stock(purchase.product_id, purchase.option_key or "", purchase.amount)
    purchase.status = Purchase.STATUS_REFUNDED
    purchase.save(update_fields=["status"])
    return purchase


# ─────────────────────────────────────────────────────────────────────────────
# 결제 승인 직후: 카트 -> OrderItem 생성(멱등)
# ─────────────────────────────────────────────────────────────────────────────
def validate_cart_stock(user: Any) -> None:
    """
    장바구니의 모든 아이템 재고를 사전 검증 (토스 결제 전)
    재고 부족 시 ValidationError 발생
    """
    from domains.carts.services import get_user_cart

    cart = get_user_cart(user, create=False)
    if not cart or not cart.items.exists():
        raise EmptyCartError({"cart": "장바구니가 비어 있습니다."})

    # 각 아이템의 재고 검증
    for ci in cart.items.select_related("product"):
        try:
            from domains.catalog.services import check_stock_availability

            check_stock_availability(ci.product_id, ci.option_key or "", ci.quantity)
        except (OutOfStockError, StockRowMissing) as e:
            raise ValidationError(
                {
                    "stock": f"재고 부족: {ci.product.name} (필요: {ci.quantity}, 옵션: {ci.option_key or '없음'}) - {str(e)}"
                }
            )


@transaction.atomic
def create_order_items_from_cart(purchase: Purchase) -> int:
    """
    결제 승인 직후: 유저의 장바구니를 읽어 OrderItem을 생성하고 재고 차감, 장바구니 비우기.
    이미 OrderItem이 있으면 아무 것도 하지 않음(멱등성).
    반환값: 생성된 라인 개수
    """
    # 이미 생성됐다면 멱등 처리
    if OrderItem.objects.filter(order=purchase).exists():
        return 0

    # 유저 카트 로드
    cart: Optional[Cart] = (
        Cart.objects.select_related("user")
        .prefetch_related("items__product")
        .filter(user=purchase.user)
        .first()
    )

    # 장바구니가 없으면 오류
    if not cart:
        raise EmptyCartError({"cart": "장바구니가 없습니다."})

    # 장바구니가 비어있으면 오류 (체크아웃 시점에 이미 검증되었지만 안전장치)
    if not cart.items.exists():
        raise EmptyCartError({"cart": "장바구니가 비어 있습니다."})

    items_to_create: list[OrderItem] = []

    # 재고 차감 + 라인 스냅샷 준비
    try:
        for ci in cart.items.select_related("product").order_by(
            "product_id", "option_key"
        ):
            reserve_stock(ci.product_id, ci.option_key or "", ci.quantity)

            items_to_create.append(
                OrderItem(
                    order=purchase,
                    product_id=ci.product_id,
                    stock_id=None,  # 옵션 재고 행을 별도 추적한다면 채워주세요
                    product_name=ci.product.name,  # 스냅샷
                    thumbnail_url=getattr(ci.product, "thumbnail_url", "") or "",
                    sku="",  # SKU 쓰면 매핑
                    option_key=ci.option_key or "",
                    options=ci.options or {},
                    unit_price=ci.unit_price,
                    quantity=ci.quantity,
                    line_discount=0,
                    line_tax=0,
                    currency="KRW",
                )
            )
    except (OutOfStockError, StockRowMissing) as e:
        raise ValidationError({"stock": str(e)})

    # OrderItem 생성 (실패 시 트랜잭션 롤백으로 재고도 복구됨)
    OrderItem.objects.bulk_create(items_to_create)

    # ✅ OrderItem 생성 성공 후에만 카트 비우기
    clear_cart_items(cart)
    return len(items_to_create)
