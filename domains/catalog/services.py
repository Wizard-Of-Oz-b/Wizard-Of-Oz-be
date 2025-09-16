# domains/catalog/services.py
from __future__ import annotations
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from .models import ProductStock

class OutOfStockError(Exception):
    """요청 수량보다 재고가 부족할 때"""
    pass

class StockRowMissing(Exception):
    """해당 (product, option_key) 재고 행이 존재하지 않을 때"""
    pass

@transaction.atomic
def reserve_stock(product_id, option_key: str, qty: int):
    """
    결제 확정(또는 직전) 시 호출: 재고 차감.
    동시성 대비: 행 잠금 + F() 원자적 감소.
    """
    try:
        row = (ProductStock.objects
               .select_for_update()
               .get(product_id=product_id, option_key=option_key))
    except ProductStock.DoesNotExist:
        raise StockRowMissing(f"재고행 없음: product={product_id}, option={option_key}")

    if qty <= 0:
        return

    if row.stock_quantity < qty:
        raise OutOfStockError(f"재고 부족: 요청={qty}, 보유={row.stock_quantity}")

    ProductStock.objects.filter(pk=row.pk).update(
        stock_quantity=F("stock_quantity") - qty,
        updated_at=timezone.now(),
    )

@transaction.atomic
def release_stock(product_id, option_key: str, qty: int):
    """
    취소/환불 시 재고 복원.
    """
    try:
        row = (ProductStock.objects
               .select_for_update()
               .get(product_id=product_id, option_key=option_key))
    except ProductStock.DoesNotExist:
        raise StockRowMissing(f"재고행 없음: product={product_id}, option={option_key}")

    if qty <= 0:
        return

    ProductStock.objects.filter(pk=row.pk).update(
        stock_quantity=F("stock_quantity") + qty,
        updated_at=timezone.now(),
    )
