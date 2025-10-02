# domains/orders/services_merge.py
from __future__ import annotations

from decimal import Decimal
from typing import Any, List, Tuple

from django.contrib.auth import get_user_model
from django.db import transaction

from rest_framework.exceptions import ValidationError

from .models import OrderItem, Purchase

User = get_user_model()


@transaction.atomic
def merge_ready_orders(user: Any, order_ids: List[str]) -> Tuple[Purchase, Any]:
    """
    여러 개의 ready 상태 주문을 하나의 새로운 주문으로 통합

    Args:
        user: 사용자 객체
        order_ids: 통합할 주문 ID 목록 (purchase_id)

    Returns:
        Tuple[Purchase, Payment]: 새로 생성된 통합 주문과 결제 스텁

    Raises:
        ValidationError: 주문이 없거나 ready 상태가 아닌 경우
    """
    if not order_ids:
        raise ValidationError({"detail": "통합할 주문 ID가 필요합니다."})

    # 1) 대상 주문들 조회 및 검증
    orders = Purchase.objects.select_for_update().filter(
        purchase_id__in=order_ids, user=user, status=Purchase.STATUS_READY
    )

    if orders.count() != len(order_ids):
        missing_count = len(order_ids) - orders.count()
        raise ValidationError(
            {
                "detail": f"일부 주문을 찾을 수 없거나 이미 처리되었습니다. (누락: {missing_count}개)"
            }
        )

    if orders.count() < 2:
        raise ValidationError({"detail": "최소 2개 이상의 주문이 필요합니다."})

    # 2) 새로운 통합 주문 생성
    first_order = orders.first()
    merged_order = Purchase.objects.create(
        user=user,
        status=Purchase.STATUS_READY,
        items_total=Decimal("0"),
        grand_total=Decimal("0"),
        # 배송지 정보는 첫 번째 주문에서 복사 (있다면)
        shipping_recipient=first_order.shipping_recipient,
        shipping_phone=first_order.shipping_phone,
        shipping_postcode=first_order.shipping_postcode,
        shipping_address1=first_order.shipping_address1,
        shipping_address2=first_order.shipping_address2,
        shipping_memo=first_order.shipping_memo,
    )

    # 3) 기존 주문들의 OrderItem들을 새 통합 주문으로 이동
    total_amount = Decimal("0")
    all_items_to_update = []

    for order in orders:
        items = OrderItem.objects.filter(order=order)
        for item in items:
            item.order = merged_order  # 새 주문으로 재할당
            total_amount += item.unit_price * item.quantity
            all_items_to_update.append(item)

    # 4) OrderItem 일괄 업데이트
    if all_items_to_update:
        OrderItem.objects.bulk_update(all_items_to_update, ["order"])

    # 5) 통합 주문의 총액 업데이트
    merged_order.items_total = total_amount
    merged_order.grand_total = total_amount
    merged_order.save(update_fields=["items_total", "grand_total"])

    # 6) 기존 주문들 상태 변경 (merged)
    orders.update(status=Purchase.STATUS_MERGED)

    # 7) 새로운 통합 주문에 대한 Payment 스텁 생성
    from domains.payments.services import create_payment_stub

    payment = create_payment_stub(merged_order, amount=merged_order.grand_total)

    return merged_order, payment


def get_user_ready_orders_summary(user: Any) -> dict:
    """사용자의 미결제 주문 요약 정보"""

    ready_orders = (
        Purchase.objects.filter(user=user, status=Purchase.STATUS_READY)
        .prefetch_related("items")
        .order_by("-purchased_at")
    )

    if not ready_orders.exists():
        return {
            "total_orders": 0,
            "total_amount": "0",
            "orders": [],
            "can_merge": False,
        }

    total_amount = Decimal("0")
    orders_data = []

    for order in ready_orders:
        order_amount = order.grand_total or Decimal("0")
        total_amount += order_amount

        orders_data.append(
            {
                "order_id": str(order.purchase_id),
                "amount": str(order_amount),
                "items_count": order.items.count(),
                "created_at": order.purchased_at.isoformat(),
                "order_name": f"주문 {order.items.count()}개 상품",
            }
        )

    return {
        "total_orders": len(orders_data),
        "total_amount": str(total_amount),
        "orders": orders_data,
        "can_merge": len(orders_data) >= 2,
    }


