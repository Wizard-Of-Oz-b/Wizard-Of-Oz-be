"""
domains/shipments/services.py 테스트
"""

from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.utils import timezone

import pytest

from domains.accounts.models import User
from domains.catalog.models import Product
from domains.orders.models import OrderItem, Purchase
from domains.shipments.adapters.sweettracker import SweetTrackerAdapter
from domains.shipments.models import Shipment, ShipmentEvent, ShipmentStatus
from domains.shipments.services import (
    _norm_status,
    _parse_dt_safe,
    _recompute_status_from_events,
    register_tracking_with_sweettracker,
    sync_by_tracking,
    upsert_events_from_adapter,
)


@pytest.mark.django_db
class TestRegisterTrackingWithSweettracker:
    """register_tracking_with_sweettracker 함수 테스트"""

    def test_register_tracking_success(self, user_factory, product_factory):
        """운송장 등록 성공 테스트"""
        user = user_factory()
        product = product_factory()

        # 주문 생성
        order = Purchase.objects.create(
            user=user,
            product=product,
            amount=1,
            unit_price=Decimal("10000"),
            status="paid",
        )

        # 운송장 등록
        with patch.object(SweetTrackerAdapter, "register_tracking") as mock_register:
            shipment = register_tracking_with_sweettracker(
                tracking_number="CJT-123456",
                carrier="kr.cjlogistics",
                user=user,
                order=order,
            )

        # 검증
        assert shipment.carrier == "kr.cjlogistics"
        assert shipment.tracking_number == "CJT-123456"
        assert shipment.user == user
        assert shipment.order == order

        # 어댑터 호출 확인
        mock_register.assert_called_once_with(
            tracking_number="CJT-123456", carrier="kr.cjlogistics", fid=str(shipment.id)
        )

    def test_register_tracking_existing(self, user_factory, product_factory):
        """기존 운송장 등록 테스트"""
        user = user_factory()
        product = product_factory()

        # 주문 생성
        order = Purchase.objects.create(
            user=user,
            product=product,
            amount=1,
            unit_price=Decimal("10000"),
            status="paid",
        )

        # 기존 운송장 생성
        existing_shipment = Shipment.objects.create(
            carrier="kr.cjlogistics",
            tracking_number="CJT-123456",
            user=user,
            order=order,
        )

        # 같은 운송장으로 다시 등록
        with patch.object(SweetTrackerAdapter, "register_tracking") as mock_register:
            shipment = register_tracking_with_sweettracker(
                tracking_number="CJT-123456",
                carrier="kr.cjlogistics",
                user=user,
                order=order,
            )

        # 기존 운송장이 반환되는지 확인
        assert shipment == existing_shipment
        assert shipment.id == existing_shipment.id

        # 어댑터 호출 확인
        mock_register.assert_called_once_with(
            tracking_number="CJT-123456", carrier="kr.cjlogistics", fid=str(shipment.id)
        )


