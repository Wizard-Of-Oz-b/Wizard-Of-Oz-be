from __future__ import annotations

import base64
import os
from decimal import Decimal

from django.conf import settings

import requests

TOSS_API_BASE = "https://api.tosspayments.com"


def _auth_header() -> dict:
    secret = settings.TOSS_SECRET_KEY or ""
    token = base64.b64encode(f"{secret}:".encode("utf-8")).decode("utf-8")
    return {"Authorization": f"Basic {token}", "Content-Type": "application/json"}


def _to_int_amount(v) -> int:
    # Decimal/str/float/int 모두 안전하게 정수 KRW로
    return int(Decimal(str(v)))


def _mock_enabled() -> bool:
    # 로컬/샌드박스에서 네트워크 없이 테스트하고 싶을 때
    return os.getenv("TOSS_MOCK", "0") == "1" or (
        getattr(settings, "DEBUG", False)
        and str(getattr(settings, "TOSS_SECRET_KEY", "")).startswith("test_sk_")
        and os.getenv("TOSS_FORCE_LIVE", "0") != "1"
    )


def confirm(payment_key: str, order_id: str, amount) -> dict:
    if _mock_enabled():
        return {
            "paymentKey": payment_key,
            "orderId": order_id,
            "totalAmount": _to_int_amount(amount),
            "status": "DONE",
            "method": "CARD",
            "receipt": {"url": "https://example.local/receipt"},
            "card": {"company": "Mock", "number": "****-****-****-1234"},
        }
    url = f"{TOSS_API_BASE}/v1/payments/confirm"
    body = {
        "paymentKey": str(payment_key),
        "orderId": str(order_id),
        "amount": _to_int_amount(amount),
    }
    res = requests.post(url, headers=_auth_header(), json=body, timeout=10)
    res.raise_for_status()
    return res.json()


def retrieve_by_key(payment_key: str) -> dict:
    if _mock_enabled():
        return {"status": "DONE"}
    url = f"{TOSS_API_BASE}/v1/payments/{payment_key}"
    res = requests.get(url, headers=_auth_header(), timeout=10)
    res.raise_for_status()
    return res.json()


def cancel(payment_key: str, amount, reason: str, tax_free_amount=0) -> dict:
    if _mock_enabled():
        return {"status": "CANCELED" if _to_int_amount(amount) else "PARTIAL_CANCELED"}
    url = f"{TOSS_API_BASE}/v1/payments/{payment_key}/cancel"
    body = {
        "cancelReason": reason or "cancel",
        "cancelAmount": _to_int_amount(amount),
        "taxFreeAmount": _to_int_amount(tax_free_amount),
    }
    res = requests.post(url, headers=_auth_header(), json=body, timeout=10)
    res.raise_for_status()
    return res.json()
