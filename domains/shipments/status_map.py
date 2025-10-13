from typing import Literal


def map_provider_status(
    provider_status: str,
) -> Literal[
    "pending", "in_transit", "out_for_delivery", "delivered", "exception", "canceled"
]:
    s = (provider_status or "").lower()
    if s in {"info_received", "accepted", "ready"}:
        return "pending"
    if s in {"in_transit", "transit", "arrived", "departed"}:
        return "in_transit"
    if s in {"out_for_delivery"}:
        return "out_for_delivery"
    if s in {"delivered"}:
        return "delivered"
    if s in {"failed", "exception", "returned"}:
        return "exception"
    if s in {"canceled", "cancelled"}:
        return "canceled"
    return "in_transit"