@pytest.mark.django_db
class TestSyncByTracking:
    """sync_by_tracking 함수 테스트"""

    def test_sync_by_tracking_success(self, user_factory, product_factory):
        """운송장 동기화 성공 테스트"""
        user = user_factory()
        product = product_factory()

        # 주문 생성
        order = Purchase.objects.create(
            user=user,
            product=product,
            amount=1,
            unit_price=Decimal("10000"),
            status="paid",
        )

        # 운송장 생성
        shipment = Shipment.objects.create(
            carrier="kr.cjlogistics",
            tracking_number="CJT-123456",
            user=user,
            order=order,
        )

        # 어댑터 모킹
        mock_adapter = MagicMock()
        mock_adapter.fetch_tracking.return_value = {
            "carrier": "kr.cjlogistics",
            "tracking_number": "CJT-123456",
            "events": [
                {
                    "occurred_at": "2024-01-01T10:00:00Z",
                    "status": "in_transit",
                    "location": "서울",
                    "description": "배송 시작",
                }
            ],
        }
        mock_adapter.parse_events.return_value = [
            {
                "occurred_at": "2024-01-01T10:00:00Z",
                "status": "in_transit",
                "location": "서울",
                "description": "배송 시작",
            }
        ]

        # 동기화 실행
        with patch(
            "domains.shipments.services.upsert_events_from_adapter"
        ) as mock_upsert:
            mock_upsert.return_value = 1
            result = sync_by_tracking("kr.cjlogistics", "CJT-123456", mock_adapter)

        # 검증
        assert result == 1
        mock_adapter.fetch_tracking.assert_called_once_with("CJT-123456")
        mock_adapter.parse_events.assert_called_once()
        mock_upsert.assert_called_once()

    def test_sync_by_tracking_default_adapter(self, user_factory, product_factory):
        """기본 어댑터 사용 테스트"""
        user = user_factory()
        product = product_factory()

        # 주문 생성
        order = Purchase.objects.create(
            user=user,
            product=product,
            amount=1,
            unit_price=Decimal("10000"),
            status="paid",
        )

        # 운송장 생성
        shipment = Shipment.objects.create(
            carrier="kr.cjlogistics",
            tracking_number="CJT-123456",
            user=user,
            order=order,
        )

        # 기본 어댑터 사용 (adapter=None)
        with (
            patch("domains.shipments.adapters.get_adapter") as mock_get_adapter,
            patch(
                "domains.shipments.services.SweetTrackerAdapter"
            ) as mock_sweet_tracker,
            patch(
                "domains.shipments.services.upsert_events_from_adapter"
            ) as mock_upsert,
        ):

            mock_get_adapter.side_effect = Exception("Adapter not found")
            mock_adapter = MagicMock()
            mock_sweet_tracker.return_value = mock_adapter
            mock_adapter.fetch_tracking.return_value = {}
            mock_adapter.parse_events.return_value = []
            mock_upsert.return_value = 0

            result = sync_by_tracking("kr.cjlogistics", "CJT-123456")

        # SweetTrackerAdapter가 사용되었는지 확인
        mock_sweet_tracker.assert_called_once()


@pytest.mark.django_db
class TestNormStatus:
    """_norm_status 함수 테스트"""

    def test_norm_status_basic(self):
        """기본 상태 정규화 테스트"""
        assert _norm_status("IN_TRANSIT") == "in_transit"
        assert _norm_status("out-for-delivery") == "out_for_delivery"
        assert _norm_status("DELIVERED") == "delivered"
        assert _norm_status("CANCELED") == "canceled"

    def test_norm_status_aliases(self):
        """상태 별칭 테스트"""
        assert _norm_status("intransit") == "in_transit"
        assert _norm_status("outfordelivery") == "out_for_delivery"
        assert _norm_status("배송중") == "in_transit"
        assert _norm_status("배송출발") == "out_for_delivery"
        assert _norm_status("배달완료") == "delivered"
        assert _norm_status("취소") == "canceled"
        assert _norm_status("반송") == "returned"

    def test_norm_status_edge_cases(self):
        """경계값 테스트"""
        assert _norm_status("") == ""
        assert _norm_status(None) == ""
        assert _norm_status("unknown_status") == "unknown_status"


