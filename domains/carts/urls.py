# domains/carts/urls.py
from django.urls import path
from .views import (
    MyCartView,
    CartItemAddView,
    CartItemDeleteByProductOptionAPI,
    CartItemDetailView,
    CartItemQuantityView,   # ← 수량 변경
    CartClearView,          # ← 전체 비우기
)

urlpatterns = [
    # 내 카트 조회
    path("me/", MyCartView.as_view(), name="cart-me"),

    # 아이템 추가
    path("items/", CartItemAddView.as_view(), name="cartitem-add"),

    # 아이템 단건 삭제 (item_id)
    path("items/<uuid:item_id>/", CartItemDetailView.as_view(), name="cartitem-detail"),

    # 아이템 수량 변경 (PATCH body: {"quantity": n})
    path("items/<uuid:item_id>/quantity/", CartItemQuantityView.as_view(), name="cartitem-quantity"),

    # 상품+옵션키로 특정 라인 삭제 (옵션 없는 경우 option_key="")
    path(
        "items/by-product/<uuid:product_id>/",
        CartItemDeleteByProductOptionAPI.as_view(),
        name="cart-item-delete-by-product-option",
    ),

    # 카트 전체 비우기
    path("clear/", CartClearView.as_view(), name="cart-clear"),
]
