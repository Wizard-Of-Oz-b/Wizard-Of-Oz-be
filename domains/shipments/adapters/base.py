# domains/shipments/adapters/base.py
from typing import Any, Dict, List

class CarrierAdapter:
    """
    각 택배사 어댑터의 최소 공통 인터페이스
    """

    def register_tracking(self, *, tracking_number: str, carrier: str, fid: str) -> None:
        """
        (옵션) 외부 서비스에 트래킹 번호를 등록해야 할 때 사용.
        기본 구현은 no-op.
        """
        return None

    def fetch_tracking(self, tracking_number: str) -> Dict[str, Any]:
        """
        (옵션) 외부 조회 API에서 원본 payload를 가져오는 함수.
        테스트/더미 기본 구현은 이벤트 없음.
        """
        return {"tracking_number": tracking_number, "events": []}

    def parse_events(self, raw: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        외부 원본 payload(raw) → 내부 공통 스키마(events)로 변환.
        기본 구현은 이미 표준 스키마라고 가정하고 그대로 반환.
        """
        return raw.get("events") or []
