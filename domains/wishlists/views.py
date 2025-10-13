from django.db import transaction

from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework import filters, mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

# carts 쪽 의존
from domains.carts.models import CartItem
from domains.carts.serializers import CartItemSerializer  # 이미 있는 시리얼라이저
from domains.carts.services import get_or_create_user_cart
from domains.wishlists.models import WishlistItem

from .serializers import (
    MoveToCartRequestSerializer,
    WishlistItemReadSerializer,
    WishlistItemWriteSerializer,
)


class MyWishlistViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    search_fields = ["product__name", "product__description"]
    ordering_fields = ["created_at", "product__price"]

    def get_queryset(self):
        return (
            WishlistItem.objects.filter(user=self.request.user)
            .select_related("product")
            .prefetch_related("product__images")
            .order_by("-created_at")
        )

    def get_serializer_class(self):
        return (
            WishlistItemWriteSerializer
            if self.action == "create"
            else WishlistItemReadSerializer
        )

    @extend_schema(
        request=MoveToCartRequestSerializer,
        responses=CartItemSerializer,
        examples=[
            OpenApiExample(
                "기본 사용",
                value={"quantity": 1, "remove_from_wishlist": True},
                request_only=True,
            )
        ],
    )
    @action(detail=True, methods=["post"], url_path="move-to-cart")
    @transaction.atomic
    def move_to_cart(self, request, pk=None):
        item = self.get_object()  # wishlist item (현재 유저로 제한된 queryset에서)

        s = MoveToCartRequestSerializer(data=request.data or {})
        s.is_valid(raise_exception=True)
        qty = s.validated_data["quantity"]
        do_remove = s.validated_data["remove_from_wishlist"]

        cart = get_or_create_user_cart(request.user)

        # ★ unit_price 반드시 채우기 (상품 현재 가격 스냅샷)
        product_price = item.product.price

        cart_item, created = CartItem.objects.select_for_update().get_or_create(
            cart=cart,
            product=item.product,
            option_key=item.option_key or "",
            defaults={
                "quantity": qty,
                "options": item.options or {},
                "unit_price": product_price,  # ← 여기 추가
            },
        )

        if not created:
            # 수량 누적
            cart_item.quantity = cart_item.quantity + qty
            # 옵션 최신화(선택)
            if item.options:
                cart_item.options = item.options
            # ★ 혹시 과거 데이터가 unit_price=None이면 채워두기
            if getattr(cart_item, "unit_price", None) is None:
                cart_item.unit_price = product_price
            cart_item.save(
                update_fields=["quantity", "options", "unit_price", "updated_at"]
            )

        if do_remove:
            item.delete()

        return Response(
            CartItemSerializer(cart_item, context={"request": request}).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )
