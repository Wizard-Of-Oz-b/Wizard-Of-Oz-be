import pytest
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_wishlist_add_and_move_to_cart(user_factory, product_factory, create_stock):
    user = user_factory()
    product = product_factory()
    create_stock(product, {"size": "S"}, 3)

    c = APIClient()
    c.force_authenticate(user=user)

    # 위시리스트 추가
    r = c.post(
        "/api/v1/wishlist/items/",
        {"product_id": str(product.id), "options": {"size": "S"}},
        format="json",
    )

    assert r.status_code in (200, 201), r.content
    wid = r.json().get("wishlist_id")

    # 장바구니로 이동
    r = c.post(f"/api/v1/wishlist/items/{wid}/move-to-cart/")
    assert r.status_code in (200, 201, 204), r.content

    # 장바구니 확인
    r = c.get("/api/v1/carts/me/")
    assert r.status_code == 200
    j = r.json()
    text = str(j)
    assert "items" in text or "results" in text