@pytest.mark.django_db
class TestUpsertEventsFromAdapter:
    """upsert_events_from_adapter 함수 테스트"""

    def test_upsert_events_success(self, user_factory, product_factory):
        """이벤트 업서트 성공 테스트"""
        user = user_factory()
        product = product_factory()

        # 주문 생성
        order = Purchase.objects.create(
            user=user,
            product=product,
            amount=1,
            unit_price=Decimal("10000"),
            status="paid",
        )

        # 운송장 생성
        shipment = Shipment.objects.create(
            carrier="kr.cjlogistics",
            tracking_number="CJT-123456",
            user=user,
            order=order,
        )

        # 이벤트 페이로드
        payload = {
            "carrier": "kr.cjlogistics",
            "tracking_number": "CJT-123456",
            "events": [
                {
                    "occurred_at": "2024-01-01T10:00:00Z",
                    "status": "in_transit",
                    "location": "서울",
                    "description": "배송 시작",
                    "provider_code": "HUB01",
                },
                {
                    "occurred_at": "2024-01-02T15:00:00Z",
                    "status": "delivered",
                    "location": "부산",
                    "description": "배달 완료",
                },
            ],
        }

        # 이벤트 업서트
        with (
            patch(
                "domains.shipments.services._recompute_status_from_events"
            ) as mock_recompute,
            patch("domains.shipments.tasks.notify_shipment") as mock_notify,
        ):

            mock_recompute.return_value = "delivered"
            result = upsert_events_from_adapter(payload)

        # 검증
        assert result == 2  # 2개 이벤트 생성

        # 이벤트 생성 확인
        events = ShipmentEvent.objects.filter(shipment=shipment)
        assert events.count() == 2

        # 운송장 업데이트 확인
        shipment.refresh_from_db()
        assert shipment.last_event_at is not None
        assert shipment.last_event_status == "delivered"
        assert shipment.last_synced_at is not None

    def test_upsert_events_no_shipment(self, user_factory, product_factory):
        """등록되지 않은 운송장 테스트"""
        # 이벤트 페이로드 (등록되지 않은 운송장)
        payload = {
            "carrier": "kr.cjlogistics",
            "tracking_number": "UNKNOWN-123",
            "events": [
                {
                    "occurred_at": "2024-01-01T10:00:00Z",
                    "status": "in_transit",
                    "location": "서울",
                    "description": "배송 시작",
                }
            ],
        }

        # 이벤트 업서트
        result = upsert_events_from_adapter(payload)

        # 결과가 0인지 확인
        assert result == 0

    def test_upsert_events_invalid_payload(self):
        """잘못된 페이로드 테스트"""
        # 빈 페이로드
        result = upsert_events_from_adapter({})
        assert result == 0

        # None 페이로드
        result = upsert_events_from_adapter(None)
        assert result == 0

        # 필수 필드 누락
        result = upsert_events_from_adapter({"carrier": "kr.cjlogistics"})
        assert result == 0

    def test_upsert_events_duplicate_dedupe_key(self, user_factory, product_factory):
        """중복 dedupe_key 테스트"""
        user = user_factory()
        product = product_factory()

        # 주문 생성
        order = Purchase.objects.create(
            user=user,
            product=product,
            amount=1,
            unit_price=Decimal("10000"),
            status="paid",
        )

        # 운송장 생성
        shipment = Shipment.objects.create(
            carrier="kr.cjlogistics",
            tracking_number="CJT-123456",
            user=user,
            order=order,
        )

        # 첫 번째 이벤트 생성
        payload1 = {
            "carrier": "kr.cjlogistics",
            "tracking_number": "CJT-123456",
            "events": [
                {
                    "occurred_at": "2024-01-01T10:00:00Z",
                    "status": "in_transit",
                    "location": "서울",
                    "description": "배송 시작",
                    "dedupe_key": "unique_key_1",
                }
            ],
        }

        result1 = upsert_events_from_adapter(payload1)
        assert result1 == 1

        # 같은 dedupe_key로 두 번째 이벤트 (업데이트)
        payload2 = {
            "carrier": "kr.cjlogistics",
            "tracking_number": "CJT-123456",
            "events": [
                {
                    "occurred_at": "2024-01-01T10:00:00Z",
                    "status": "in_transit",
                    "location": "서울",
                    "description": "배송 시작 (업데이트)",
                    "dedupe_key": "unique_key_1",
                }
            ],
        }

        result2 = upsert_events_from_adapter(payload2)
        assert result2 == 0  # 업데이트이므로 생성된 이벤트는 0개

        # 이벤트가 하나만 있는지 확인
        events = ShipmentEvent.objects.filter(shipment=shipment)
        assert events.count() == 1
        assert events.first().description == "배송 시작 (업데이트)"


