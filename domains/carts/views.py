from __future__ import annotations

from django.shortcuts import get_object_or_404

from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from domains.catalog.models import Product

from .models import Cart, CartItem
from .serializers import (
    AddCartItemSerializer,
    CartItemSerializer,
    CartSerializer,
    UpdateCartItemSerializer,
    UpdateCartQtySerializer,
)
from .services import get_or_create_user_cart


def get_cart_item_prefetch_queryset():
    """장바구니 아이템 프리패치 쿼리셋 생성 (중복 코드 제거)"""
    qs = CartItem.objects.select_related("product")
    if hasattr(Product, "images"):
        qs = qs.prefetch_related("product__images")
    if hasattr(Product, "productimage_set"):
        qs = qs.prefetch_related("product__productimage_set")
    return qs


def get_cart_prefetch_queryset():
    """장바구니 프리패치 쿼리셋 생성 (중복 코드 제거)"""
    prefetches = ["items__product"]
    if hasattr(Product, "images"):
        prefetches.append("items__product__images")
    if hasattr(Product, "productimage_set"):
        prefetches.append("items__product__productimage_set")
    return prefetches


# ─────────────────────────────────────────────────────────────
# GET 내 카트 조회
# ─────────────────────────────────────────────────────────────
class MyCartView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = CartSerializer  # 응답 스키마 힌트

    @extend_schema(
        operation_id="GetMyCart",
        responses=CartSerializer,
        tags=["Carts"],
    )
    def get(self, request):
        """
        내 카트 조회.
        - N+1 방지: items -> product (및 product.images / productimage_set까지) prefetch
        - 이미지 절대 URL을 위해 serializer context에 request 전달
        """
        cart = get_or_create_user_cart(request.user)

        # Product에 images 또는 기본 productimage_set가 있으면 프리패치
        prefetches = get_cart_prefetch_queryset()

        cart = (
            Cart.objects.select_related("user")
            .prefetch_related(*prefetches)
            .get(pk=cart.pk)
        )
        return Response(CartSerializer(cart, context={"request": request}).data)


