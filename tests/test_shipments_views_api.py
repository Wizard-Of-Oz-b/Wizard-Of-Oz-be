import pytest
from rest_framework.test import APIClient

@pytest.mark.django_db
def test_shipments_register_and_sync(monkeypatch, user_factory, product_factory, create_stock):
    user = user_factory(role="admin")
    product = product_factory()
    create_stock(product, {}, 1)

    # 구매 하나 만들어두기(유료)
    from domains.orders.models import Purchase
    paid = Purchase.objects.create(user=user, product=product,
                                   status=getattr(Purchase, "STATUS_PAID","paid"))

    c = APIClient(); c.force_authenticate(user=user)

    # 어댑터 가짜 등록
    from domains.shipments.adapters.sweettracker import SweetTrackerAdapter
    reg_calls = []
    def fake_register(self, *, tracking_number, carrier, fid):
        reg_calls.append((tracking_number, carrier, fid))
    monkeypatch.setattr(SweetTrackerAdapter, "register_tracking", fake_register)

    # register
    r = c.post("/api/v1/shipments/register/", {
        "carrier":"kr.cjlogistics", "tracking_number":"CJT-1001", "purchase_id": str(paid.pk)
    }, format="json")
    assert r.status_code in (200,201,204,403)


    # sync 가짜
    def fake_fetch(self, tracking_number):
        return {
            "carrier":"kr.cjlogistics","tracking_number":tracking_number,
            "events":[{"occurred_at":"2025-09-24T01:00:00Z","status":"in_transit"}]
        }
    monkeypatch.setattr(SweetTrackerAdapter, "fetch_tracking", fake_fetch)
    def fake_parse_events(self, raw):
        return raw["events"]
    monkeypatch.setattr(SweetTrackerAdapter, "parse_events", fake_parse_events)

    r = c.post("/api/v1/shipments/sync/", {
        "carrier":"kr.cjlogistics",
        "tracking_number":"CJT-1001",
        "purchase_id": str(paid.pk)
    }, format="json")
    assert r.status_code in (200,201,204)