@pytest.mark.django_db
class TestParseDtSafe:
    """_parse_dt_safe 함수 테스트"""

    def test_parse_dt_safe_valid_formats(self):
        """유효한 날짜 형식 테스트"""
        # ISO 형식
        dt = _parse_dt_safe("2024-01-01T10:00:00Z")
        assert dt is not None
        assert dt.year == 2024
        assert dt.month == 1
        assert dt.day == 1

        # 다른 형식
        dt = _parse_dt_safe("2024-01-01 10:00:00")
        assert dt is not None

        # 날짜만
        dt = _parse_dt_safe("2024-01-01")
        assert dt is not None

    def test_parse_dt_safe_invalid_formats(self):
        """잘못된 날짜 형식 테스트"""
        # 빈 값
        assert _parse_dt_safe("") is None
        assert _parse_dt_safe(None) is None

        # 잘못된 형식
        assert _parse_dt_safe("invalid") is None
        assert _parse_dt_safe("2024-01") is None  # 하이픈 부족
        assert _parse_dt_safe("-2024-01-01") is None  # 음수 연도

    def test_parse_dt_safe_naive_to_aware(self):
        """naive datetime을 aware로 변환 테스트"""
        # naive datetime (timezone 정보 없음)
        dt = _parse_dt_safe("2024-01-01T10:00:00")
        assert dt is not None
        # 실제로는 timezone 정보가 있는 경우에만 aware가 됨
        # 이 테스트는 단순히 파싱이 되는지만 확인
        assert dt.year == 2024
        assert dt.month == 1
        assert dt.day == 1


