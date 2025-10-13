# tests/test_shipments_services_unit.py
import pytest

import domains.shipments.services as svc

# 모델/상수 안전 임포트
from domains.orders.models import Purchase
from domains.shipments import models as ship_models

Shipment = ship_models.Shipment
ShipmentEvent = ship_models.ShipmentEvent
ShipmentStatus = getattr(
    ship_models, "ShipmentStatus", None
)  # TextChoices 일 수도, 없을 수도


def S(name: str, default: str):
    """ShipmentStatus(TextChoices) 존재 시 값을, 없으면 문자열 기본값."""
    if ShipmentStatus is None:
        return default
    val = getattr(ShipmentStatus, name, None)
    if val is None:
        return default
    return getattr(val, "value", str(val))


@pytest.mark.django_db
def test_upsert_events_idempotent_and_status_rollup(user_factory, product_factory):
    user = user_factory()
    product = product_factory()

    # Shipment 가 NOT NULL order FK 요구 → 우선 구매를 만들어서 연결
    purchase = Purchase.objects.create(
        user=user,
        product_id=product.id,
        status=getattr(Purchase, "STATUS_PAID", "paid"),
    )

    sh = Shipment.objects.create(
        user=user,
        order=purchase,  # ★ order 필수
        carrier="kr.cjlogistics",
        tracking_number="CJT123",
        status=S("PENDING", "PENDING"),
    )

    payload = {
        "carrier": "kr.cjlogistics",
        "tracking_number": "CJT123",
        "events": [
            {
                "occurred_at": "2025-09-24T01:00:00Z",
                "status": "in_transit",
                "location": "강남허브",
                "description": "집화완료",
                "provider_code": "HUB01",
            },
            {
                "occurred_at": "2025-09-24T03:00:00Z",
                "status": "out_for_delivery",
                "location": "강남구",
                "description": "배송출발",
                "provider_code": "GANGNAM",
            },
        ],
    }

    created = svc.upsert_events_from_adapter(payload)
    assert created >= 2

    sh.refresh_from_db()
    assert sh.last_event_status in ("out_for_delivery", "in_transit")
    assert sh.status in (
        S("OUT_FOR_DELIVERY", "OUT_FOR_DELIVERY"),
        S("IN_TRANSIT", "IN_TRANSIT"),
        S("DELIVERED", "DELIVERED"),
        S("CANCELED", "CANCELED"),
    )

    # 멱등성
    assert svc.upsert_events_from_adapter(payload) == 0

    # 배송완료 이벤트 추가 → DELIVERED
    payload["events"].append(
        {
            "occurred_at": "2025-09-24T06:00:00Z",
            "status": "delivered",
            "location": "수령지",
            "description": "배송완료",
            "provider_code": "LAST",
        }
    )
    assert svc.upsert_events_from_adapter(payload) == 1

    sh.refresh_from_db()
    assert sh.status == S("DELIVERED", "DELIVERED")


@pytest.mark.django_db
def test_sync_by_tracking_uses_adapter_and_updates(user_factory, product_factory):
    user = user_factory()
    product = product_factory()

    purchase = Purchase.objects.create(
        user=user,
        product_id=product.id,
        status=getattr(Purchase, "STATUS_PAID", "paid"),
    )

    sh = Shipment.objects.create(
        user=user,
        order=purchase,  # ★ order 필수
        carrier="kr.cjlogistics",
        tracking_number="CJT999",
        status=S("PENDING", "PENDING"),
    )

    class FakeAdapter:
        def fetch_tracking(self, tracking_number):
            assert tracking_number == "CJT999"
            return {
                "carrier": "kr.cjlogistics",
                "tracking_number": "CJT999",
                "trace": "raw body ...",
            }

        def parse_events(self, raw):
            return [
                {
                    "occurred_at": "2025-09-24T01:00:00Z",
                    "status": "in_transit",
                    "location": "서울허브",
                    "description": "집화",
                },
                {
                    "occurred_at": "2025-09-24T03:00:00Z",
                    "status": "out_for_delivery",
                    "location": "강남구",
                    "description": "배송출발",
                },
            ]

    created = svc.sync_by_tracking(
        carrier="kr.cjlogistics",
        tracking_number="CJT999",
        adapter=FakeAdapter(),
    )
    assert created == 2

    sh.refresh_from_db()
    assert sh.last_event_status in ("out_for_delivery", "in_transit")
    assert sh.status in (
        S("OUT_FOR_DELIVERY", "OUT_FOR_DELIVERY"),
        S("IN_TRANSIT", "IN_TRANSIT"),
    )
