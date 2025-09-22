# domains/shipments/tasks.py
from __future__ import annotations

from typing import Any, Dict, Optional
from celery import shared_task
import json
from django.utils.timezone import localtime
from django.core.serializers.json import DjangoJSONEncoder

@shared_task(bind=True, max_retries=3, retry_backoff=True, retry_jitter=True, acks_late=True,
            name="domains.shipments.tasks.poll_shipment")
def poll_shipment(self, carrier: str, tracking_number: str) -> int:
    """
    단일 운송장 폴링 → 외부 어댑터 조회 → 이벤트 upsert
    반환: 생성된 이벤트 수
    """
    try:
        from .services import sync_by_tracking
        return int(sync_by_tracking(carrier, tracking_number))
    except Exception as e:
        raise self.retry(exc=e)

@shared_task(name="domains.shipments.tasks.poll_open_shipments")
def poll_open_shipments() -> None:
    """
    진행중인 건만 순회 폴링
    """
    from .models import Shipment
    qs = Shipment.objects.filter(status__in=["pending", "in_transit", "out_for_delivery"])
    for s in qs.iterator():
        poll_shipment.delay(s.carrier, s.tracking_number)

def _dt(v):
    if not v:
        return None
    try:
        return localtime(v).isoformat()
    except Exception:
        return str(v)

@shared_task(name="domains.shipments.tasks.notify_shipment")
def notify_shipment(shipment_id: str, event_type: str, payload: dict):
    # 지연 임포트로 순환참조 회피
    from .models import Shipment

    try:
        sh = Shipment.objects.get(id=shipment_id)
        body = {
            "type": event_type,
            "shipment": {
                "id": str(sh.id),
                "carrier": sh.carrier,
                "tracking_number": sh.tracking_number,
                "status": sh.status,
                "last_event_status": sh.last_event_status,
                "last_event_at": _dt(sh.last_event_at),
                "last_event_loc": sh.last_event_loc,
                "last_event_desc": sh.last_event_desc,
                "shipped_at": _dt(sh.shipped_at),
                "delivered_at": _dt(sh.delivered_at),
                "canceled_at": _dt(sh.canceled_at),
            },
            **(payload or {}),
        }

        print("[NOTIFY] " + json.dumps(body, ensure_ascii=False, cls=DjangoJSONEncoder), flush=True)

    except Exception as e:
        print(f"[NOTIFY][ERROR] {e}")
