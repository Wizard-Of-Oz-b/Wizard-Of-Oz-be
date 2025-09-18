# domains/shipments/adapters/base.py
from abc import ABC, abstractmethod
from typing import Dict, Iterable, Any

class CarrierAdapter(ABC):
    provider: str  # "DT" 등 내부 식별자

    @abstractmethod
    def fetch_tracking(self, tracking_number: str) -> Dict[str, Any]:
        """원격 API 호출, provider 원본 JSON 반환"""

    @abstractmethod
    def normalize_events(self, payload: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
        """
        원본 → 내부 표준 이벤트 변환
        return: [{occurred_at: dt, status: 'in_transit', location: str, description: str,
                  provider_code: str, raw: dict, dedupe_key: str}]
        """

    @abstractmethod
    def verify_webhook(self, request) -> bool:
        """웹훅 서명 검증"""

    @abstractmethod
    def parse_webhook(self, request) -> Dict[str, Any]:
        """웹훅 바디 파싱 → fetch_tracking과 동일 스키마로 맞춰 반환(또는 events 중심)"""
