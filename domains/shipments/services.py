# domains/shipments/services.py
from __future__ import annotations

from typing import Any, Dict, Iterable, Optional

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
    사용자/주문 컨텍스트에서 운송장 등록 + 외부 등록 호출.
    이미 존재하면 기존 객체 반환.
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


@transaction.atomic
def upsert_events_from_adapter(payload: Dict[str, Any]) -> int:
    """
    외부 어댑터/웹훅에서 들어온 이벤트들을 upsert.

    payload 예:
    {
      "carrier": "kr.cjlogistics",
      "tracking_number": "1234567890",
      "events": [
        {
          "occurred_at": "2025-09-17T12:34:56+09:00",
          "status": "in_transit",
          "location": "서울중앙",
          "description": "허브 입고",
          "provider_code": "kr.cjlogistics",
          "source": "webhook" | "adapter"  # (뷰에서 주입 가능)
        },
        ...
      ],
      "payload": {...}   # optional
    }
    """
    raw = payload or {}
    carrier = raw.get("carrier") or raw.get("carrier_code") or ""
    tracking_number = raw.get("tracking_number") or raw.get("invoice_no") or ""
    if not (carrier and tracking_number):
        return 0

    # ⚠️ 웹훅이 먼저 오는 상황 방지: 등록된 운송장만 업데이트
    shipment: Optional[Shipment] = Shipment.objects.filter(
        tracking_number=tracking_number, carrier=carrier
    ).first()
    if shipment is None:
        # 정책에 따라 place-holder 생성으로 바꿀 수도 있음
        return 0

    events: Iterable[Dict[str, Any]] = raw.get("events") or []
    created_count = 0

    latest_dt: Optional[timezone.datetime] = None
    latest_status: Optional[str] = None
    latest_loc = ""
    latest_desc = ""

    for e in events:
        # 1) 키 매핑
        raw_time = (
            e.get("occurred_at")
            or e.get("time")
            or e.get("timestamp")
            or e.get("time_sweet")
        )
        status = (e.get("status") or e.get("state") or "").strip()
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

        # 2) 시간 정규화(연도 누락/이상치 스킵)
        dt = _parse_dt_safe(raw_time)
        if dt is None:
            continue

        # 3) dedupe 기준 (운송장 + 시각 + 상태 + 장소)
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

        # 4) 최신 이벤트 추출 (last_* 갱신용)
        if (latest_dt is None) or (dt > latest_dt):
            latest_dt = dt
            latest_status = status or None
            latest_loc = location or ""
            latest_desc = description or ""

    # 5) Shipment last_* & last_synced_at 갱신
    updates: Dict[str, Any] = {"last_synced_at": timezone.now()}
    if latest_dt:
        # status 값 유효성 체크 후 반영
        valid_statuses = set(dict(ShipmentStatus.choices).keys())
        safe_status = latest_status if latest_status in valid_statuses else None
        updates.update(
            {
                "last_event_at": latest_dt,
                "last_event_status": safe_status,
                "last_event_loc": latest_loc,
                "last_event_desc": latest_desc,
            }
        )
    Shipment.objects.filter(id=shipment.id).update(**updates)

    # 6) 상태/타임스탬프 자동 집계 (roll-up)
    rollup_status_for_shipment(shipment)

    return created_count


def _parse_dt_safe(value) -> Optional[timezone.datetime]:
    """ISO8601 파싱, 연도 누락/형식 오류면 None 반환."""
    if not value:
        return None
    s = str(value).strip()
    # "-09-17..." 같은 연도 누락 방어
    if s.startswith("-") or s.count("-") < 2:
        return None
    dt = parse_datetime(s)
    if dt is None:
        return None
    if dt.tzinfo is None:
        # naive → 현재 타임존 기준 aware 승격
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


def rollup_status_for_shipment(shipment: Shipment) -> str:
    """
    이벤트 테이블 기준으로 Shipment의 요약 상태/시각 필드 갱신.
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
