# domains/shipments/adapters/sweettracker.py
from typing import Any, Dict, List
from django.utils import timezone


class SweetTrackerAdapter:
    """
    외부 배송추적 제공자와의 경계. 실제 HTTP 호출은 추후 주입.
    """

    def register_tracking(self, *, tracking_number: str, carrier: str, fid: str) -> None:
        # 실제 서비스 붙일 때 외부 등록 API 호출 위치
        # 지금은 더미 (아무 것도 안 함)
        _ = {
            "tracking_number": tracking_number,
            "carrier_code": carrier,  # 외부 스펙이 carrier_code라면 이쪽에서만 변환
            "fid": fid,
        }

    def fetch_tracking(self, tracking_number: str) -> Dict[str, Any]:
        """
        [테스트용] 매 호출마다 현재시각 이벤트 1건을 반환해서
        폴링 파이프라인이 실제로 upsert되는지 확인할 수 있게 함.
        실제 연동 시에는 외부 API 응답을 그대로 리턴(or 가공)하세요.
        """
        return {
            "tracking_number": tracking_number,
            "carrier": "kr.cjlogistics",
            "events": [
                {
                    "occurred_at": timezone.now().isoformat(),  # 매번 다른 시각 → dedupe 통과
                    "status": "in_transit",
                    "location": "테스트HUB",
                    "description": "폴링테스트",
                }
            ],
        }

    def parse_events(self, raw: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        제공자 웹훅(raw) → 내부 통일 스키마로 변환
        내부 스키마 예시 키:
          - dedupe_key (str, unique)
          - where/location, details/description
          - time_sweet/occurred_at 등...
        """
        events = raw.get("events") or []
        out: List[Dict[str, Any]] = []
        for e in events:
            dedupe_key = (
                str(e.get("id"))
                or f"{raw.get('tracking_number','')}-{e.get('occurred_at') or e.get('time')}-{e.get('status')}"
            )
            out.append(
                {
                    "dedupe_key": dedupe_key,
                    # 아래 키들은 services.upsert_events_from_adapter에서 소화됩니다.
                    "where": e.get("location", "") or e.get("where", ""),
                    "details": e.get("description", "") or e.get("details", ""),
                    "occurred_at": e.get("occurred_at"),  # ISO8601 문자열
                    "time": e.get("time") or e.get("time_sweet"),
                    "status": e.get("status"),
                    "provider_code": e.get("carrier_code") or raw.get("carrier") or raw.get("carrier_code"),
                }
            )
        return out
