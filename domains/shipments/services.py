# domains/shipments/services.py
from __future__ import annotations

from typing import Any, Dict, Iterable, Optional, Tuple

from django.db import transaction
from django.db.models import Max, Min
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import Shipment, ShipmentEvent, ShipmentStatus
from .adapters.sweettracker import SweetTrackerAdapter


def register_tracking_with_sweettracker(
    *, tracking_number: str, carrier: str, user, order
) -> Shipment:
    """
    (order, tracking_number) 조합을 등록하고, 어댑터에 fid(=shipment.id) 등록까지 수행.
    - Shipment.user 는 order.user로 일관화하는 게 안전하지만, 호출부에서 user를 넘기면 그대로 사용.
    """
    shipment, _ = Shipment.objects.get_or_create(
        carrier=carrier,
        tracking_number=tracking_number,
        defaults={"user": user, "order": order},
    )
    SweetTrackerAdapter().register_tracking(
        tracking_number=tracking_number,
        carrier=carrier,
        fid=str(shipment.id),
    )
    return shipment


# === 동기화(폴링/트리거) 진입점 ==============================================
def sync_by_tracking(carrier: str, tracking_number: str, adapter=None) -> int:
    """
    carrier/운송장으로 어댑터에서 조회 → events 파싱 → upsert.
    반환값: 생성/업데이트된 이벤트 개수
    """
    if adapter is None:
        try:
            from .adapters import get_adapter
            adapter = get_adapter(carrier)
        except Exception:
            adapter = SweetTrackerAdapter()

    raw = adapter.fetch_tracking(tracking_number)
    raw = dict(raw or {})
    raw.setdefault("carrier", carrier)
    raw.setdefault("tracking_number", tracking_number)

    events = adapter.parse_events(raw)  # [{occurred_at, status, location, description, ...}, ...]
    payload = {
        "carrier": raw.get("carrier"),
        "tracking_number": raw.get("tracking_number"),
        "events": events,
    }
    return upsert_events_from_adapter(payload)
# ============================================================================


def _norm_status(s: str) -> str:
    if not s:
        return ""
    s = str(s).strip().lower().replace("-", "_")
    alias = {
        "intransit": "in_transit",
        "outfordelivery": "out_for_delivery",
        "배송중": "in_transit",
        "배송출발": "out_for_delivery",
        "배달완료": "delivered",
        "취소": "canceled",
        "반송": "returned",
    }
    return alias.get(s, s)


