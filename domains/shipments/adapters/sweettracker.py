from typing import Any, Dict, List


class SweetTrackerAdapter:
    """
    외부 배송추적 제공자와의 경계. 실제 HTTP 호출은 추후 주입.
    최소 인터페이스만 맞춘 더미 구현.
    """

    def register_tracking(self, *, tracking_number: str, carrier: str, fid: str) -> None:
        payload = {
            "tracking_number": tracking_number,
            "carrier_code": carrier,   # ✅ 여기서만 이름 변환
            "fid": fid,
        }

    def parse_events(self, raw: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        제공자 웹훅(raw) → 내부 통일 스키마로 변환
        내부 스키마 필수키:
          - dedupe_key (str, unique)
          - level (int)
          - where (str)
          - details (str)
          - time_trans (datetime | None)
          - time_sweet (str)
          - telno_office (str)
          - telno_man (str)
          - comcode (str)
        """
        events = raw.get("events") or []
        out: List[Dict[str, Any]] = []
        for e in events:
            dedupe_key = (
                str(e.get("id"))
                or f"{raw.get('tracking_number','')}-{e.get('time')}-{e.get('status')}"
            )
            out.append(
                {
                    "dedupe_key": dedupe_key,
                    "level": int(e.get("level", 0)),
                    "where": e.get("location", "") or e.get("where", ""),
                    "details": e.get("description", "") or e.get("details", ""),
                    "time_trans": e.get("time_trans"),  # 미리 파싱되어 올 수도, 아니면 None
                    "time_sweet": e.get("time", ""),
                    "telno_office": e.get("tel_office", "") or e.get("office_tel", ""),
                    "telno_man": e.get("tel_man", "") or e.get("man_tel", ""),
                    "comcode": e.get("carrier_code", "") or raw.get("carrier_code", ""),
                }
            )
        return out