# ─────────────────────────────────────────────────────────────
# POST 장바구니에 상품 추가
# ─────────────────────────────────────────────────────────────
class CartItemAddView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = CartItemSerializer  # 응답의 형태(읽기용)

    @extend_schema(
        operation_id="AddCartItem",
        request=AddCartItemSerializer,  # 요청 스키마
        responses={201: CartItemSerializer},  # 응답 스키마
        tags=["Carts"],
    )
    def post(self, request):
        """
        장바구니에 상품 추가.
        - option_key 또는 options 중 하나만 사용(둘 다 비어있으면 '옵션 없음')
        - 테스트/클라이언트 호환: payload에 product_id만 있을 경우 product로 자동 매핑
        - 응답에서 image_url 절대경로를 위해 serializer context에 request 전달
        - N+1 방지를 위해 product(+images) 프리패치 후 반환
        """
        # 페이로드 정규화: product_id -> product (테스트 바디 호환)
        data = request.data.copy()
        if "product" not in data and "product_id" in data:
            data["product"] = data["product_id"]

        ser = AddCartItemSerializer(data=data, context={"request": request})
        ser.is_valid(raise_exception=True)
        item = ser.save()

        # 응답 시 N+1 방지를 위해 재조회(상품/이미지 프리패치)
        item = get_cart_item_prefetch_queryset().get(pk=item.pk)

        return Response(
            CartItemSerializer(item, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


# ─────────────────────────────────────────────────────────────
# PATCH 수량 변경
# ─────────────────────────────────────────────────────────────
class CartItemQuantityView(APIView):
    """
    PATCH /api/v1/carts/items/{item_id}/quantity
    body: { "quantity": <int>=1+ }
    """

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        operation_id="UpdateCartItemQuantity",
        request=UpdateCartQtySerializer,
        parameters=[
            OpenApiParameter(
                "item_id", OpenApiTypes.UUID, OpenApiParameter.PATH, required=True
            ),
        ],
        responses={200: CartItemSerializer, 400: dict, 404: dict},
        tags=["Carts"],
    )
    def patch(self, request, item_id):
        ser = UpdateCartQtySerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        qty = ser.validated_data["quantity"]

        item = get_object_or_404(CartItem, pk=item_id, cart__user=request.user)
        item.quantity = qty
        item.save(update_fields=["quantity"])

        # 최신 product/이미지 프리패치 후 반환
        item = get_cart_item_prefetch_queryset().get(pk=item.pk)

        return Response(
            CartItemSerializer(item, context={"request": request}).data, status=200
        )


# ─────────────────────────────────────────────────────────────
# PATCH 아이템 수량 + 옵션 변경 (item_id + option_key)
# ─────────────────────────────────────────────────────────────
class CartItemUpdateView(APIView):
    """
    PATCH /api/v1/carts/items/{item_id}/update
    body: { "quantity": <int>, "option_key": "<str>", "options": {} }
    """

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        operation_id="UpdateCartItemWithOptions",
        request=UpdateCartItemSerializer,
        parameters=[
            OpenApiParameter(
                "item_id", OpenApiTypes.UUID, OpenApiParameter.PATH, required=True
            ),
        ],
        responses={200: CartItemSerializer, 400: dict, 404: dict},
        tags=["Carts"],
    )
    def patch(self, request, item_id):
        """
        장바구니 아이템의 수량과 옵션을 함께 업데이트.
        """
        ser = UpdateCartItemSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        item = get_object_or_404(CartItem, pk=item_id, cart__user=request.user)

        # 수량 업데이트
        if "quantity" in ser.validated_data:
            item.quantity = ser.validated_data["quantity"]

        # 옵션 업데이트
        if "option_key" in ser.validated_data:
            item.option_key = ser.validated_data["option_key"]

        if "options" in ser.validated_data:
            item.options = ser.validated_data["options"]

        item.save()

        # 최신 product/이미지 프리패치 후 반환
        item = get_cart_item_prefetch_queryset().get(pk=item.pk)

        return Response(
            CartItemSerializer(item, context={"request": request}).data, status=200
        )


# ─────────────────────────────────────────────────────────────
# DELETE 상품 + 옵션키 조합으로 한 줄 삭제
# ─────────────────────────────────────────────────────────────
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
        responses={
            204: {"description": "아이템이 성공적으로 삭제됨"},
            400: {"description": "잘못된 요청 (option_key 누락 등)"},
            404: {"description": "해당 상품+옵션 조합의 아이템을 찾을 수 없음"},
        },
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
            return Response(
                {"detail": "option_key is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        deleted, _ = CartItem.objects.filter(
            cart__user=request.user,
            product_id=product_id,
            option_key=option_key,
        ).delete()

        if deleted == 0:
            return Response(
                {"detail": "item_not_found"}, status=status.HTTP_404_NOT_FOUND
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


# ─────────────────────────────────────────────────────────────
# DELETE item_id로 한 줄 삭제
# ─────────────────────────────────────────────────────────────
class CartItemDetailView(generics.DestroyAPIView):
    """
    DELETE /api/v1/carts/items/<item_id>/
    본인 장바구니의 해당 item_id 한 줄만 삭제
    """

    permission_classes = [permissions.IsAuthenticated]
    lookup_url_kwarg = "item_id"

    @extend_schema(
        operation_id="DeleteCartItemById",
        responses={204: None, 404: dict},
        tags=["Carts"],
    )
    def delete(self, request, *args, **kwargs):
        return super().delete(request, *args, **kwargs)

    def get_queryset(self):
        # 본인 소유 카트만
        return CartItem.objects.filter(cart__user=self.request.user)


# ─────────────────────────────────────────────────────────────
# DELETE 카트 전체 비우기
# ─────────────────────────────────────────────────────────────
class CartClearView(APIView):
    """
    DELETE /api/v1/carts/clear
    → 내 카트 전체 비우기
    """

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        operation_id="ClearMyCart",
        responses={204: None},
        tags=["Carts"],
    )
    def delete(self, request):
        cart = get_or_create_user_cart(request.user)
        cart.items.all().delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