@transaction.atomic
def upsert_events_from_adapter(payload: Dict[str, Any]) -> int:
    """
    payload 예:
    {
      "carrier": "kr.cjlogistics",
      "tracking_number": "123",
      "events": [
         {"occurred_at": "...", "status": "in_transit", "location": "...", "description": "...", "provider_code": "HUB01", "dedupe_key": "..."},
         ...
      ]
    }
    """
    raw = payload or {}
    carrier = raw.get("carrier") or raw.get("carrier_code") or ""
    tracking_number = raw.get("tracking_number") or raw.get("invoice_no") or ""
    if not (carrier and tracking_number):
        return 0

    # 등록된 운송장만 업데이트
    shipment: Optional[Shipment] = Shipment.objects.filter(
        tracking_number=tracking_number, carrier=carrier
    ).first()
    if shipment is None:
        return 0

    # 알림 비교를 위한 이전 스냅샷
    prev_status = shipment.status
    prev_last_event_at = shipment.last_event_at

    events: Iterable[Dict[str, Any]] = raw.get("events") or []
    created_count = 0

    latest_dt = None
    latest_status = None
    latest_loc = None
    latest_desc = None

    for e in events:
        status = _norm_status(e.get("status"))
        raw_time = (
            e.get("occurred_at")
            or e.get("time")
            or e.get("when")
            or e.get("timestamp")
            or e.get("datetime")
            or ""
        )
        location = e.get("location") or e.get("where") or ""
        description = e.get("description") or e.get("details") or e.get("desc") or ""
        provider_code = e.get("provider_code") or e.get("code") or ""
        source = e.get("source") or "adapter"
        raw_payload = e.get("raw_payload", e)

        dt = _parse_dt_safe(raw_time)
        if dt is None:
            continue

        dedupe_key = e.get("dedupe_key") or f"{shipment.id}|{dt.isoformat()}|{status}|{location}"

        _, created = ShipmentEvent.objects.update_or_create(
            dedupe_key=dedupe_key,
            defaults={
                "shipment": shipment,
                "occurred_at": dt,
                "status": status,
                "location": location,
                "description": description,
                "provider_code": provider_code,
                "raw_payload": raw_payload,
                "source": source,
            },
        )
        if created:
            created_count += 1

        if (latest_dt is None) or (dt > latest_dt):
            latest_dt = dt
            latest_status = status or None
            latest_loc = location or None
            latest_desc = description or None

    # 최신 이벤트 스냅샷/last_synced_at
    if latest_dt:
        Shipment.objects.filter(id=shipment.id).update(
            last_event_at=latest_dt,
            last_event_status=latest_status,
            last_event_loc=latest_loc,
            last_event_desc=latest_desc,
            last_synced_at=timezone.now(),
        )

    # 전체 상태 재계산
    new_status = _recompute_status_from_events(shipment)

    # 1) 마지막 이벤트 시간이 바뀐 경우 알림
    if latest_dt and (prev_last_event_at != latest_dt):
        try:
            from .tasks import notify_shipment  # celery optional
            meta = {
                "latest_event": {
                    "occurred_at": latest_dt.isoformat() if latest_dt else None,
                    "status": latest_status,
                    "location": latest_loc,
                    "description": latest_desc,
                },
                "created": created_count,
            }
            notify_shipment.delay(str(shipment.id), "events_appended", meta)
        except Exception:
            pass

    # 2) 상태가 바뀐 경우 알림
    if new_status != prev_status:
        try:
            from .tasks import notify_shipment
            meta = {"prev": prev_status, "curr": new_status}
            notify_shipment.delay(str(shipment.id), "status_changed", meta)
        except Exception:
            pass

    return created_count


def _parse_dt_safe(value) -> Optional[timezone.datetime]:
    if not value:
        return None
    s = str(value).strip()
    if s.startswith("-") or s.count("-") < 2:
        return None
    dt = parse_datetime(s)
    try:
        # naive → aware 보정
        if dt and timezone.is_naive(dt):
            dt = timezone.make_aware(dt, timezone=timezone.utc)
    except Exception:
        pass
    return dt


def _recompute_status_from_events(shipment: Shipment) -> str:
    """
    이벤트 집계로 Shipment.status, shipped_at, delivered_at, canceled_at 갱신
    """
    qs = ShipmentEvent.objects.filter(shipment_id=shipment.id)
    shipped_first = qs.filter(status="in_transit").aggregate(Min("occurred_at"))["occurred_at__min"]
    delivered_last = qs.filter(status="delivered").aggregate(Max("occurred_at"))["occurred_at__max"]
    canceled_last = qs.filter(status="canceled").aggregate(Max("occurred_at"))["occurred_at__max"]
    out4_exists = qs.filter(status="out_for_delivery").exists()
    in_transit_ok = qs.filter(status="in_transit").exists()

    new_status = shipment.status
    if canceled_last and (not delivered_last or canceled_last >= delivered_last):
        new_status = ShipmentStatus.CANCELED
    elif delivered_last:
        new_status = ShipmentStatus.DELIVERED
    elif out4_exists:
        new_status = ShipmentStatus.OUT_FOR_DELIVERY
    elif in_transit_ok:
        new_status = ShipmentStatus.IN_TRANSIT

    Shipment.objects.filter(id=shipment.id).update(
        status=new_status,
        shipped_at=shipped_first,
        delivered_at=delivered_last,
        canceled_at=canceled_last,
    )
    return new_status
