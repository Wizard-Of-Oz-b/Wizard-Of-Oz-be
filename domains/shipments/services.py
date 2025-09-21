# domains/shipments/services.py
from __future__ import annotations

from typing import Any, Dict, Iterable, Optional, Set
from datetime import datetime

from django.db import transaction
from django.db.models import Max, Min
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import Shipment, ShipmentEvent, ShipmentStatus
from .adapters.sweettracker import SweetTrackerAdapter


def register_tracking_with_sweettracker(
    *, tracking_number: str, carrier: str, user, order
) -> Shipment:
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


# ----------------- 헬퍼 -----------------
def _norm_status(s: str) -> str:
    if not s:
        return ""
    s = s.strip().lower().replace("-", "_")
    alias = {
        "intransit": "in_transit",
        "outfordelivery": "out_for_delivery",
        # 한글 별칭
        "배송중": "in_transit",
        "배송출발": "out_for_delivery",
        "배달완료": "delivered",
        "취소": "canceled",
        "반송": "returned",
    }
    return alias.get(s, s)

def _parse_dt_safe(value) -> Optional[datetime]:
    """ISO8601 파싱, 연도 누락/형식 오류면 None 반환."""
    if not value:
        return None
    s = str(value).strip()
    if s.startswith("-") or s.count("-") < 2:
        return None
    dt = parse_datetime(s)
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return dt

def _valid_statuses() -> Set[str]:
    """
    프로젝트별 구현차를 흡수해 유효 상태 집합을 안전하게 획득.
    - Django TextChoices: .values / .choices
    - Enum: 멤버 .value
    - 최후: 이벤트 테이블의 distinct(status)
    """
    # TextChoices(.values)
    vals = getattr(ShipmentStatus, "values", None)
    if vals:
        return set(vals)

    # TextChoices(.choices) 또는 choices 튜플
    ch = getattr(ShipmentStatus, "choices", None)
    if ch:
        try:
            return {c[0] for c in ch}
        except Exception:
            pass

    # Enum
    try:
        return {getattr(m, "value", m) for m in ShipmentStatus}  # type: ignore
    except Exception:
        pass

    # Fallback
    return set(
        ShipmentEvent.objects.values_list("status", flat=True).distinct()
    )
# ----------------------------------------


# Celery 진입점: 조회 → normalize → upsert
def sync_by_tracking(carrier: str, tracking_number: str, adapter=None) -> int:
    if adapter is None:
        from .adapters import get_adapter
        adapter = get_adapter(carrier)

    raw = adapter.fetch_tracking(tracking_number) or {}
    raw = dict(raw)
    raw.setdefault("carrier", carrier)
    raw.setdefault("tracking_number", tracking_number)

    events = adapter.parse_events(raw)
    payload = {
        "carrier": raw.get("carrier"),
        "tracking_number": raw.get("tracking_number"),
        "events": events,
    }
    return upsert_events_from_adapter(payload)


@transaction.atomic
def upsert_events_from_adapter(payload: Dict[str, Any]) -> int:
    raw = payload or {}
    carrier = raw.get("carrier") or raw.get("carrier_code") or ""
    tracking_number = raw.get("tracking_number") or raw.get("invoice_no") or ""
    if not (carrier and tracking_number):
        return 0

    shipment: Optional[Shipment] = Shipment.objects.filter(
        tracking_number=tracking_number, carrier=carrier
    ).first()
    if shipment is None:
        return 0

    events: Iterable[Dict[str, Any]] = raw.get("events") or []
    created_count = 0

    latest_dt: Optional[datetime] = None
    latest_status: Optional[str] = None
    latest_loc = ""
    latest_desc = ""

    for e in events:
        raw_time = (
            e.get("occurred_at")
            or e.get("time")
            or e.get("timestamp")
            or e.get("time_sweet")
        )
        status = _norm_status(e.get("status") or e.get("state") or "")
        location = (e.get("location") or e.get("where") or "").strip()
        description = (e.get("description") or e.get("details") or "").strip()
        provider_code = (
            e.get("provider_code")
            or raw.get("carrier")
            or raw.get("carrier_code")
            or ""
        )
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
            latest_loc = location or ""
            latest_desc = description or ""

    # last_* 1차 갱신
    updates: Dict[str, Any] = {"last_synced_at": timezone.now()}
    valid_statuses = _valid_statuses()

    if latest_dt:
        safe_status = latest_status if (latest_status in valid_statuses) else None
        updates.update(
            {
                "last_event_at": latest_dt,
                "last_event_status": safe_status,
                "last_event_loc": latest_loc,
                "last_event_desc": latest_desc,
            }
        )

    # 🔒 안전망: DB 최신 이벤트로 확정
    last_ev = (
        ShipmentEvent.objects
        .filter(shipment=shipment)
        .order_by("-occurred_at", "-created_at")
        .first()
    )
    if last_ev:
        normalized = _norm_status(last_ev.status or "")
        safe = normalized if normalized in valid_statuses else None
        updates.update(
            {
                "last_event_at": last_ev.occurred_at,
                "last_event_status": safe,
                "last_event_loc": last_ev.location or "",
                "last_event_desc": last_ev.description or "",
            }
        )

    Shipment.objects.filter(id=shipment.id).update(**updates)

    # 요약 상태/타임스탬프 롤업
    rollup_status_for_shipment(shipment)

    return created_count


def rollup_status_for_shipment(shipment: Shipment) -> str:
    """
    우선순위: canceled > returned > delivered > out_for_delivery > in_transit > pending
    """
    qs = ShipmentEvent.objects.filter(shipment=shipment)

    shipped_first = (
        qs.filter(status=ShipmentStatus.IN_TRANSIT).aggregate(first=Min("occurred_at"))["first"]
    )
    out4_exists = qs.filter(status=ShipmentStatus.OUT_FOR_DELIVERY).exists()
    delivered_last = (
        qs.filter(status=ShipmentStatus.DELIVERED).aggregate(last=Max("occurred_at"))["last"]
    )
    returned_last = (
        qs.filter(status=ShipmentStatus.RETURNED).aggregate(last=Max("occurred_at"))["last"]
    )
    canceled_last = (
        qs.filter(status=ShipmentStatus.CANCELED).aggregate(last=Max("occurred_at"))["last"]
    )
    in_transit_exist = qs.filter(status=ShipmentStatus.IN_TRANSIT).exists()

    new_status = ShipmentStatus.PENDING
    if canceled_last:
        new_status = ShipmentStatus.CANCELED
    elif returned_last:
        new_status = ShipmentStatus.RETURNED
    elif delivered_last:
        new_status = ShipmentStatus.DELIVERED
    elif out4_exists:
        new_status = ShipmentStatus.OUT_FOR_DELIVERY
    elif in_transit_exist:
        new_status = ShipmentStatus.IN_TRANSIT

    Shipment.objects.filter(id=shipment.id).update(
        status=new_status,
        shipped_at=shipped_first,
        delivered_at=delivered_last,
        canceled_at=canceled_last,
    )
    return new_status
