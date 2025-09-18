# domains/shipments/adapters/provider.py
import hashlib, hmac, json
from typing import Dict, Iterable
from .base import CarrierAdapter
from ..status_map import map_provider_status
from django.utils.dateparse import parse_datetime

class DTAdapter(CarrierAdapter):
    provider = "DT"

    def fetch_tracking(self, tracking_number: str) -> Dict[str, any]:
        # requests.get(...) 호출부 (timeout, retry는 세션에서 관리)
        # 여기서는 스켈레톤만:
        return {"tracking_number": tracking_number, "events": []}

    def normalize_events(self, payload: Dict[str, any]) -> Iterable[Dict[str, any]]:
        events = payload.get("events", [])
        for ev in events:
            internal = map_provider_status(ev.get("status"))
            occurred = parse_datetime(ev.get("time"))  # "2025-09-16T04:20:00Z" 등
            yield {
                "occurred_at": occurred,
                "status": internal,
                "location": ev.get("location") or "",
                "description": ev.get("description") or "",
                "provider_code": ev.get("status"),
                "raw": ev,
                "dedupe_key": f"DT:{payload.get('tracking_number')}:{ev.get('id') or ev.get('time')}",
            }

    def verify_webhook(self, request) -> bool:
        sig = request.headers.get("X-Provider-Signature")
        secret = (getattr(request, "webhook_secret", None)  # 주입 or settings
                  or "")
        mac = hmac.new(secret.encode(), request.body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(sig or "", mac)

    def parse_webhook(self, request) -> Dict[str, any]:
        return json.loads(request.body.decode("utf-8"))
