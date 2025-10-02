"""
domains/payments/services.py 테스트
"""

from datetime import timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.utils import timezone

import pytest

from domains.accounts.models import User
from domains.carts.models import Cart, CartItem
from domains.catalog.models import Product, ProductStock
from domains.orders.models import OrderItem, Purchase
from domains.payments.models import Payment as PaymentModel
from domains.payments.models import PaymentEvent as PaymentEventModel
from domains.payments.services import (
    ORDER_STATUS_CANCELED,
    ORDER_STATUS_PAID,
    ORDER_STATUS_READY,
    PAYMENT_STATUS_CANCELED,
    PAYMENT_STATUS_IN_PROGRESS,
    PAYMENT_STATUS_PAID,
    PAYMENT_STATUS_READY,
    PAYMENT_STATUS_WAITING_FOR_DEPOSIT,
    Payment,
    PaymentEvent,
    _record_event,
    cancel_payment,
    confirm_payment,
    create_payment_stub,
)


@pytest.mark.django_db
class TestRecordEvent:
    """_record_event 함수 테스트"""

    def test_record_event_basic(self, user_factory, product_factory):
        """기본 이벤트 기록 테스트"""
        user = user_factory()
        product = product_factory()

        # 주문 생성
        order = Purchase.objects.create(
            user=user,
            product=product,
            amount=1,
            unit_price=Decimal("10000"),
            status=ORDER_STATUS_READY,
        )

        # 결제 생성
        payment = PaymentModel.objects.create(
            order=order,
            status=PAYMENT_STATUS_READY,
            amount_total=Decimal("10000"),
            order_number=str(order.purchase_id),
        )

        # 이벤트 기록
        event = _record_event(
            payment_obj=payment,
            source="api",
            event_type="test_event",
            provider_status="ready",
            payload={"test": "data"},
            dedupe_key="test_key",
        )

        # 검증
        assert event.payment == payment
        assert event.source == "api"
        assert event.event_type == "test_event"
        assert event.provider_status == "ready"
        assert event.payload == {"test": "data"}
        assert event.dedupe_key == "test_key"
        assert event.occurred_at is not None

    def test_record_event_minimal(self, user_factory, product_factory):
        """최소 파라미터로 이벤트 기록 테스트"""
        user = user_factory()
        product = product_factory()

        # 주문 생성
        order = Purchase.objects.create(
            user=user,
            product=product,
            amount=1,
            unit_price=Decimal("10000"),
            status=ORDER_STATUS_READY,
        )

        # 결제 생성
        payment = PaymentModel.objects.create(
            order=order,
            status=PAYMENT_STATUS_READY,
            amount_total=Decimal("10000"),
            order_number=str(order.purchase_id),
        )

        # 이벤트 기록 (최소 파라미터)
        event = _record_event(
            payment_obj=payment, source="api", event_type="minimal_event"
        )

        # 검증
        assert event.payment == payment
        assert event.source == "api"
        assert event.event_type == "minimal_event"
        assert event.provider_status is None
        assert event.payload == {}
        assert event.dedupe_key is None