@transaction.atomic
def cancel_merged_order(merged_order: Purchase, user: Any) -> dict:
    """
    통합 주문을 취소하고 원래 주문들을 복원

    Args:
        merged_order: 취소할 통합 주문
        user: 사용자 객체

    Returns:
        dict: 복원 결과
    """
    if merged_order.user != user:
        raise ValidationError({"detail": "권한이 없습니다."})

    if merged_order.status != Purchase.STATUS_READY:
        raise ValidationError({"detail": "취소할 수 없는 주문 상태입니다."})

    # 1) 관련된 merged 상태 주문들 찾기
    original_orders = Purchase.objects.filter(
        user=user,
        status=Purchase.STATUS_MERGED,
        purchased_at__lt=merged_order.purchased_at,  # 통합 주문보다 이전에 생성된 것들
    ).order_by("purchased_at")

    if not original_orders.exists():
        # 원래 주문들이 없으면 단순히 현재 주문만 취소
        merged_order.status = Purchase.STATUS_CANCELED
        merged_order.save(update_fields=["status"])
        return {"restored_orders": 0, "canceled_order": str(merged_order.purchase_id)}

    # 2) OrderItem들을 원래 주문들로 분배 (간단히 첫 번째 주문으로 모두 이동)
    first_original_order = original_orders.first()
    OrderItem.objects.filter(order=merged_order).update(order=first_original_order)

    # 3) 첫 번째 원래 주문의 금액 재계산
    total_amount = sum(
        item.unit_price * item.quantity
        for item in OrderItem.objects.filter(order=first_original_order)
    )
    first_original_order.items_total = total_amount
    first_original_order.grand_total = total_amount
    first_original_order.status = Purchase.STATUS_READY
    first_original_order.save(update_fields=["items_total", "grand_total", "status"])

    # 4) 나머지 원래 주문들도 ready 상태로 복원 (OrderItem은 없지만 기록 유지)
    original_orders.exclude(purchase_id=first_original_order.purchase_id).update(
        status=Purchase.STATUS_READY
    )

    # 5) 통합 주문 삭제
    merged_order.delete()

    return {
        "restored_orders": original_orders.count(),
        "main_order_id": str(first_original_order.purchase_id),
    }


@transaction.atomic
def delete_ready_orders(user: Any, order_ids: List[str]) -> dict:
    """
    Ready 상태의 주문들을 삭제하고 재고를 복구

    Args:
        user: 사용자 객체
        order_ids: 삭제할 주문 ID 목록 (purchase_id)

    Returns:
        dict: 삭제 결과

    Raises:
        ValidationError: 주문이 없거나 ready 상태가 아닌 경우
    """
    if not order_ids:
        raise ValidationError({"detail": "삭제할 주문 ID가 필요합니다."})

    # 1) 대상 주문들 조회 및 검증 (ready 상태만)
    orders = Purchase.objects.select_for_update().filter(
        purchase_id__in=order_ids, user=user, status=Purchase.STATUS_READY
    )

    if orders.count() != len(order_ids):
        missing_count = len(order_ids) - orders.count()
        raise ValidationError(
            {
                "detail": f"일부 주문을 찾을 수 없거나 이미 처리되었습니다. (누락: {missing_count}개)"
            }
        )

    # 2) 재고 복구
    restored_stock_count = 0
    for order in orders:
        order_items = OrderItem.objects.filter(order=order)
        for item in order_items:
            try:
                # 재고 복구 로직 (catalog.services에 있다고 가정)
                from domains.catalog.services import release_stock

                release_stock(
                    product_id=item.product_id,
                    option_key=item.option_key or "",
                    quantity=item.quantity,
                )
                restored_stock_count += item.quantity
            except Exception as e:
                # 재고 복구 실패해도 계속 진행 (로그만 남김)
                import logging

                logger = logging.getLogger(__name__)
                logger.warning(f"재고 복구 실패: {e}, OrderItem ID: {item.item_id}")

    # 3) OrderItem들 삭제
    deleted_items_count = 0
    for order in orders:
        items_count = OrderItem.objects.filter(order=order).count()
        OrderItem.objects.filter(order=order).delete()
        deleted_items_count += items_count

    # 4) Purchase 주문들 삭제
    deleted_orders_count = orders.count()
    orders.delete()

    return {
        "deleted_orders": deleted_orders_count,
        "deleted_items": deleted_items_count,
        "restored_stock": restored_stock_count,
        "message": f"{deleted_orders_count}개의 주문이 삭제되고 {restored_stock_count}개의 재고가 복구되었습니다.",
    }


def delete_single_ready_order(user: Any, order_id: str) -> dict:
    """
    단일 Ready 상태 주문 삭제 (편의 함수)

    Args:
        user: 사용자 객체
        order_id: 삭제할 주문 ID (purchase_id)

    Returns:
        dict: 삭제 결과
    """
    return delete_ready_orders(user, [order_id])