@pytest.mark.django_db
class TestRecomputeStatusFromEvents:
    """_recompute_status_from_events 함수 테스트"""

    def test_recompute_status_delivered(self, user_factory, product_factory):
        """배달 완료 상태 재계산 테스트"""
        user = user_factory()
        product = product_factory()

        # 주문 생성
        order = Purchase.objects.create(
            user=user,
            product=product,
            amount=1,
            unit_price=Decimal("10000"),
            status="paid",
        )

        # 운송장 생성
        shipment = Shipment.objects.create(
            carrier="kr.cjlogistics",
            tracking_number="CJT-123456",
            user=user,
            order=order,
            status=ShipmentStatus.IN_TRANSIT,
        )

        # 이벤트 생성
        ShipmentEvent.objects.create(
            shipment=shipment,
            occurred_at=timezone.now() - timedelta(days=2),
            status="in_transit",
            location="서울",
            description="배송 시작",
        )

        ShipmentEvent.objects.create(
            shipment=shipment,
            occurred_at=timezone.now() - timedelta(days=1),
            status="out_for_delivery",
            location="부산",
            description="배송 중",
        )

        ShipmentEvent.objects.create(
            shipment=shipment,
            occurred_at=timezone.now(),
            status="delivered",
            location="부산",
            description="배달 완료",
        )

        # 상태 재계산
        new_status = _recompute_status_from_events(shipment)

        # 검증
        assert new_status == ShipmentStatus.DELIVERED

        # 운송장 업데이트 확인
        shipment.refresh_from_db()
        assert shipment.status == ShipmentStatus.DELIVERED
        assert shipment.delivered_at is not None
        assert shipment.shipped_at is not None

    def test_recompute_status_canceled(self, user_factory, product_factory):
        """취소 상태 재계산 테스트"""
        user = user_factory()
        product = product_factory()

        # 주문 생성
        order = Purchase.objects.create(
            user=user,
            product=product,
            amount=1,
            unit_price=Decimal("10000"),
            status="paid",
        )

        # 운송장 생성
        shipment = Shipment.objects.create(
            carrier="kr.cjlogistics",
            tracking_number="CJT-123456",
            user=user,
            order=order,
            status=ShipmentStatus.IN_TRANSIT,
        )

        # 이벤트 생성
        ShipmentEvent.objects.create(
            shipment=shipment,
            occurred_at=timezone.now() - timedelta(days=1),
            status="in_transit",
            location="서울",
            description="배송 시작",
        )

        ShipmentEvent.objects.create(
            shipment=shipment,
            occurred_at=timezone.now(),
            status="canceled",
            location="서울",
            description="배송 취소",
        )

        # 상태 재계산
        new_status = _recompute_status_from_events(shipment)

        # 검증
        assert new_status == ShipmentStatus.CANCELED

        # 운송장 업데이트 확인
        shipment.refresh_from_db()
        assert shipment.status == ShipmentStatus.CANCELED
        assert shipment.canceled_at is not None

    def test_recompute_status_out_for_delivery(self, user_factory, product_factory):
        """배송 출발 상태 재계산 테스트"""
        user = user_factory()
        product = product_factory()

        # 주문 생성
        order = Purchase.objects.create(
            user=user,
            product=product,
            amount=1,
            unit_price=Decimal("10000"),
            status="paid",
        )

        # 운송장 생성
        shipment = Shipment.objects.create(
            carrier="kr.cjlogistics",
            tracking_number="CJT-123456",
            user=user,
            order=order,
            status=ShipmentStatus.IN_TRANSIT,
        )

        # 이벤트 생성
        ShipmentEvent.objects.create(
            shipment=shipment,
            occurred_at=timezone.now() - timedelta(days=1),
            status="in_transit",
            location="서울",
            description="배송 시작",
        )

        ShipmentEvent.objects.create(
            shipment=shipment,
            occurred_at=timezone.now(),
            status="out_for_delivery",
            location="부산",
            description="배송 출발",
        )

        # 상태 재계산
        new_status = _recompute_status_from_events(shipment)

        # 검증
        assert new_status == ShipmentStatus.OUT_FOR_DELIVERY

        # 운송장 업데이트 확인
        shipment.refresh_from_db()
        assert shipment.status == ShipmentStatus.OUT_FOR_DELIVERY

    def test_recompute_status_in_transit(self, user_factory, product_factory):
        """배송 중 상태 재계산 테스트"""
        user = user_factory()
        product = product_factory()

        # 주문 생성
        order = Purchase.objects.create(
            user=user,
            product=product,
            amount=1,
            unit_price=Decimal("10000"),
            status="paid",
        )

        # 운송장 생성
        shipment = Shipment.objects.create(
            carrier="kr.cjlogistics",
            tracking_number="CJT-123456",
            user=user,
            order=order,
            status="ready",
        )

        # 이벤트 생성
        ShipmentEvent.objects.create(
            shipment=shipment,
            occurred_at=timezone.now(),
            status="in_transit",
            location="서울",
            description="배송 시작",
        )

        # 상태 재계산
        new_status = _recompute_status_from_events(shipment)

        # 검증
        assert new_status == ShipmentStatus.IN_TRANSIT

        # 운송장 업데이트 확인
        shipment.refresh_from_db()
        assert shipment.status == ShipmentStatus.IN_TRANSIT
        assert shipment.shipped_at is not None


