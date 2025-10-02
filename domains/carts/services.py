from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlencode

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from domains.catalog.models import Product
from domains.orders.utils import parse_option_key_safe

from .models import Cart, CartItem

User = get_user_model()


def make_option_key(options: Dict[str, Any] | None) -> str:
    """
    옵션 dict을 안정적으로 직렬화해 키를 생성.
    예: {"size":"L","color":"red"} -> "color=red&size=L"
    """
    options = options or {}
    flat = {
        str(k): (",".join(map(str, v)) if isinstance(v, (list, tuple)) else str(v))
        for k, v in options.items()
    }
    return urlencode(sorted(flat.items()))  # 키 정렬 고정


@transaction.atomic
def get_or_create_user_cart(user: Any) -> Cart:
    """유저의 카트를 잠금(select_for_update)으로 확보하거나 생성."""
    cart, _ = Cart.objects.select_for_update().get_or_create(user=user)
    # 만료 처리(선택): 만료됐으면 새로 생성
    if cart.expires_at and cart.expires_at < timezone.now():
        cart.delete()
        cart = Cart.objects.create(user=user)
    return cart


@transaction.atomic
def add_or_update_item(
    *,
    user: Any,
    product: Product,
    options: Dict[str, Any] | str | None,
    quantity: int = 1,
    unit_price: Decimal | None = None,
) -> Tuple[Cart, CartItem]:
    """
    같은 (product, option_key)가 있으면 수량만 증가, 없으면 새로 추가.
    options는 dict 또는 'k=v&k2=v2' 문자열 모두 허용.
    """
    if quantity <= 0:
        raise ValueError("quantity must be >= 1")

    # 문자열 → dict 안전 변환
    if isinstance(options, str):
        options = parse_option_key_safe(options) or {}
    elif options is None:
        options = {}

    if not isinstance(options, dict):
        raise ValueError("options must be dict or 'k=v&k2=v2' string")

    cart = get_or_create_user_cart(user)
    option_key = make_option_key(options)

    if unit_price is None:
        unit_price = Decimal(str(product.price))

    item, created = CartItem.objects.select_for_update().get_or_create(
        cart=cart,
        product=product,
        option_key=option_key,
        defaults={
            "options": options,
            "quantity": quantity,
            "unit_price": unit_price,
        },
    )
    if not created:
        # 합산 정책
        item.quantity += quantity
        item.unit_price = unit_price  # 최신 단가 스냅샷(원치 않으면 제거)
        item.save(update_fields=["quantity", "unit_price"])

    return cart, item


@transaction.atomic
def get_user_cart(user, create: bool = True) -> Cart | None:
    """
    로그인 유저의 장바구니를 반환. 없으면 create=True일 때 생성.
    익명 유저면 None.
    """
    if not user or getattr(user, "is_anonymous", False):
        return None
    if create:
        return get_or_create_user_cart(user)  # 통일된 함수 사용
    return Cart.objects.filter(user=user).first()


@transaction.atomic
def clear_cart(cart: Cart | None) -> None:
    """장바구니 아이템 전체 삭제(체크아웃 완료 후 호출)."""
    if cart:
        cart.items.all().delete()


__all__ = [
    "get_user_cart",
    "get_or_create_user_cart",
    "add_or_update_item",
    "make_option_key",
    "clear_cart",
]
