# domains/shipments/adapters/__init__.py
from .sweettracker import SweetTrackerAdapter

# 필요한 경우 여기서 다른 어댑터를 매핑해 주세요.
_ADAPTERS = {
    "kr.cjlogistics": SweetTrackerAdapter,
}


def get_adapter(carrier: str):
    """carrier 코드로 알맞은 어댑터 생성."""
    cls = _ADAPTERS.get((carrier or "").strip().lower(), SweetTrackerAdapter)
    return cls()


__all__ = ["get_adapter", "SweetTrackerAdapter"]
