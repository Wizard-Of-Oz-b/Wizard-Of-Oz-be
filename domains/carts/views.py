# domains/carts/views.py
from rest_framework import status, serializers
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


class CartItemDetailView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CartItemSerializer

    @extend_schema(
        operation_id="UpdateCartItem",
        parameters=[
            OpenApiParameter("item_id", OpenApiTypes.UUID, OpenApiParameter.PATH),  # urls가 <uuid:item_id> 라면 UUID, int면 INT
        ],
        request=UpdateCartQtySerializer,
        responses=CartItemSerializer,
        tags=["Carts"],
    )
    def patch(self, request, item_id):
        item = get_object_or_404(
            CartItem.objects.select_related("cart"),
            pk=item_id,
            cart__user=request.user,
        )
        ser = UpdateCartQtySerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        item.quantity = ser.validated_data["quantity"]
        item.save(update_fields=["quantity"])
        return Response(CartItemSerializer(item).data)

    @extend_schema(
        operation_id="DeleteCartItem",
        parameters=[OpenApiParameter("item_id", OpenApiTypes.UUID, OpenApiParameter.PATH)],
        responses={204: None},
        tags=["Carts"],
    )
    def delete(self, request, item_id):
        item = get_object_or_404(
            CartItem.objects.select_related("cart"),
            pk=item_id,
            cart__user=request.user,
        )
        item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
