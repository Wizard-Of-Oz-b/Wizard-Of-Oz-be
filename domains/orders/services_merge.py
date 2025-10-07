from __future__ import annotations

from decimal import Decimal
from typing import Any, List, Tuple, Dict

from django.contrib.auth import get_user_model
from django.db import transaction

from rest_framework.exceptions import ValidationError

from .models import OrderItem, Purchase

User = get_user_model()


@transaction.atomic
def merge_ready_orders(user: Any, order_ids: List[str]) -> Tuple[Purchase, Any]:
    """
    여러 개의 ready 상태 주문을 하나의 새로운 주문으로 통합
    """
    if not order_ids:
        raise ValidationError({"detail": "통합할 주문 ID가 필요합니다."})

    orders = Purchase.objects.select_for_update().filter(
        purchase_id__in=order_ids, user=user, status=Purchase.STATUS_READY
    )

    if orders.count() != len(order_ids):
        missing_count = len(order_ids) - orders.count()
        raise ValidationError(
            {"detail": f"일부 주문을 찾을 수 없거나 이미 처리되었습니다. (누락: {missing_count}개)"}
        )

    if orders.count() < 2:
        raise ValidationError({"detail": "최소 2개 이상의 주문이 필요합니다."})

    # ✅ guard 추가
    first_order = orders.first()
    if not first_order:
        raise ValidationError({"detail": "선택한 주문들을 찾을 수 없습니다."})

    merged_order = Purchase.objects.create(
        user=user,
        status=Purchase.STATUS_READY,
        items_total=Decimal("0"),
        grand_total=Decimal("0"),
        shipping_recipient=first_order.shipping_recipient,
        shipping_phone=first_order.shipping_phone,
        shipping_postcode=first_order.shipping_postcode,
        shipping_address1=first_order.shipping_address1,
        shipping_address2=first_order.shipping_address2,
        shipping_memo=first_order.shipping_memo,
    )

    total_amount = Decimal("0")
    all_items_to_update: list[OrderItem] = []

    for order in orders:
        items = OrderItem.objects.filter(order=order)
        for item in items:
            item.order = merged_order
            total_amount += item.unit_price * item.quantity
            all_items_to_update.append(item)

    if all_items_to_update:
        OrderItem.objects.bulk_update(all_items_to_update, ["order"])

    merged_order.items_total = total_amount
    merged_order.grand_total = total_amount
    merged_order.save(update_fields=["items_total", "grand_total"])

    orders.update(status=Purchase.STATUS_MERGED)

    from domains.payments.services import create_payment_stub

    payment = create_payment_stub(merged_order, amount=merged_order.grand_total)
    return merged_order, payment


def get_user_ready_orders_summary(user: Any) -> Dict[str, Any]:
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
    orders_data: list[dict[str, Any]] = []

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
def cancel_merged_order(merged_order: Purchase, user: Any) -> Dict[str, Any]:
    """
    통합 주문을 취소하고 원래 주문들을 복원
    """
    if merged_order.user != user:
        raise ValidationError({"detail": "권한이 없습니다."})

    if merged_order.status != Purchase.STATUS_READY:
        raise ValidationError({"detail": "취소할 수 없는 주문 상태입니다."})

    original_orders = Purchase.objects.filter(
        user=user,
        status=Purchase.STATUS_MERGED,
        purchased_at__lt=merged_order.purchased_at,
    ).order_by("purchased_at")

    if not original_orders.exists():
        merged_order.status = Purchase.STATUS_CANCELED
        merged_order.save(update_fields=["status"])
        return {"restored_orders": 0, "canceled_order": str(merged_order.purchase_id)}

    first_original_order = original_orders.first()
    if not first_original_order:
        raise ValidationError({"detail": "복원할 원래 주문을 찾을 수 없습니다."})

    OrderItem.objects.filter(order=merged_order).update(order=first_original_order)

    total_amount = sum(
        item.unit_price * item.quantity
        for item in OrderItem.objects.filter(order=first_original_order)
    )
    first_original_order.items_total = total_amount
    first_original_order.grand_total = total_amount
    first_original_order.status = Purchase.STATUS_READY
    first_original_order.save(update_fields=["items_total", "grand_total", "status"])

    original_orders.exclude(purchase_id=first_original_order.purchase_id).update(
        status=Purchase.STATUS_READY
    )

    merged_order.delete()

    return {
        "restored_orders": original_orders.count(),
        "main_order_id": str(first_original_order.purchase_id),
    }


@transaction.atomic
def delete_ready_orders(user: Any, order_ids: List[str]) -> Dict[str, Any]:
    """
    Ready 상태의 주문들을 삭제하고 재고를 복구
    """
    if not order_ids:
        raise ValidationError({"detail": "삭제할 주문 ID가 필요합니다."})

    orders = Purchase.objects.select_for_update().filter(
        purchase_id__in=order_ids, user=user, status=Purchase.STATUS_READY
    )

    if orders.count() != len(order_ids):
        missing_count = len(order_ids) - orders.count()
        raise ValidationError(
            {"detail": f"일부 주문을 찾을 수 없거나 이미 처리되었습니다. (누락: {missing_count}개)"}
        )

    restored_stock_count = 0
    for order in orders:
        order_items = OrderItem.objects.filter(order=order)
        for item in order_items:
            try:
                from domains.catalog.services import release_stock

                release_stock(
                    product_id=item.product_id,
                    option_key=item.option_key or "",
                    qty=item.quantity,
                )
                restored_stock_count += item.quantity
            except Exception as e:
                import logging

                logger = logging.getLogger(__name__)
                logger.warning(f"재고 복구 실패: {e}, OrderItem ID: {item.item_id}")

    deleted_items_count = 0
    for order in orders:
        items_count = OrderItem.objects.filter(order=order).count()
        OrderItem.objects.filter(order=order).delete()
        deleted_items_count += items_count

    deleted_orders_count = orders.count()
    orders.delete()

    return {
        "deleted_orders": deleted_orders_count,
        "deleted_items": deleted_items_count,
        "restored_stock": restored_stock_count,
        "message": f"{deleted_orders_count}개의 주문이 삭제되고 {restored_stock_count}개의 재고가 복구되었습니다.",
    }


def delete_single_ready_order(user: Any, order_id: str) -> Dict[str, Any]:
    """단일 Ready 상태 주문 삭제 (편의 함수)"""
    return delete_ready_orders(user, [order_id])
