# domains/carts/views.py
from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework import status, serializers, permissions, generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes

from django.db.models import Prefetch

from .models import CartItem, Cart
from .serializers import CartSerializer, AddCartItemSerializer, CartItemSerializer
from .services import get_or_create_user_cart
from domains.catalog.models import Product


# PATCH 요청 바디 검증용(수량만 받음)
class UpdateCartQtySerializer(serializers.Serializer):
    quantity = serializers.IntegerField(min_value=1)


class MyCartView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CartSerializer  # ← 응답 스키마 힌트

    @extend_schema(
        operation_id="GetMyCart",
        responses=CartSerializer,
        tags=["Carts"],
    )
    def get(self, request):
        """
        내 카트 조회.
        - N+1 방지: items -> product (및 product.images가 있으면 이미지까지) prefetch
        """
        # 카트가 없으면 생성
        cart = get_or_create_user_cart(request.user)

        # Product에 images related_name이 있으면 prefetch에 포함
        prefetches = ["items__product"]
        if hasattr(Product, "images"):
            prefetches.append("items__product__images")

        # 프리패치된 상태로 다시 로드
        cart = (
            Cart.objects
            .select_related("user")
            .prefetch_related(*prefetches)
            .get(pk=cart.pk)
        )
        return Response(CartSerializer(cart).data)


class CartItemAddView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CartItemSerializer  # 응답의 형태

    @extend_schema(
        operation_id="AddCartItem",
        request=AddCartItemSerializer,          # ← 요청 스키마
        responses={201: CartItemSerializer},    # ← 응답 스키마
        tags=["Carts"],
    )
    def post(self, request):
        """
        장바구니에 상품 추가.
        - 응답에서 image_url을 올바르게 주기 위해 product(+images)까지 프리패치해서 반환
        """
        ser = AddCartItemSerializer(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)
        item = ser.save()

        # 응답 시 N+1 방지를 위해 재조회(상품/이미지 프리패치)
        qs = CartItem.objects.select_related("product")
        if hasattr(Product, "images"):
            qs = qs.prefetch_related("product__images")
        item = qs.get(pk=item.pk)

        return Response(CartItemSerializer(item).data, status=status.HTTP_201_CREATED)


class CartItemDeleteByProductOptionAPI(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        operation_id="DeleteCartItemByProductAndOption",
        parameters=[
            OpenApiParameter(
                name="product_id",
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.PATH,
                required=True,
                description="상품 ID (UUID)",
            ),
            OpenApiParameter(
                name="option_key",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                required=True,
                description="옵션키. 예) color=black&size=M (옵션 없는 상품은 빈 문자열 ''로 전달)",
            ),
        ],
        responses={204: None, 400: dict, 404: dict},
        tags=["Carts"],
    )
    def delete(self, request, product_id):
        """
        상품ID + option_key 조합으로 해당 라인만 삭제.
        (옵션 없는 상품은 option_key=""로 호출)
        """
        # 쿼리스트링 우선, 없으면 바디에서도 허용(프론트 편의)
        option_key = request.query_params.get("option_key")
        if option_key is None:
            option_key = (request.data or {}).get("option_key")

        if option_key is None:
            return Response({"detail": "option_key is required"}, status=status.HTTP_400_BAD_REQUEST)

        # 본인 장바구니에서만 삭제 가능
        qs = CartItem.objects.filter(
            cart__user=request.user,
            product_id=product_id,
            option_key=option_key,
        )

        deleted, _ = qs.delete()
        if deleted == 0:
            return Response({"detail": "item_not_found"}, status=status.HTTP_404_NOT_FOUND)

        return Response(status=status.HTTP_204_NO_CONTENT)


class CartItemDetailView(generics.DestroyAPIView):
    """
    DELETE /api/v1/carts/items/<item_id>/
    본인 장바구니의 해당 item_id 한 줄만 삭제
    """
    permission_classes = [permissions.IsAuthenticated]
    lookup_url_kwarg = "item_id"

    def get_queryset(self):
        # 본인 소유 카트만
        return CartItem.objects.filter(cart__user=self.request.user)
