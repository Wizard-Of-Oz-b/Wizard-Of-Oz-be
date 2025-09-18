from __future__ import annotations

from decimal import Decimal
from typing import Dict, Tuple
from urllib.parse import urlencode

from django.db import transaction
from django.utils import timezone
from django.conf import settings

from .models import Cart, CartItem
from domains.catalog.models import Product


def make_option_key(options: Dict) -> str:
    """
    옵션 dict을 안정적으로 직렬화해 해시 키를 만든다.
    예: {"size":"L","color":"red"} -> "color=red&size=L"
    """
    options = options or {}
    # 값이 리스트/딕트인 경우도 문자열화(필요에 따라 강화 가능)
    flat = {str(k): (",".join(map(str, v)) if isinstance(v, (list, tuple)) else str(v))
            for k, v in options.items()}
    return urlencode(sorted(flat.items()))  # 키 정렬


@transaction.atomic
def get_or_create_user_cart(user) -> Cart:
    cart, _ = Cart.objects.select_for_update().get_or_create(user=user)
    # 만료되었으면 재생성 (선택)
    if cart.expires_at and cart.expires_at < timezone.now():
        cart.delete()
        cart = Cart.objects.create(user=user)
    return cart


@transaction.atomic
def add_or_update_item(
    *,
    user,
    product: Product,
    options: Dict,
    quantity: int = 1,
    unit_price: Decimal | None = None,
) -> Tuple[Cart, CartItem]:
    """
    같은 (product, option_key)가 있으면 수량만 증가, 없으면 새로 추가.
    unit_price는 신뢰 가능한 서버 측에서 결정(보통 product.price 스냅샷).
    """
    if quantity <= 0:
        raise ValueError("quantity must be >= 1")

    cart = get_or_create_user_cart(user)
    option_key = make_option_key(options)

    if unit_price is None:
        unit_price = product.price

    item, created = CartItem.objects.select_for_update().get_or_create(
        cart=cart,
        product=product,
        option_key=option_key,
        defaults={
            "options": options or {},
            "quantity": quantity,
            "unit_price": unit_price,
        },
    )
    if not created:
        # 합산 정책(필요하면 대입 정책으로 변경)
        item.quantity += quantity
        item.unit_price = unit_price  # 최신 스냅샷으로 갱신 (원하지 않으면 제거)
        item.save(update_fields=["quantity", "unit_price"])
    return cart, item
