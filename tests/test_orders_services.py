"""
domains/orders/services.py 테스트
"""
import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.utils import timezone
from datetime import timedelta

from domains.orders.services import (
    EmptyCartError,
    checkout_user_cart,
    checkout,
    cancel_purchase,
    refund_purchase,
    create_order_items_from_cart,
)
from domains.orders.models import Purchase, OrderItem
from domains.carts.models import Cart, CartItem
from domains.catalog.models import Product, Category, ProductStock
from domains.accounts.models import User


@pytest.mark.django_db
class TestCheckoutUserCart:
    """checkout_user_cart 함수 테스트"""
    
    def test_checkout_user_cart_success(self, user_factory, product_factory):
        """장바구니 체크아웃 성공 테스트"""
        user = user_factory()
        product = product_factory()
        
        # 재고 생성
        ProductStock.objects.create(
            product=product,
            option_key="size=L",
            stock_quantity=10
        )
        
        # 장바구니 생성 및 아이템 추가
        cart = Cart.objects.create(user=user)
        CartItem.objects.create(
            cart=cart,
            product=product,
            option_key="size=L",
            options={"size": "L"},
            quantity=2,
            unit_price=Decimal("10000")
        )
        
        # 체크아웃 실행
        purchases = checkout_user_cart(user, clear_cart=True)
        
        # 검증
        assert len(purchases) == 1
        purchase = purchases[0]
        assert purchase.user == user
        assert purchase.product_id == product.id
        assert purchase.amount == 2
        assert purchase.unit_price == Decimal("10000")
        assert purchase.options == {"size": "L"}
        assert purchase.status == Purchase.STATUS_PAID
        
        # 장바구니가 비워졌는지 확인
        assert not CartItem.objects.filter(cart=cart).exists()
        
        # 재고가 차감되었는지 확인
        stock = ProductStock.objects.get(product=product, option_key="size=L")
        assert stock.stock_quantity == 8  # 10 - 2 = 8
    
    def test_checkout_user_cart_empty_cart(self, user_factory):
        """빈 장바구니 체크아웃 테스트"""
        user = user_factory()
        
        # 장바구니가 없는 경우
        with pytest.raises(EmptyCartError, match="장바구니가 없습니다"):
            checkout_user_cart(user)
        
        # 빈 장바구니인 경우
        Cart.objects.create(user=user)
        with pytest.raises(EmptyCartError, match="장바구니에 담긴 상품이 없습니다"):
            checkout_user_cart(user)
    
    def test_checkout_user_cart_insufficient_stock(self, user_factory, product_factory):
        """재고 부족 시 체크아웃 테스트"""
        user = user_factory()
        product = product_factory()
        
        # 재고 생성 (부족한 수량)
        ProductStock.objects.create(
            product=product,
            option_key="size=L",
            stock_quantity=1
        )
        
        # 장바구니 생성 및 아이템 추가
        cart = Cart.objects.create(user=user)
        CartItem.objects.create(
            cart=cart,
            product=product,
            option_key="size=L",
            quantity=5,  # 재고보다 많은 수량
            unit_price=Decimal("10000")
        )
        
        # 체크아웃 실패
        with pytest.raises(Exception, match="재고 부족"):
            checkout_user_cart(user)
        
        # 장바구니가 그대로 남아있는지 확인
        assert CartItem.objects.filter(cart=cart).exists()
    
    def test_checkout_user_cart_clear_cart_false(self, user_factory, product_factory):
        """장바구니 비우기 옵션 테스트"""
        user = user_factory()
        product = product_factory()
        
        # 재고 생성
        ProductStock.objects.create(
            product=product,
            option_key="size=L",
            stock_quantity=10
        )
        
        # 장바구니 생성 및 아이템 추가
        cart = Cart.objects.create(user=user)
        CartItem.objects.create(
            cart=cart,
            product=product,
            option_key="size=L",
            quantity=2,
            unit_price=Decimal("10000")
        )
        
        # 체크아웃 실행 (장바구니 비우기 안함)
        purchases = checkout_user_cart(user, clear_cart=False)
        
        # 장바구니가 그대로 남아있는지 확인
        assert CartItem.objects.filter(cart=cart).exists()


