"""
재고 없는 상품이 장바구니에 있을 때 checkout 테스트
"""
import pytest
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_checkout_with_out_of_stock_product(user_factory, product_factory, create_stock):
    """재고가 없는 상품이 장바구니에 있을 때 checkout 시 409 에러 반환"""
    user = user_factory()
    product = product_factory(name="품절상품")
    
    # 재고 0으로 설정
    create_stock(product, "", 0)
    
    client = APIClient()
    client.force_authenticate(user=user)
    
    # 장바구니에 상품 추가 (수량 1)
    response = client.post(
        "/api/v1/carts/items/",
        {"product": str(product.id), "options": {}, "quantity": 1},
        format="json",
    )
    assert response.status_code in (200, 201)
    
    # 체크아웃 시도 - 409 에러 기대
    response = client.post("/api/v1/orders/checkout/")
    assert response.status_code == 409, f"Expected 409, got {response.status_code}: {response.json()}"
    
    data = response.json()
    assert "detail" in data
    assert "재고" in data["detail"]


@pytest.mark.django_db
def test_checkout_with_insufficient_stock(user_factory, product_factory, create_stock):
    """장바구니 수량보다 재고가 적을 때 checkout 시 409 에러 반환"""
    user = user_factory()
    product = product_factory(name="재고부족상품")
    
    # 재고 2개만 설정
    create_stock(product, "", 2)
    
    client = APIClient()
    client.force_authenticate(user=user)
    
    # 장바구니에 상품 5개 추가
    response = client.post(
        "/api/v1/carts/items/",
        {"product": str(product.id), "options": {}, "quantity": 5},
        format="json",
    )
    assert response.status_code in (200, 201)
    
    # 체크아웃 시도 - 409 에러 기대
    response = client.post("/api/v1/orders/checkout/")
    assert response.status_code == 409, f"Expected 409, got {response.status_code}: {response.json()}"
    
    data = response.json()
    assert "detail" in data
    assert "재고" in data["detail"]


@pytest.mark.django_db
def test_checkout_with_sufficient_stock_success(user_factory, product_factory, create_stock):
    """재고가 충분할 때 checkout 성공"""
    user = user_factory()
    product = product_factory(name="정상상품")
    
    # 재고 충분하게 설정
    create_stock(product, "", 10)
    
    client = APIClient()
    client.force_authenticate(user=user)
    
    # 장바구니에 상품 3개 추가
    response = client.post(
        "/api/v1/carts/items/",
        {"product": str(product.id), "options": {}, "quantity": 3},
        format="json",
    )
    assert response.status_code in (200, 201)
    
    # 체크아웃 시도 - 성공 기대
    response = client.post("/api/v1/orders/checkout/")
    assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.json()}"
    
    data = response.json()
    assert "id" in data or "purchase_id" in data

