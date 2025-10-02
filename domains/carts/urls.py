# domains/carts/urls.py
from django.urls import path

from .views import CartClearView  # ← 전체 비우기
from .views import CartItemQuantityView  # ← 수량 변경
from .views import CartItemUpdateView  # ← 수량 + 옵션 변경
from .views import (
    CartItemAddView,
    CartItemDeleteByProductOptionAPI,
    CartItemDetailView,
    MyCartView,
)

urlpatterns = [
    # 내 카트 조회
    path("me/", MyCartView.as_view(), name="cart-me"),
    # 아이템 추가
    path("items/", CartItemAddView.as_view(), name="cartitem-add"),
    # 아이템 단건 삭제 (item_id)
    path("items/<uuid:item_id>/", CartItemDetailView.as_view(), name="cartitem-detail"),
    # 아이템 수량 변경 (PATCH body: {"quantity": n})
    path(
        "items/<uuid:item_id>/quantity/",
        CartItemQuantityView.as_view(),
        name="cartitem-quantity",
    ),
    # 아이템 수량 + 옵션 변경 (PATCH body: {"quantity": n, "option_key": "str", "options": {}})
    path(
        "items/<uuid:item_id>/update/",
        CartItemUpdateView.as_view(),
        name="cartitem-update",
    ),
    # 상품+옵션키로 특정 라인 삭제 (옵션 없는 경우 option_key="")
    path(
        "items/by-product/<uuid:product_id>/",
        CartItemDeleteByProductOptionAPI.as_view(),
        name="cart-item-delete-by-product-option",
    ),
    # 카트 전체 비우기
    path("clear/", CartClearView.as_view(), name="cart-clear"),
]
