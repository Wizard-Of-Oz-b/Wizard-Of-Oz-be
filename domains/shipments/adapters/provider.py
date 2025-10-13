from __future__ import annotations

from typing import Dict, Type

from .base import BaseAdapter

# 어댑터 레지스트리
_REGISTRY: Dict[str, Type[BaseAdapter]] = {}


def _norm(code: str) -> str:
    return (code or "").strip().lower().replace("-", "_").replace(" ", "")


# 흔한 별칭 → 표준 코드
_ALIASES = {
    "cj": "kr.cjlogistics",
    "cjlogistics": "kr.cjlogistics",
    "sweettracker": "kr.cjlogistics",  # 데모/중계사 명칭을 같은 어댑터로 묶기
}


def register_adapter(code: str, adapter_cls: Type[BaseAdapter]) -> None:
    """캐리어 코드(별칭 포함)에 어댑터 클래스를 등록."""
    _REGISTRY[_norm(code)] = adapter_cls


def get_adapter(code: str) -> BaseAdapter:
    """캐리어 코드/별칭으로 어댑터 인스턴스를 반환."""
    key = _norm(_ALIASES.get(_norm(code), code))
    cls = _REGISTRY.get(key)
    if not cls:
        raise ImportError(f"No adapter registered for carrier '{code}' (key='{key}')")
    return cls()