@pytest.mark.django_db
class TestCheckout:
    """checkout 함수 테스트"""
    
    def test_checkout_success(self, user_factory, product_factory):
        """단일 주문 체크아웃 성공 테스트"""
        user = user_factory()
        product = product_factory()
        
        # 재고 생성
        ProductStock.objects.create(
            product=product,
            option_key="size=L",
            stock_quantity=10
        )
        
        # 장바구니 생성 및 아이템 추가
        cart = Cart.objects.create(user=user)
        CartItem.objects.create(
            cart=cart,
            product=product,
            option_key="size=L",
            options={"size": "L"},
            quantity=2,
            unit_price=Decimal("10000")
        )
        
        # 체크아웃 실행
        with patch('domains.payments.services.create_payment_stub') as mock_create_payment:
            mock_payment = MagicMock()
            mock_create_payment.return_value = mock_payment
            
            order, payment = checkout(user)
        
        # 검증
        assert order.user == user
        assert order.status == Purchase.STATUS_READY
        assert order.items_total == Decimal("20000")  # 2 * 10000
        assert order.grand_total == Decimal("20000")
        
        # OrderItem 생성 확인
        order_items = OrderItem.objects.filter(order=order)
        assert order_items.count() == 1
        
        order_item = order_items.first()
        assert order_item.product_id == product.id
        assert order_item.quantity == 2
        assert order_item.unit_price == Decimal("10000")
        assert order_item.options == {"size": "L"}
        
        # 결제 스텁 생성 확인
        mock_create_payment.assert_called_once_with(order, amount=order.grand_total)
    
    def test_checkout_empty_cart(self, user_factory):
        """빈 장바구니 체크아웃 테스트"""
        user = user_factory()
        
        # 장바구니가 없는 경우
        with pytest.raises(EmptyCartError, match="장바구니가 없습니다"):
            checkout(user)
        
        # 빈 장바구니인 경우
        Cart.objects.create(user=user)
        with pytest.raises(EmptyCartError, match="장바구니에 담긴 상품이 없습니다"):
            checkout(user)


@pytest.mark.django_db
class TestCancelPurchase:
    """cancel_purchase 함수 테스트"""
    
    def test_cancel_purchase_success(self, user_factory, product_factory):
        """구매 취소 성공 테스트"""
        user = user_factory()
        product = product_factory()
        
        # 구매 생성
        purchase = Purchase.objects.create(
            user=user,
            product=product,
            amount=2,
            unit_price=Decimal("10000"),
            option_key="size=L",
            status=Purchase.STATUS_PAID
        )
        
        # 재고 생성
        ProductStock.objects.create(
            product=product,
            option_key="size=L",
            stock_quantity=5
        )
        
        # 취소 실행
        result = cancel_purchase(purchase)
        
        # 검증
        assert result == purchase
        assert purchase.status == Purchase.STATUS_CANCELED
        
        # 재고가 복구되었는지 확인
        stock = ProductStock.objects.get(product=product, option_key="size=L")
        assert stock.stock_quantity == 7  # 5 + 2 = 7
    
    def test_cancel_purchase_already_canceled(self, user_factory, product_factory):
        """이미 취소된 구매 테스트"""
        user = user_factory()
        product = product_factory()
        
        # 이미 취소된 구매 생성
        purchase = Purchase.objects.create(
            user=user,
            product=product,
            amount=2,
            unit_price=Decimal("10000"),
            status=Purchase.STATUS_CANCELED
        )
        
        # 취소 실행
        result = cancel_purchase(purchase)
        
        # 상태가 변경되지 않았는지 확인
        assert result == purchase
        assert purchase.status == Purchase.STATUS_CANCELED


@pytest.mark.django_db
class TestRefundPurchase:
    """refund_purchase 함수 테스트"""
    
    def test_refund_purchase_success(self, user_factory, product_factory):
        """구매 환불 성공 테스트"""
        user = user_factory()
        product = product_factory()
        
        # 구매 생성
        purchase = Purchase.objects.create(
            user=user,
            product=product,
            amount=3,
            unit_price=Decimal("15000"),
            option_key="size=M",
            status=Purchase.STATUS_PAID
        )
        
        # 재고 생성
        ProductStock.objects.create(
            product=product,
            option_key="size=M",
            stock_quantity=2
        )
        
        # 환불 실행
        result = refund_purchase(purchase)
        
        # 검증
        assert result == purchase
        assert purchase.status == Purchase.STATUS_REFUNDED
        
        # 재고가 복구되었는지 확인
        stock = ProductStock.objects.get(product=product, option_key="size=M")
        assert stock.stock_quantity == 5  # 2 + 3 = 5
    
    def test_refund_purchase_already_refunded(self, user_factory, product_factory):
        """이미 환불된 구매 테스트"""
        user = user_factory()
        product = product_factory()
        
        # 이미 환불된 구매 생성
        purchase = Purchase.objects.create(
            user=user,
            product=product,
            amount=2,
            unit_price=Decimal("10000"),
            status=Purchase.STATUS_REFUNDED
        )
        
        # 환불 실행
        result = refund_purchase(purchase)
        
        # 상태가 변경되지 않았는지 확인
        assert result == purchase
        assert purchase.status == Purchase.STATUS_REFUNDED


