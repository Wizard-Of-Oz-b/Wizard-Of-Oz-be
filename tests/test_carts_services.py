"""
domains/carts/services.py 테스트
"""

from datetime import timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.utils import timezone

import pytest

from domains.carts.models import Cart, CartItem
from domains.carts.services import (
    add_or_update_item,
    clear_cart,
    get_or_create_user_cart,
    get_user_cart,
    make_option_key,
)
from domains.catalog.models import Category, Product

User = get_user_model()


class TestMakeOptionKey:
    """make_option_key 함수 테스트"""

    def test_make_option_key_basic(self):
        """기본 옵션 딕셔너리 테스트"""
        options = {"size": "L", "color": "red"}
        result = make_option_key(options)
        # 키가 정렬되어야 함
        assert result == "color=red&size=L"

    def test_make_option_key_empty(self):
        """빈 옵션 테스트"""
        result = make_option_key({})
        assert result == ""

        result = make_option_key(None)
        assert result == ""

    def test_make_option_key_list_values(self):
        """리스트/튜플 값 처리 테스트"""
        options = {"sizes": ["S", "M", "L"], "colors": ("red", "blue")}
        result = make_option_key(options)
        assert "sizes=S%2CM%2CL" in result  # URL 인코딩됨
        assert "colors=red%2Cblue" in result

    def test_make_option_key_special_chars(self):
        """특수 문자 처리 테스트"""
        options = {"name": "test & value", "price": "100.50"}
        result = make_option_key(options)
        assert "name=test+%26+value" in result  # URL 인코딩됨
        assert "price=100.50" in result


@pytest.mark.django_db
class TestGetOrCreateUserCart:
    """get_or_create_user_cart 함수 테스트"""

    def test_create_new_cart(self, user_factory):
        """새 카트 생성 테스트"""
        user = user_factory()
        cart = get_or_create_user_cart(user)

        assert isinstance(cart, Cart)
        assert cart.user == user
        assert cart.id is not None

    def test_get_existing_cart(self, user_factory):
        """기존 카트 반환 테스트"""
        user = user_factory()
        existing_cart = Cart.objects.create(user=user)

        cart = get_or_create_user_cart(user)
        assert cart.id == existing_cart.id

    def test_expired_cart_recreation(self, user_factory):
        """만료된 카트 재생성 테스트"""
        user = user_factory()
        expired_time = timezone.now() - timedelta(days=1)

        # 만료된 카트 생성
        expired_cart = Cart.objects.create(user=user, expires_at=expired_time)
        old_id = expired_cart.id

        # 새 카트 생성
        cart = get_or_create_user_cart(user)
        assert cart.id != old_id
        assert cart.user == user


@pytest.mark.django_db
class TestAddOrUpdateItem:
    """add_or_update_item 함수 테스트"""

    def test_add_new_item(self, user_factory, product_factory):
        """새 아이템 추가 테스트"""
        user = user_factory()
        product = product_factory()
        options = {"size": "L", "color": "red"}

        cart, item = add_or_update_item(
            user=user, product=product, options=options, quantity=2
        )

        assert isinstance(cart, Cart)
        assert isinstance(item, CartItem)
        assert item.cart == cart
        assert item.product == product
        assert item.quantity == 2
        assert item.options == options
        # product.price는 문자열이므로 Decimal로 변환해서 비교
        assert item.unit_price == Decimal(str(product.price))

    def test_update_existing_item(self, user_factory, product_factory):
        """기존 아이템 수량 업데이트 테스트"""
        user = user_factory()
        product = product_factory()
        options = {"size": "M"}

        # 첫 번째 추가
        cart, item1 = add_or_update_item(
            user=user, product=product, options=options, quantity=1
        )

        # 두 번째 추가 (수량 증가)
        cart, item2 = add_or_update_item(
            user=user, product=product, options=options, quantity=2
        )

        assert item1.id == item2.id  # 같은 아이템
        assert item2.quantity == 3  # 1 + 2

    def test_add_item_with_string_options(self, user_factory, product_factory):
        """문자열 옵션으로 아이템 추가 테스트"""
        user = user_factory()
        product = product_factory()
        options_str = "size=L&color=blue"

        cart, item = add_or_update_item(
            user=user, product=product, options=options_str, quantity=1
        )

        assert item.options == {"size": "L", "color": "blue"}

    def test_add_item_with_custom_price(self, user_factory, product_factory):
        """커스텀 가격으로 아이템 추가 테스트"""
        user = user_factory()
        product = product_factory(price=Decimal("100.00"))
        custom_price = Decimal("90.00")

        cart, item = add_or_update_item(
            user=user, product=product, options={}, quantity=1, unit_price=custom_price
        )

        assert item.unit_price == custom_price

    def test_invalid_quantity(self, user_factory, product_factory):
        """잘못된 수량 테스트"""
        user = user_factory()
        product = product_factory()

        with pytest.raises(ValueError, match="quantity must be >= 1"):
            add_or_update_item(user=user, product=product, options={}, quantity=0)

        with pytest.raises(ValueError, match="quantity must be >= 1"):
            add_or_update_item(user=user, product=product, options={}, quantity=-1)

    def test_invalid_options_type(self, user_factory, product_factory):
        """잘못된 옵션 타입 테스트"""
        user = user_factory()
        product = product_factory()

        with pytest.raises(ValueError, match="options must be dict or"):
            add_or_update_item(user=user, product=product, options=123, quantity=1)