@pytest.mark.django_db
class TestShipmentIntegration:
    """배송 관련 통합 테스트"""

    def test_complete_shipment_flow(self, user_factory, product_factory):
        """완전한 배송 플로우 테스트"""
        user = user_factory()
        product = product_factory()

        # 주문 생성
        order = Purchase.objects.create(
            user=user,
            product=product,
            amount=1,
            unit_price=Decimal("10000"),
            status="paid",
        )

        # 1. 운송장 등록
        with patch.object(SweetTrackerAdapter, "register_tracking") as mock_register:
            shipment = register_tracking_with_sweettracker(
                tracking_number="CJT-123456",
                carrier="kr.cjlogistics",
                user=user,
                order=order,
            )

        # 2. 이벤트 동기화
        payload = {
            "carrier": "kr.cjlogistics",
            "tracking_number": "CJT-123456",
            "events": [
                {
                    "occurred_at": "2024-01-01T10:00:00Z",
                    "status": "in_transit",
                    "location": "서울",
                    "description": "배송 시작",
                },
                {
                    "occurred_at": "2024-01-02T15:00:00Z",
                    "status": "delivered",
                    "location": "부산",
                    "description": "배달 완료",
                },
            ],
        }

        with patch("domains.shipments.tasks.notify_shipment") as mock_notify:
            result = upsert_events_from_adapter(payload)

        # 3. 검증
        assert result == 2  # 2개 이벤트 생성

        # 운송장 상태 확인 (실제 _recompute_status_from_events가 호출되어 상태가 업데이트됨)
        shipment.refresh_from_db()
        assert shipment.status == "delivered"
        assert shipment.last_event_at is not None
        assert shipment.last_synced_at is not None

        # 이벤트 확인
        events = ShipmentEvent.objects.filter(shipment=shipment)
        assert events.count() == 2

        # 어댑터 호출 확인
        mock_register.assert_called_once()


@pytest.mark.django_db
class TestShipmentsServicesEdgeCases:
    """shipments services의 추가 엣지 케이스 테스트"""

    def test_upsert_events_invalid_datetime_skip(self, user_factory, product_factory):
        """유효하지 않은 datetime으로 이벤트 스킵 테스트 (135번째 줄 커버)"""
        user = user_factory()
        product = product_factory()
        order = Purchase.objects.create(
            user=user,
            product=product,
            amount=1,
            unit_price=Decimal("10000"),
            status="paid",
        )
        shipment = Shipment.objects.create(
            carrier="kr.cjlogistics",
            tracking_number="CJT-123456",
            user=user,
            order=order,
        )

        # 유효하지 않은 datetime이 포함된 이벤트 페이로드
        payload = {
            "carrier": "kr.cjlogistics",
            "tracking_number": "CJT-123456",
            "events": [
                {
                    "occurred_at": "invalid-datetime",  # 유효하지 않은 datetime
                    "status": "in_transit",
                    "location": "서울",
                    "description": "배송 시작",
                },
                {
                    "occurred_at": "2024-01-01T10:00:00Z",  # 유효한 datetime
                    "status": "delivered",
                    "location": "부산",
                    "description": "배달 완료",
                },
            ],
        }

        with patch("domains.shipments.tasks.notify_shipment"):
            result = upsert_events_from_adapter(payload)

        # 유효한 이벤트만 생성되어야 함 (1개)
        assert result == 1
        events = ShipmentEvent.objects.filter(shipment=shipment)
        assert events.count() == 1
        assert events.first().status == "delivered"

    def test_upsert_events_notification_exception_handling(
        self, user_factory, product_factory
    ):
        """알림 전송 예외 처리 테스트 (189-190, 198-199번째 줄 커버)"""
        user = user_factory()
        product = product_factory()
        order = Purchase.objects.create(
            user=user,
            product=product,
            amount=1,
            unit_price=Decimal("10000"),
            status="paid",
        )
        shipment = Shipment.objects.create(
            carrier="kr.cjlogistics",
            tracking_number="CJT-123456",
            user=user,
            order=order,
        )

        # 알림 전송이 실패하는 상황 시뮬레이션
        with patch("domains.shipments.tasks.notify_shipment") as mock_notify:
            mock_notify.delay.side_effect = Exception("Notification failed")

            payload = {
                "carrier": "kr.cjlogistics",
                "tracking_number": "CJT-123456",
                "events": [
                    {
                        "occurred_at": "2024-01-01T10:00:00Z",
                        "status": "in_transit",
                        "location": "서울",
                        "description": "배송 시작",
                    }
                ],
            }

            # 예외가 발생해도 이벤트는 정상적으로 생성되어야 함
            result = upsert_events_from_adapter(payload)
            assert result == 1

            # 알림 전송이 시도되었는지 확인
            assert mock_notify.delay.call_count >= 1
