import pytest
from rest_framework.test import APIClient

from domains.orders.models import Purchase


def _extract_items_and_meta(body):
    """
    지원 케이스:
    A) {"items":[...], "avg_rating": 5.0, "count": 1}
    A'={"items":{"count":...,"next":...,"previous":...,"results":[...]}, "avg_rating":..., "count": ...}
    B) {"count":...,"next":...,"previous":...,"results":[...]}
    C) [ ... ]  # 리스트 그대로
    """
    avg = None
    cnt = None
    items = []

    if isinstance(body, dict):
        # A 또는 A'
        if "items" in body:
            maybe = body["items"]
            avg = body.get("avg_rating")
            cnt = body.get("count")
            if isinstance(maybe, dict) and "results" in maybe:  # A'
                items = maybe["results"]
                cnt = cnt if cnt is not None else maybe.get("count")
            elif isinstance(maybe, list):  # A
                items = maybe
                cnt = cnt if cnt is not None else len(items)
        # B
        elif "results" in body:
            items = body["results"]
            cnt = body.get("count", len(items))
            avg = body.get("avg_rating")  # 혹시 제공되면 사용
    elif isinstance(body, list):  # C
        items = body
        cnt = len(items)

    return items, cnt, avg


@pytest.mark.django_db
def test_purchase_then_review(user, product, create_stock):
    # 재고 준비
    create_stock(product, {"size": "M"}, 3)

    # 유료구매 이력 주입 → 구매자 조건 충족
    Purchase.objects.create(
        user=user, product_id=product.id, status=Purchase.STATUS_PAID
    )

    c = APIClient()
    c.force_authenticate(user=user)

    # 리뷰 작성 (끝 슬래시!)
    r = c.post(
        f"/api/v1/products/{product.id}/reviews/",
        {"rating": 5, "content": "좋아요!"},
        format="json",
    )
    assert r.status_code in (200, 201), getattr(r, "data", r.content)

    # 리뷰 목록
    r = c.get(f"/api/v1/products/{product.id}/reviews/?size=50")
    assert r.status_code == 200, getattr(r, "data", r.content)

    body = r.json()
    items, cnt, avg = _extract_items_and_meta(body)

    assert (cnt or 0) >= 1
    assert any((isinstance(it, dict) and it.get("rating") == 5) for it in items)

    if avg is not None:
        assert round(float(avg), 2) == 5.0
