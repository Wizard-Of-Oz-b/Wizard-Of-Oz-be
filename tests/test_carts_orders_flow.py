import pytest
from rest_framework.test import APIClient

@pytest.mark.django_db
def test_cart_to_checkout_flow(user_factory, product_factory, create_stock):
    user = user_factory()
    product = product_factory()
    create_stock(product, {"size": "M"}, 5)

    c = APIClient()
    c.force_authenticate(user=user)

    # 장바구니 담기
    r = c.post("/api/v1/carts/items/", {
        "product_id": str(product.id),
        "options": {"size": "M"},
        "quantity": 2
    }, format="json")
    assert r.status_code in (200, 201, 204)

    # 내 장바구니 조회 (비어있지 않아야 함)
    r = c.get("/api/v1/carts/me/")
    assert r.status_code == 200
    body = r.json()
    assert body.get("items") or body.get("results")

    # 체크아웃
    r = c.post("/api/v1/orders/checkout/")
    assert r.status_code in (200, 201)
    payload = r.json()

    # V1/V2 응답 포맷 모두 허용
    purchase_id = payload.get("id") or payload.get("purchase_id") or payload.get("order_id")
    assert purchase_id

    # 체크아웃 후 카트는 비어야 함
    after = c.get("/api/v1/carts/me/")
    assert after.status_code == 200
    after_body = after.json()
    assert len(after_body.get("items") or after_body.get("results") or []) == 0

    # 응답 본문에 product id가 포함돼 있으면(아이템을 포함하는 구현) 검증
    if isinstance(payload, dict):
        assert str(product.id) in str(payload)
