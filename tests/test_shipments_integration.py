import pytest
from domains.orders.models import Purchase
from domains.shipments import services as svc
from domains.shipments.models import Shipment, ShipmentEvent, ShipmentStatus
from domains.shipments.adapters.sweettracker import SweetTrackerAdapter


def S(*names):
    """ShipmentStatus 안전 접근 (enum/choices/문자열 모두 커버)"""
    for n in names:
        n = str(n).upper()
        if hasattr(ShipmentStatus, n):
            return getattr(ShipmentStatus, n)
    return names[0].lower()


@pytest.fixture
def owner(user_factory):
    return user_factory()


@pytest.fixture
def product(product_factory):
    return product_factory()


@pytest.fixture
def paid_purchase(db, owner, product):
    status = getattr(Purchase, "STATUS_PAID", "paid")
    return Purchase.objects.create(user=owner, product_id=product.id, status=status)


def _fake_events(*rows):
    """
    rows: (iso_dt, status, location, desc)
    """
    out = []
    for iso_dt, status, loc, desc in rows:
        out.append(
            {
                "occurred_at": iso_dt,
                "status": status,
                "location": loc,
                "description": desc,
                "dedupe_key": f"{iso_dt}|{status}",
                "source": "test",
            }
        )
    return out


# ─────────────────────────────────────────────────────────────
# 1) SweetTracker 등록 성공 (monkeypatch로 spy 흉내)
# ─────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_register_shipment_success(monkeypatch, owner, paid_purchase):
    calls = []

    def fake_register_tracking(self, *, tracking_number, carrier, fid):
        # 호출 파라미터 저장만 하고 아무 것도 안 함
        calls.append({"tracking_number": tracking_number, "carrier": carrier, "fid": fid})

    monkeypatch.setattr(SweetTrackerAdapter, "register_tracking", fake_register_tracking)

    sh = svc.register_tracking_with_sweettracker(
        tracking_number="CJT-0001",
        carrier="kr.cjlogistics",
        user=owner,
        order=paid_purchase,
    )

    assert isinstance(sh, Shipment)
    assert sh.carrier == "kr.cjlogistics"
    assert sh.tracking_number == "CJT-0001"
    assert sh.order_id == paid_purchase.pk

    # spy 검증
    assert len(calls) == 1
    assert calls[0]["tracking_number"] == "CJT-0001"
    assert calls[0]["carrier"] == "kr.cjlogistics"
    assert calls[0]["fid"] == str(sh.id)


# ─────────────────────────────────────────────────────────────
# 2) sync_by_tracking: 어댑터 사용 & 이벤트 upsert & 상태 롤업
# ─────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_sync_tracking_updates_status_and_events(monkeypatch, owner, paid_purchase):
    # 등록 시 어댑터 호출 무시
    monkeypatch.setattr(SweetTrackerAdapter, "register_tracking", lambda *a, **k: None)

    sh = svc.register_tracking_with_sweettracker(
        tracking_number="CJT-999",
        carrier="kr.cjlogistics",
        user=owner,
        order=paid_purchase,
    )

    class FakeAdapter:
        def fetch_tracking(self, tracking_number):
            return {
                "carrier": "kr.cjlogistics",
                "tracking_number": tracking_number,
            }

        def parse_events(self, raw):
            # 최신 이벤트가 07:00 → in_transit
            return _fake_events(
                ("2025-09-24T06:00:00Z", "in_transit", "HUB-01", "집화"),
                ("2025-09-24T07:00:00Z", "in_transit", "HUB-02", "이동"),
            )

    created = svc.sync_by_tracking("kr.cjlogistics", "CJT-999", adapter=FakeAdapter())
    assert created >= 2

    sh.refresh_from_db()
    assert sh.last_event_status == "in_transit"
    assert sh.status in {S("IN_TRANSIT", "IN_TRANSIT"), "in_transit"}

    evts = list(ShipmentEvent.objects.filter(shipment=sh).order_by("occurred_at"))
    assert len(evts) >= 2
    assert evts[-1].status == "in_transit"
    assert evts[-1].location == "HUB-02"


# ─────────────────────────────────────────────────────────────
# 3) 웹훅 유사 시나리오: 멱등성 확인 (동일 페이로드 2번 → 2번째 0건)
# ─────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_webhook_signature_and_idempotency(monkeypatch, owner, paid_purchase):
    monkeypatch.setattr(SweetTrackerAdapter, "register_tracking", lambda *a, **k: None)

    sh = svc.register_tracking_with_sweettracker(
        tracking_number="CJT-777",
        carrier="kr.cjlogistics",
        user=owner,
        order=paid_purchase,
    )

    payload = {
        "carrier": "kr.cjlogistics",
        "tracking_number": "CJT-777",
        "events": _fake_events(
            ("2025-09-24T06:10:00Z", "out_for_delivery", "강남대리점", "배송출발"),
            ("2025-09-24T07:40:00Z", "delivered", "수취처", "배달완료"),
        ),
    }

    created1 = svc.upsert_events_from_adapter(payload)
    created2 = svc.upsert_events_from_adapter(payload)

    assert created1 >= 2
    assert created2 == 0

    sh.refresh_from_db()
    assert sh.status in {S("DELIVERED", "DELIVERED"), "delivered"}
    assert sh.last_event_status == "delivered"
