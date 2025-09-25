# tests/test_shipments_services_edgecases.py
import pytest
import domains.shipments.services as svc
from domains.orders.models import Purchase
from domains.shipments import models as ship_models

Shipment = ship_models.Shipment
ShipmentEvent = ship_models.ShipmentEvent
ShipmentStatus = getattr(ship_models, "ShipmentStatus", None)

def S(name: str, default: str):
    if ShipmentStatus is None:
        return default
    val = getattr(ShipmentStatus, name, None)
    if val is None:
        return default
    return getattr(val, "value", str(val))

@pytest.mark.django_db
def test_ignores_bad_datetime(user_factory, product_factory):
    user = user_factory()
    product = product_factory()
    purchase = Purchase.objects.create(user=user, product_id=product.id,
                                       status=getattr(Purchase,"STATUS_PAID","paid"))

    Shipment.objects.create(
        user=user, order=purchase, carrier="kr.cjlogistics",
        tracking_number="BADTIME", status=S("PENDING","PENDING")
    )

    payload = {
        "carrier": "kr.cjlogistics",
        "tracking_number": "BADTIME",
        "events": [
            {"occurred_at": "nope", "status": "in_transit"},     # 무시됨
            {"occurred_at": "2025-09-24T05:00:00Z", "status": "in_transit"},  # 유효
        ],
    }
    created = svc.upsert_events_from_adapter(payload)
    assert created == 1

@pytest.mark.django_db
def test_canceled_overrides_delivered_if_latest(user_factory, product_factory):
    user = user_factory()
    product = product_factory()
    purchase = Purchase.objects.create(user=user, product_id=product.id,
                                       status=getattr(Purchase,"STATUS_PAID","paid"))

    sh = Shipment.objects.create(
        user=user, order=purchase, carrier="kr.cjlogistics",
        tracking_number="CANCELWIN", status=S("PENDING","PENDING")
    )

    payload = {
        "carrier": "kr.cjlogistics", "tracking_number": "CANCELWIN",
        "events": [
            {"occurred_at": "2025-09-24T06:00:00Z", "status": "delivered"},
            {"occurred_at": "2025-09-24T07:00:00Z", "status": "canceled"},  # 더 늦음 → CANCELED
        ],
    }
    svc.upsert_events_from_adapter(payload)
    sh.refresh_from_db()
    assert sh.status == S("CANCELED","CANCELED")

@pytest.mark.django_db
def test_delivered_wins_if_later_than_canceled(user_factory, product_factory):
    user = user_factory()
    product = product_factory()
    purchase = Purchase.objects.create(user=user, product_id=product.id,
                                       status=getattr(Purchase,"STATUS_PAID","paid"))

    sh = Shipment.objects.create(
        user=user, order=purchase, carrier="kr.cjlogistics",
        tracking_number="DELIWIN", status=S("PENDING","PENDING")
    )
    payload = {
        "carrier": "kr.cjlogistics", "tracking_number": "DELIWIN",
        "events": [
            {"occurred_at": "2025-09-24T06:00:00Z", "status": "canceled"},
            {"occurred_at": "2025-09-24T07:30:00Z", "status": "delivered"},  # 더 늦음 → DELIVERED
        ],
    }
    svc.upsert_events_from_adapter(payload)
    sh.refresh_from_db()
    assert sh.status == S("DELIVERED","DELIVERED")

@pytest.mark.django_db
def test_out_for_delivery_without_in_transit(user_factory, product_factory):
    user = user_factory()
    product = product_factory()
    purchase = Purchase.objects.create(user=user, product_id=product.id,
                                       status=getattr(Purchase,"STATUS_PAID","paid"))

    sh = Shipment.objects.create(
        user=user, order=purchase, carrier="kr.cjlogistics",
        tracking_number="ONLYOFD", status=S("PENDING","PENDING")
    )
    payload = {
        "carrier": "kr.cjlogistics", "tracking_number": "ONLYOFD",
        "events": [
            {"occurred_at": "2025-09-24T03:00:00Z", "status": "out_for_delivery"},
        ],
    }
    svc.upsert_events_from_adapter(payload)
    sh.refresh_from_db()
    assert sh.status == S("OUT_FOR_DELIVERY","OUT_FOR_DELIVERY")