@pytest.mark.django_db
class TestCreatePaymentStub:
    """create_payment_stub 함수 테스트"""

    def test_create_payment_stub_success(self, user_factory, product_factory):
        """결제 스텁 생성 성공 테스트"""
        user = user_factory()
        product = product_factory()

        # 주문 생성
        order = Purchase.objects.create(
            user=user,
            product=product,
            amount=1,
            unit_price=Decimal("10000"),
            status=ORDER_STATUS_READY,
            grand_total=Decimal("10000"),
        )

        # 결제 스텁 생성
        payment = create_payment_stub(order, amount=Decimal("10000"))

        # 검증
        assert payment.order == order
        assert payment.status == PAYMENT_STATUS_READY
        assert payment.amount_total == Decimal("10000")
        assert payment.order_number == str(order.purchase_id)
        assert payment.requested_at is not None

        # 이벤트 기록 확인
        events = PaymentEventModel.objects.filter(payment=payment)
        assert events.count() == 1
        event = events.first()
        assert event.event_type == "stub_created"
        assert event.source == "api"

    def test_create_payment_stub_idempotent(self, user_factory, product_factory):
        """결제 스텁 생성 멱등성 테스트"""
        user = user_factory()
        product = product_factory()

        # 주문 생성
        order = Purchase.objects.create(
            user=user,
            product=product,
            amount=1,
            unit_price=Decimal("10000"),
            status=ORDER_STATUS_READY,
            grand_total=Decimal("10000"),
        )

        # 첫 번째 생성
        payment1 = create_payment_stub(order, amount=Decimal("10000"))

        # 두 번째 생성 (멱등성)
        payment2 = create_payment_stub(order, amount=Decimal("10000"))

        # 같은 객체인지 확인
        assert payment1 == payment2
        assert payment1.payment_id == payment2.payment_id

        # 결제 객체가 하나만 생성되었는지 확인
        payments = PaymentModel.objects.filter(order=order, status=PAYMENT_STATUS_READY)
        assert payments.count() == 1

    def test_create_payment_stub_use_grand_total(self, user_factory, product_factory):
        """grand_total 사용 테스트"""
        user = user_factory()
        product = product_factory()

        # 주문 생성
        order = Purchase.objects.create(
            user=user,
            product=product,
            amount=1,
            unit_price=Decimal("10000"),
            status=ORDER_STATUS_READY,
            grand_total=Decimal("15000"),
        )

        # amount 없이 결제 스텁 생성
        payment = create_payment_stub(order)

        # grand_total이 사용되었는지 확인
        assert payment.amount_total == Decimal("15000")


@pytest.mark.django_db
class TestConfirmPayment:
    """confirm_payment 함수 테스트"""

    def test_confirm_payment_success(self, user_factory, product_factory):
        """결제 승인 성공 테스트"""
        user = user_factory()
        product = product_factory()

        # 주문 생성
        order = Purchase.objects.create(
            user=user,
            product=product,
            amount=1,
            unit_price=Decimal("10000"),
            status=ORDER_STATUS_READY,
            grand_total=Decimal("10000"),
        )

        # 결제 생성
        payment = PaymentModel.objects.create(
            order=order,
            status=PAYMENT_STATUS_READY,
            amount_total=Decimal("10000"),
            order_number=str(order.purchase_id),
        )

        # 결제 승인
        with (
            patch("domains.carts.services.get_user_cart") as mock_get_cart,
            patch("domains.carts.services.clear_cart") as mock_clear_cart,
        ):

            mock_cart = MagicMock()
            mock_get_cart.return_value = mock_cart

            result = confirm_payment(
                payment,
                provider_payment_key="pk_123",
                provider_payload={"transactionKey": "tx_456"},
            )

        # 검증
        assert result == payment
        assert payment.status == PAYMENT_STATUS_PAID
        assert payment.provider_payment_key == "pk_123"
        assert payment.approved_at is not None
        assert payment.updated_at is not None

        # 주문 상태 변경 확인
        order.refresh_from_db()
        assert order.status == ORDER_STATUS_PAID

        # 이벤트 기록 확인
        events = PaymentEventModel.objects.filter(
            payment=payment, event_type="approval"
        )
        assert events.count() == 1
        event = events.first()
        assert event.payload == {"transactionKey": "tx_456"}
        assert event.dedupe_key == "tx_456"

        # 카트 비우기 호출 확인
        mock_get_cart.assert_called_once_with(order.user, create=False)
        mock_clear_cart.assert_called_once_with(mock_cart)

    def test_confirm_payment_already_paid(self, user_factory, product_factory):
        """이미 승인된 결제 테스트"""
        user = user_factory()
        product = product_factory()

        # 주문 생성
        order = Purchase.objects.create(
            user=user,
            product=product,
            amount=1,
            unit_price=Decimal("10000"),
            status=ORDER_STATUS_PAID,
            grand_total=Decimal("10000"),
        )

        # 이미 승인된 결제 생성
        payment = PaymentModel.objects.create(
            order=order,
            status=PAYMENT_STATUS_PAID,
            amount_total=Decimal("10000"),
            order_number=str(order.purchase_id),
            approved_at=timezone.now(),
        )

        # 결제 승인 (이미 승인됨)
        result = confirm_payment(payment, provider_payment_key="pk_123")

        # 상태가 변경되지 않았는지 확인
        assert result == payment
        assert payment.status == PAYMENT_STATUS_PAID

    def test_confirm_payment_invalid_status(self, user_factory, product_factory):
        """잘못된 상태에서 승인 시도 테스트"""
        user = user_factory()
        product = product_factory()

        # 주문 생성
        order = Purchase.objects.create(
            user=user,
            product=product,
            amount=1,
            unit_price=Decimal("10000"),
            status=ORDER_STATUS_READY,
            grand_total=Decimal("10000"),
        )

        # 취소된 결제 생성
        payment = PaymentModel.objects.create(
            order=order,
            status=PAYMENT_STATUS_CANCELED,
            amount_total=Decimal("10000"),
            order_number=str(order.purchase_id),
        )

        # 결제 승인 실패
        with pytest.raises(Exception, match="invalid state to confirm"):
            confirm_payment(payment, provider_payment_key="pk_123")


