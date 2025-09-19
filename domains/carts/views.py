# domains/carts/views.py
from rest_framework import status, serializers, permissions, generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes

from .models import CartItem
from .serializers import CartSerializer, AddCartItemSerializer, CartItemSerializer
from .services import get_or_create_user_cart


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
        cart = get_or_create_user_cart(request.user)
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
        ser = AddCartItemSerializer(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)
        item = ser.save()
        return Response(ser.to_representation(item), status=status.HTTP_201_CREATED)


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
    )
    def delete(self, request, product_id):
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
