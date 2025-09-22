# domains/shipments/notifications.py
from __future__ import annotations

import json
from typing import Any, Dict, Optional
from dataclasses import asdict, dataclass
from urllib.request import Request, urlopen
from urllib.error import URLError
from django.conf import settings

@dataclass
class ShipmentSnapshot:
    id: str
    carrier: str
    tracking_number: str
    status: str
    last_event_status: Optional[str]
    last_event_at: Optional[str]
    last_event_loc: str
    last_event_desc: str
    shipped_at: Optional[str]
    delivered_at: Optional[str]
    canceled_at: Optional[str]

def _dump_shipment(shipment) -> Dict[str, Any]:
    return asdict(ShipmentSnapshot(
        id=str(shipment.id),
        carrier=shipment.carrier,
        tracking_number=shipment.tracking_number,
        status=shipment.status,
        last_event_status=shipment.last_event_status,
        last_event_at=shipment.last_event_at.isoformat() if shipment.last_event_at else None,
        last_event_loc=shipment.last_event_loc or "",
        last_event_desc=shipment.last_event_desc or "",
        shipped_at=shipment.shipped_at.isoformat() if shipment.shipped_at else None,
        delivered_at=shipment.delivered_at.isoformat() if shipment.delivered_at else None,
        canceled_at=shipment.canceled_at.isoformat() if shipment.canceled_at else None,
    ))

def _post_json(url: str, payload: Dict[str, Any]) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = Request(url, data=body, headers={"Content-Type": "application/json"})
    with urlopen(req, timeout=5) as _:
        pass

def send_notification(kind: str, shipment, meta: Optional[Dict[str, Any]] = None) -> None:
    """
    kind: "events_appended" | "status_changed"
    meta: 자유 필드 (예: {"created":3, "latest_event": {...}} 등)
    """
    payload = {
        "type": kind,
        "shipment": _dump_shipment(shipment),
        "meta": meta or {},
    }

    url = getattr(settings, "SHIPMENTS_NOTIFY_WEBHOOK", None)
    if url:
        try:
            _post_json(url, payload)
        except URLError as e:
            print(f"[NOTIFY][ERROR] urlopen failed: {e}")
    else:
        # 웹훅 미설정 시 콘솔로 남김 (워커 로그에서 grep 가능)
        print("[NOTIFY]", json.dumps(payload, ensure_ascii=False))
