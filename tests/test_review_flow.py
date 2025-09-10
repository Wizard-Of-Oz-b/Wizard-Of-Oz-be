# tests/test_review_flow.py
import pytest
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_purchase_then_review(user_factory, product_factory):
    user = user_factory()                  # 활성 유저 1명
    product = product_factory()            # 상품 1개

    c = APIClient()
    # JWT 대신 테스트용으로 인증을 강제로 붙임
    c.force_authenticate(user)

    # 1) 구매 생성
    r = c.post("/api/v1/purchases", {"product_id": product.pk, "amount": 1}, format="json")
    assert r.status_code == 201

    # 2) 리뷰 작성(구매자만)
    r = c.post(f"/api/v1/products/{product.pk}/reviews", {"rating": 5, "content": "좋아요!"}, format="json")
    assert r.status_code == 201

    # 3) 리뷰 목록 확인(집계 포함)
    r = c.get(f"/api/v1/products/{product.pk}/reviews")
    assert r.status_code == 200
    assert r.data["count"] == 1
