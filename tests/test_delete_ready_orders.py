"""
Delete-ready 엔드포인트 테스트 - Soft delete 검증
"""

import pytest
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_delete_ready_order_soft_delete(user_factory, product_factory, create_stock):
    """
    Delete-ready로 주문 삭제 후:
    1. 주문 상태가 'deleted'로 변경되어야 함
    2. purchases/me 조회 시 삭제된 주문은 보이지 않아야 함
    3. 주문 데이터는 DB에 남아있어야 함 (soft delete)
    """
    user = user_factory()
    product = product_factory(name="테스트상품")
    create_stock(product, "", 10)

    client = APIClient()
    client.force_authenticate(user=user)

    # 1. 장바구니에 상품 추가
    response = client.post(
        "/api/v1/carts/items/",
        {"product": str(product.id), "options": {}, "quantity": 2},
        format="json",
    )
    assert response.status_code in (200, 201)

    # 2. 체크아웃 (ready 상태 주문 생성)
    response = client.post("/api/v1/orders/checkout/")
    assert response.status_code == 201

    order_data = response.json()
    order_id = order_data.get("order_id") or order_data.get("purchase_id")
    assert order_id

    # 3. purchases/me 조회 - 주문이 보여야 함
    response = client.get("/api/v1/orders/purchases/me/")
    assert response.status_code == 200
    data = response.json()
    results = data.get("results", data)

    # 주문이 목록에 있는지 확인
    order_ids = [str(o["purchase_id"]) for o in results]
    assert order_id in order_ids

    # 4. delete-ready로 주문 삭제
    response = client.post(
        "/api/v1/orders/delete-ready/",
        {"order_ids": [order_id]},
        format="json",
    )
    assert response.status_code in (200, 201, 204)

    # 5. purchases/me 조회 - 삭제된 주문은 보이지 않아야 함
    response = client.get("/api/v1/orders/purchases/me/")
    assert response.status_code == 200
    data = response.json()
    results = data.get("results", data)

    order_ids = [str(o["purchase_id"]) for o in results]
    assert order_id not in order_ids, "삭제된 주문이 여전히 조회됩니다"

    # 6. DB에서 주문 데이터가 삭제되지 않고 상태만 변경되었는지 확인
    from domains.orders.models import Purchase

    deleted_order = Purchase.objects.filter(purchase_id=order_id).first()
    assert deleted_order is not None, "주문이 완전히 삭제되었습니다 (hard delete)"
    assert (
        deleted_order.status == "deleted"
    ), f"주문 상태가 'deleted'가 아닙니다: {deleted_order.status}"

    # 7. OrderItem도 삭제되지 않고 남아있어야 함
    from domains.orders.models import OrderItem

    order_items = OrderItem.objects.filter(order=deleted_order)
    assert order_items.exists(), "OrderItem이 삭제되었습니다"


@pytest.mark.django_db
def test_delete_ready_order_restores_stock(user_factory, product_factory, create_stock):
    """Delete-ready 시 재고가 복구되어야 함"""
    user = user_factory()
    product = product_factory(name="재고테스트상품")
    create_stock(product, "", 10)

    client = APIClient()
    client.force_authenticate(user=user)

    # 초기 재고 확인
    from domains.catalog.models import ProductStock

    stock_before = ProductStock.objects.get(product=product, option_key="")
    assert stock_before.stock_quantity == 10

    # 장바구니에 상품 3개 추가 후 체크아웃
    client.post(
        "/api/v1/carts/items/",
        {"product": str(product.id), "options": {}, "quantity": 3},
        format="json",
    )
    response = client.post("/api/v1/orders/checkout/")
    assert response.status_code == 201

    order_data = response.json()
    order_id = order_data.get("order_id") or order_data.get("purchase_id")

    # 체크아웃 후 재고 확인 (10 - 3 = 7)
    stock_before.refresh_from_db()
    assert stock_before.stock_quantity == 7

    # delete-ready로 주문 삭제
    response = client.post(
        "/api/v1/orders/delete-ready/",
        {"order_ids": [order_id]},
        format="json",
    )
    assert response.status_code in (200, 201, 204)

    # 재고가 복구되었는지 확인 (7 + 3 = 10)
    stock_before.refresh_from_db()
    assert (
        stock_before.stock_quantity == 10
    ), f"재고가 복구되지 않았습니다: {stock_before.stock_quantity}"


@pytest.mark.django_db
def test_cannot_delete_paid_order(user_factory, product_factory, create_stock):
    """PAID 상태 주문은 delete-ready로 삭제할 수 없어야 함"""
    user = user_factory()
    product = product_factory(name="결제완료상품")
    create_stock(product, "", 10)

    client = APIClient()
    client.force_authenticate(user=user)

    # PAID 상태 주문 생성
    import uuid

    from domains.orders.models import Purchase

    order = Purchase.objects.create(
        user=user,
        status=Purchase.STATUS_PAID,
        items_total=10000,
        grand_total=10000,
    )

    # delete-ready 시도 - 실패해야 함
    response = client.post(
        "/api/v1/orders/delete-ready/",
        {"order_ids": [str(order.purchase_id)]},
        format="json",
    )
    assert response.status_code == 400, "PAID 상태 주문을 삭제할 수 있습니다"

    # 주문이 그대로 남아있어야 함
    order.refresh_from_db()
    assert order.status == Purchase.STATUS_PAID