@pytest.mark.django_db
class TestCancelPayment:
    """cancel_payment 함수 테스트"""

    def test_cancel_payment_success(self, user_factory, product_factory):
        """결제 취소 성공 테스트"""
        user = user_factory()
        product = product_factory()

        # 재고 생성
        ProductStock.objects.create(
            product=product, option_key="size=L", stock_quantity=5
        )

        # 주문 생성
        order = Purchase.objects.create(
            user=user,
            product=product,
            amount=2,
            unit_price=Decimal("10000"),
            status=ORDER_STATUS_READY,
            grand_total=Decimal("20000"),
        )

        # OrderItem 생성
        OrderItem.objects.create(
            order=order,
            product=product,
            product_name=product.name,
            option_key="size=L",
            quantity=2,
            unit_price=Decimal("10000"),
        )

        # 결제 생성
        payment = PaymentModel.objects.create(
            order=order,
            status=PAYMENT_STATUS_READY,
            amount_total=Decimal("20000"),
            order_number=str(order.purchase_id),
        )

        # 결제 취소
        result = cancel_payment(
            payment,
            reason="사용자 요청",
            provider_payload={"cancelReason": "user_request"},
        )

        # 검증
        assert result == payment
        assert payment.status == PAYMENT_STATUS_CANCELED
        assert payment.canceled_at is not None
        assert payment.updated_at is not None

        # 주문 상태 변경 확인
        order.refresh_from_db()
        assert order.status == ORDER_STATUS_CANCELED

        # 재고 복구 확인
        stock = ProductStock.objects.get(product=product, option_key="size=L")
        assert stock.stock_quantity == 7  # 5 + 2 = 7

        # 이벤트 기록 확인
        events = PaymentEventModel.objects.filter(payment=payment, event_type="cancel")
        assert events.count() == 1
        event = events.first()
        assert event.payload["reason"] == "사용자 요청"
        assert event.payload["provider"] == {"cancelReason": "user_request"}

    def test_cancel_payment_already_canceled(self, user_factory, product_factory):
        """이미 취소된 결제 테스트"""
        user = user_factory()
        product = product_factory()

        # 주문 생성
        order = Purchase.objects.create(
            user=user,
            product=product,
            amount=1,
            unit_price=Decimal("10000"),
            status=ORDER_STATUS_CANCELED,
            grand_total=Decimal("10000"),
        )

        # 이미 취소된 결제 생성
        payment = PaymentModel.objects.create(
            order=order,
            status=PAYMENT_STATUS_CANCELED,
            amount_total=Decimal("10000"),
            order_number=str(order.purchase_id),
            canceled_at=timezone.now(),
        )

        # 결제 취소 (이미 취소됨)
        result = cancel_payment(payment, reason="test")

        # 상태가 변경되지 않았는지 확인
        assert result == payment
        assert payment.status == PAYMENT_STATUS_CANCELED

    def test_cancel_payment_paid_order(self, user_factory, product_factory):
        """이미 결제된 주문 취소 테스트"""
        user = user_factory()
        product = product_factory()

        # 주문 생성 (이미 결제됨)
        order = Purchase.objects.create(
            user=user,
            product=product,
            amount=1,
            unit_price=Decimal("10000"),
            status=ORDER_STATUS_PAID,
            grand_total=Decimal("10000"),
        )

        # 결제 생성
        payment = PaymentModel.objects.create(
            order=order,
            status=PAYMENT_STATUS_READY,
            amount_total=Decimal("10000"),
            order_number=str(order.purchase_id),
        )

        # 결제 취소
        result = cancel_payment(payment, reason="test")

        # 결제는 취소되지만 주문 상태는 변경되지 않음
        assert result == payment
        assert payment.status == PAYMENT_STATUS_CANCELED

        # 주문 상태는 그대로
        order.refresh_from_db()
        assert order.status == ORDER_STATUS_PAID


