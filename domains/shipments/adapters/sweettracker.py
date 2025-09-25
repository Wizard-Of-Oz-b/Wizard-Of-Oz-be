# domains/shipments/adapters/sweettracker.py
import os
import requests
import logging
from typing import Any, Dict, List, Optional
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


class SweetTrackerAdapter:
    """
    SweetTracker API와의 실제 연동을 위한 어댑터
    """

    def __init__(self):
        # 환경변수에서 직접 API 키 가져오기
        self.api_key = os.getenv('SMARTPARCEL_API_KEY', '')
        self.base_url = os.getenv('SMARTPARCEL_HOST', 'https://trace-api.sweettracker.net')
        
        # 택배사 코드 매핑 (SweetTracker API에서 사용하는 코드)
        self.carrier_code_map = {
            'kr.cjlogistics': '04',  # CJ대한통운
            'kr.logen': '05',        # 로젠택배
            'kr.hanjin': '01',       # 한진택배
            'kr.lotte': '06',        # 롯데택배
            'kr.cupost': '08',       # CU 편의점택배
            'kr.epost': '09',        # 우체국택배
            'kr.kdexp': '10',        # 경동택배
            'kr.daesin': '11',       # 대신택배
            'kr.ilyang': '12',       # 일양로지스
            'kr.kunyoung': '13',     # 건영택배
            'kr.hdexp': '14',        # 합동택배
            'kr.cvsnet': '15',       # CVSnet 편의점택배
            'kr.dongbu': '16',       # 동부택배
            'kr.kglogis': '17',      # KG로지스
            'kr.inno': '18',         # 이노지스
            'kr.kdexp': '19',        # KGB택배
            'kr.slx': '20',          # SLX
            'kr.tnt': '21',          # TNT Express
            'kr.ups': '22',          # UPS
            'kr.fedex': '23',        # FedEx
            'kr.dhl': '24',          # DHL
        }

    def register_tracking(self, *, tracking_number: str, carrier: str, fid: str) -> None:
        """
        SweetTracker에 운송장 등록 (실제로는 조회만 가능)
        """
        logger.info(f"Registering tracking: {tracking_number} for carrier: {carrier}")
        # SweetTracker API는 등록 기능이 없고 조회만 가능
        # 실제 구현에서는 다른 서비스나 내부 시스템에 등록 정보를 저장할 수 있음
        pass

    def fetch_tracking(self, tracking_number: str, carrier: str = 'kr.cjlogistics') -> Dict[str, Any]:
        """
        SweetTracker API를 통해 실제 배송 정보 조회
        """
        if not self.api_key:
            logger.warning("SweetTracker API key not configured, returning dummy data")
            return self._get_dummy_data(tracking_number, carrier)
        
        carrier_code = self.carrier_code_map.get(carrier, '04')  # 기본값: CJ대한통운
        
        try:
            url = f"{self.base_url}/api/v1/trackingInfo"
            params = {
                't_key': self.api_key,
                't_code': carrier_code,
                't_invoice': tracking_number
            }
            
            logger.info(f"Fetching tracking info from SweetTracker: {url} with params: {params}")
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            logger.info(f"SweetTracker API response: {data}")
            
            return self._parse_sweettracker_response(data, tracking_number, carrier)
            
        except requests.exceptions.RequestException as e:
            logger.error(f"SweetTracker API request failed: {e}")
            return self._get_dummy_data(tracking_number, carrier)
        except Exception as e:
            logger.error(f"Error parsing SweetTracker response: {e}")
            return self._get_dummy_data(tracking_number, carrier)

    def _parse_sweettracker_response(self, data: Dict[str, Any], tracking_number: str, carrier: str) -> Dict[str, Any]:
        """
        SweetTracker API 응답을 내부 형식으로 변환
        """
        if not data.get('status'):
            logger.warning(f"Invalid response from SweetTracker: {data}")
            return self._get_dummy_data(tracking_number, carrier)
        
        # SweetTracker 응답 구조에 따라 파싱
        tracking_details = data.get('trackingDetails', [])
        events = []
        
        for detail in tracking_details:
            event = {
                "occurred_at": detail.get('timeString', ''),
                "status": self._map_sweettracker_status(detail.get('kind', '')),
                "location": detail.get('where', ''),
                "description": detail.get('telno', '') or detail.get('kind', ''),
            }
            events.append(event)
        
        return {
            "tracking_number": tracking_number,
            "carrier": carrier,
            "events": events,
            "raw_response": data  # 디버깅용
        }

    def _map_sweettracker_status(self, kind: str) -> str:
        """
        SweetTracker의 kind 값을 내부 상태로 매핑
        """
        status_map = {
            '집화': 'picked_up',
            '배송중': 'in_transit',
            '배송출발': 'out_for_delivery',
            '배달완료': 'delivered',
            '미배달': 'delivery_failed',
            '반송': 'returned',
            '취소': 'canceled',
        }
        return status_map.get(kind, 'in_transit')

    def _get_dummy_data(self, tracking_number: str, carrier: str) -> Dict[str, Any]:
        """
        API 키가 없거나 오류 발생 시 더미 데이터 반환
        """
        return {
            "tracking_number": tracking_number,
            "carrier": carrier,
            "events": [
                {
                    "occurred_at": timezone.now().isoformat(),
                    "status": "in_transit",
                    "location": "테스트HUB",
                    "description": "더미 데이터 (API 키 없음)",
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