@pytest.mark.django_db
class TestGetUserCart:
    """get_user_cart 함수 테스트"""

    def test_get_existing_cart(self, user_factory):
        """기존 카트 반환 테스트"""
        user = user_factory()
        existing_cart = Cart.objects.create(user=user)

        cart = get_user_cart(user, create=True)
        assert cart.id == existing_cart.id

        cart = get_user_cart(user, create=False)
        assert cart.id == existing_cart.id

    def test_create_new_cart(self, user_factory):
        """새 카트 생성 테스트"""
        user = user_factory()

        cart = get_user_cart(user, create=True)
        assert isinstance(cart, Cart)
        assert cart.user == user

    def test_no_create_false(self, user_factory):
        """create=False일 때 None 반환 테스트"""
        user = user_factory()

        cart = get_user_cart(user, create=False)
        assert cart is None

    def test_anonymous_user(self):
        """익명 사용자 테스트"""
        from django.contrib.auth.models import AnonymousUser

        cart = get_user_cart(AnonymousUser(), create=True)
        assert cart is None

        cart = get_user_cart(AnonymousUser(), create=False)
        assert cart is None

    def test_none_user(self):
        """None 사용자 테스트"""
        cart = get_user_cart(None, create=True)
        assert cart is None


@pytest.mark.django_db
class TestClearCart:
    """clear_cart 함수 테스트"""

    def test_clear_cart_with_items(self, user_factory, product_factory):
        """아이템이 있는 카트 비우기 테스트"""
        user = user_factory()
        product = product_factory()
        cart = Cart.objects.create(user=user)

        # 아이템 추가 (가격을 Decimal로 변환)
        CartItem.objects.create(
            cart=cart,
            product=product,
            quantity=1,
            unit_price=Decimal(str(product.price)),
        )
        assert cart.items.count() == 1

        # 카트 비우기
        clear_cart(cart)
        assert cart.items.count() == 0

    def test_clear_empty_cart(self, user_factory):
        """빈 카트 비우기 테스트"""
        user = user_factory()
        cart = Cart.objects.create(user=user)

        clear_cart(cart)
        assert cart.items.count() == 0

    def test_clear_none_cart(self):
        """None 카트 테스트"""
        # None을 전달해도 오류가 발생하지 않아야 함
        clear_cart(None)


@pytest.mark.django_db
class TestAddOrUpdateItemEdgeCases:
    """add_or_update_item 함수의 추가 엣지 케이스 테스트"""

    def test_add_item_none_options_explicit(self, user_factory, product_factory):
        """명시적으로 None 옵션으로 아이템 추가 테스트 (60번째 줄 커버)"""
        user = user_factory()
        product = product_factory()

        cart, item = add_or_update_item(
            user=user, product=product, options=None, quantity=1  # 명시적으로 None 전달
        )

        assert item.options == {}
        assert item.option_key == ""
        assert item.quantity == 1
        assert item.unit_price == Decimal(str(product.price))