@pytest.mark.django_db
class TestCreateOrderItemsFromCart:
    """create_order_items_from_cart 함수 테스트"""
    
    def test_create_order_items_from_cart_success(self, user_factory, product_factory):
        """장바구니에서 주문 아이템 생성 성공 테스트"""
        user = user_factory()
        product = product_factory()
        
        # 구매 생성
        purchase = Purchase.objects.create(
            user=user,
            status=Purchase.STATUS_READY
        )
        
        # 재고 생성
        ProductStock.objects.create(
            product=product,
            option_key="size=L",
            stock_quantity=10
        )
        
        # 장바구니 생성 및 아이템 추가
        cart = Cart.objects.create(user=user)
        CartItem.objects.create(
            cart=cart,
            product=product,
            option_key="size=L",
            options={"size": "L"},
            quantity=2,
            unit_price=Decimal("10000")
        )
        
        # 주문 아이템 생성
        count = create_order_items_from_cart(purchase)
        
        # 검증
        assert count == 1
        
        # OrderItem 생성 확인
        order_items = OrderItem.objects.filter(order=purchase)
        assert order_items.count() == 1
        
        order_item = order_items.first()
        assert order_item.product_id == product.id
        assert order_item.quantity == 2
        assert order_item.unit_price == Decimal("10000")
        assert order_item.options == {"size": "L"}
        
        # 장바구니가 비워졌는지 확인
        assert not CartItem.objects.filter(cart=cart).exists()
        
        # 재고가 차감되었는지 확인
        stock = ProductStock.objects.get(product=product, option_key="size=L")
        assert stock.stock_quantity == 8  # 10 - 2 = 8
    
    def test_create_order_items_from_cart_idempotent(self, user_factory, product_factory):
        """멱등성 테스트 - 이미 OrderItem이 있는 경우"""
        user = user_factory()
        product = product_factory()
        
        # 구매 생성
        purchase = Purchase.objects.create(
            user=user,
            status=Purchase.STATUS_READY
        )
        
        # 이미 OrderItem 생성
        OrderItem.objects.create(
            order=purchase,
            product=product,
            quantity=1,
            unit_price=Decimal("10000")
        )
        
        # 장바구니 생성 및 아이템 추가
        cart = Cart.objects.create(user=user)
        CartItem.objects.create(
            cart=cart,
            product=product,
            option_key="size=L",
            quantity=2,
            unit_price=Decimal("10000")
        )
        
        # 주문 아이템 생성 (멱등성)
        count = create_order_items_from_cart(purchase)
        
        # 검증
        assert count == 0  # 새로 생성된 아이템 없음
        
        # OrderItem 개수가 그대로인지 확인
        assert OrderItem.objects.filter(order=purchase).count() == 1
    
    def test_create_order_items_from_cart_empty_cart(self, user_factory):
        """빈 장바구니 테스트"""
        user = user_factory()
        
        # 구매 생성
        purchase = Purchase.objects.create(
            user=user,
            status=Purchase.STATUS_READY
        )
        
        # 장바구니가 없는 경우 - 예외 발생 예상
        with pytest.raises(EmptyCartError):
            create_order_items_from_cart(purchase)
        
        # 빈 장바구니인 경우 - 예외 발생 예상
        Cart.objects.create(user=user)
        with pytest.raises(EmptyCartError):
            create_order_items_from_cart(purchase)
    
    def test_create_order_items_from_cart_insufficient_stock(self, user_factory, product_factory):
        """재고 부족 시 테스트"""
        user = user_factory()
        product = product_factory()
        
        # 구매 생성
        purchase = Purchase.objects.create(
            user=user,
            status=Purchase.STATUS_READY
        )
        
        # 재고 생성 (부족한 수량)
        ProductStock.objects.create(
            product=product,
            option_key="size=L",
            stock_quantity=1
        )
        
        # 장바구니 생성 및 아이템 추가
        cart = Cart.objects.create(user=user)
        CartItem.objects.create(
            cart=cart,
            product=product,
            option_key="size=L",
            quantity=5,  # 재고보다 많은 수량
            unit_price=Decimal("10000")
        )
        
        # 주문 아이템 생성 실패
        with pytest.raises(Exception, match="재고 부족"):
            create_order_items_from_cart(purchase)
        
        # OrderItem이 생성되지 않았는지 확인
        assert not OrderItem.objects.filter(order=purchase).exists()
        
        # 장바구니가 그대로 남아있는지 확인
        assert CartItem.objects.filter(cart=cart).exists()


@pytest.mark.django_db
class TestCheckoutUserCartEdgeCases:
    """checkout_user_cart 함수의 추가 엣지 케이스 테스트"""

    def test_checkout_user_cart_stock_row_missing(self, user_factory, product_factory):
        """재고 행이 없어서 체크아웃 실패 테스트 (139-141번째 줄 커버)"""
        user = user_factory()
        product = product_factory()

        # 재고 행을 생성하지 않음 (StockRowMissing 에러 발생)

        # 장바구니 생성 및 아이템 추가
        cart = Cart.objects.create(user=user)
        CartItem.objects.create(
            cart=cart,
            product=product,
            option_key="size=M",
            options={"size": "M"},
            quantity=1,
            unit_price=Decimal("10000")
        )

        with pytest.raises(Exception) as exc_info:
            checkout_user_cart(user, clear_cart=True)

        # StockRowMissing 에러가 ValidationError로 변환됨
        assert "stock" in str(exc_info.value)
        # 장바구니는 비워지지 않아야 함 (트랜잭션 롤백)
        assert CartItem.objects.filter(cart=cart).count() == 1
