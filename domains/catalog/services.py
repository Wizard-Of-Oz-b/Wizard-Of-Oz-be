from __future__ import annotations

from typing import Any, Dict, Iterable, Tuple
from urllib.parse import parse_qsl, urlencode

from django.db import transaction
from django.db.models import F

from .models import ProductStock


class OutOfStockError(Exception):
    """요청 수량보다 재고가 부족할 때"""

    pass


class StockRowMissing(Exception):
    """해당 (product, option_key) 재고 행이 존재하지 않을 때"""

    pass


# -----------------------------
# option_key 정규화 유틸
# -----------------------------
def normalize_option_key(key: Any) -> str:
    """
    옵션 키를 항상 동일한 문자열로 정규화한다.
    - dict: 키 정렬 + 값이 리스트/튜플이면 콤마-조인
    - str : 쿼리스트링 파싱 → (key, value) 정렬 → 다시 인코딩
    - None/빈값: 빈 문자열
    """
    if not key:
        return ""

    # dict 형태로 받은 경우
    if isinstance(key, dict):
        flat: Dict[str, str] = {}
        for k, v in key.items():
            if isinstance(v, (list, tuple)):
                flat[str(k)] = ",".join(map(str, v))
            else:
                flat[str(k)] = "" if v is None else str(v)
        # 키 정렬 후 쿼리스트링으로
        return urlencode(sorted(flat.items()))

    # 문자열 형태로 받은 경우
    if isinstance(key, str):
        # keep_blank_values=True 로 공백 값도 유지
        pairs: Iterable[Tuple[str, str]] = parse_qsl(key, keep_blank_values=True)
        if not pairs:
            return ""
        # (key, value) 정렬 후 재인코딩
        return urlencode(sorted((str(k), str(v)) for k, v in pairs))

    # 기타 타입은 문자열화
    return str(key)


# -----------------------------
# 재고 조작 함수
# -----------------------------
@transaction.atomic
def reserve_stock(product_id, option_key: str | dict | None, qty: int):
    """
    재고 차감(예약). 재고가 부족하면 OutOfStockError.
    행이 없으면 0으로 생성 후 부족 에러를 발생시키므로
    잘못된 option_key라도 '없음'이 명확히 드러남.
    """
    if qty <= 0:
        return  # 음수/0은 무시 (원한다면 ValueError로 바꿔도 됨)

    key = normalize_option_key(option_key)

    row, _ = ProductStock.objects.select_for_update().get_or_create(
        product_id=product_id,
        option_key=key,
        defaults={"stock_quantity": 0},
    )

    if row.stock_quantity < qty:
        raise OutOfStockError(
            f"재고 부족: product={product_id}, option={key}, need={qty}, have={row.stock_quantity}"
        )

    row.stock_quantity = F("stock_quantity") - qty
    row.save(update_fields=["stock_quantity"])


@transaction.atomic
def release_stock(product_id, option_key: str | dict | None, qty: int):
    """
    재고 복구. 행이 없으면 0에서 시작해 더한다.
    """
    if qty <= 0:
        return

    key = normalize_option_key(option_key)

    row, _ = ProductStock.objects.select_for_update().get_or_create(
        product_id=product_id,
        option_key=key,
        defaults={"stock_quantity": 0},
    )
    row.stock_quantity = F("stock_quantity") + qty
    row.save(update_fields=["stock_quantity"])


# 조회 헬퍼 — 디버깅/점검용
def get_stock_quantity(product_id, option_key: str | dict | None) -> int:
    key = normalize_option_key(option_key)
    try:
        return int(
            ProductStock.objects.get(
                product_id=product_id, option_key=key
            ).stock_quantity
        )
    except ProductStock.DoesNotExist:
        return 0


def check_stock_availability(
    product_id, option_key: str | dict | None, required_quantity: int
) -> None:
    """
    재고 가용성 검증 (토스 결제 전 사전 검증용)
    재고 부족 시 OutOfStockError 또는 StockRowMissing 발생
    """
    key = normalize_option_key(option_key)

    try:
        stock_row = ProductStock.objects.get(product_id=product_id, option_key=key)
        available_quantity = int(stock_row.stock_quantity)

        if available_quantity < required_quantity:
            raise OutOfStockError(
                f"재고 부족: 상품 {product_id}, 옵션 '{key}', "
                f"요청 수량 {required_quantity}, 가용 수량 {available_quantity}"
            )
    except ProductStock.DoesNotExist:
        raise StockRowMissing(f"재고 정보 없음: 상품 {product_id}, 옵션 '{key}'")