@pytest.mark.django_db
class TestPaymentIntegration:
    """결제 관련 통합 테스트"""

    def test_payment_flow_complete(self, user_factory, product_factory):
        """완전한 결제 플로우 테스트"""
        user = user_factory()
        product = product_factory()

        # 주문 생성 (이미 결제 완료된 상태로 가정)
        order = Purchase.objects.create(
            user=user,
            product=product,
            amount=2,
            unit_price=Decimal("10000"),
            status=ORDER_STATUS_READY,
            grand_total=Decimal("20000"),
        )

        # OrderItem 생성 (이미 재고 차감 완료된 상태)
        OrderItem.objects.create(
            order=order,
            product=product,
            product_name=product.name,
            option_key="size=L",
            quantity=2,
            unit_price=Decimal("10000"),
        )

        # 1. 결제 스텁 생성
        payment = create_payment_stub(order)
        assert payment.status == PAYMENT_STATUS_READY

        # 2. 결제 승인
        with (
            patch("domains.carts.services.get_user_cart") as mock_get_cart,
            patch("domains.carts.services.clear_cart") as mock_clear_cart,
        ):

            mock_cart = MagicMock()
            mock_get_cart.return_value = mock_cart

            confirmed_payment = confirm_payment(
                payment,
                provider_payment_key="pk_123",
                provider_payload={"transactionKey": "tx_456"},
            )

        # 3. 검증
        assert confirmed_payment.status == PAYMENT_STATUS_PAID
        order.refresh_from_db()
        assert order.status == ORDER_STATUS_PAID

        # 이벤트 기록 확인
        events = PaymentEventModel.objects.filter(payment=payment)
        assert events.count() == 2  # stub_created + approval

    def test_payment_cancel_flow(self, user_factory, product_factory):
        """결제 취소 플로우 테스트"""
        user = user_factory()
        product = product_factory()

        # 재고 생성
        ProductStock.objects.create(
            product=product, option_key="size=L", stock_quantity=5
        )

        # 주문 생성
        order = Purchase.objects.create(
            user=user,
            product=product,
            amount=3,
            unit_price=Decimal("10000"),
            status=ORDER_STATUS_READY,
            grand_total=Decimal("30000"),
        )

        # OrderItem 생성
        OrderItem.objects.create(
            order=order,
            product=product,
            product_name=product.name,
            option_key="size=L",
            quantity=3,
            unit_price=Decimal("10000"),
        )

        # 1. 결제 스텁 생성
        payment = create_payment_stub(order)
        assert payment.status == PAYMENT_STATUS_READY

        # 2. 결제 취소
        canceled_payment = cancel_payment(
            payment,
            reason="사용자 취소",
            provider_payload={"cancelReason": "user_cancel"},
        )

        # 3. 검증
        assert canceled_payment.status == PAYMENT_STATUS_CANCELED
        order.refresh_from_db()
        assert order.status == ORDER_STATUS_CANCELED

        # 재고 복구 확인
        stock = ProductStock.objects.get(product=product, option_key="size=L")
        assert stock.stock_quantity == 8  # 5 + 3 = 8

        # 이벤트 기록 확인
        events = PaymentEventModel.objects.filter(payment=payment)
        assert events.count() == 2  # stub_created + cancel
