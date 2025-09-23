# domains/orders/views.py
from __future__ import annotations

import django_filters as df
from django.db import transaction
from django_filters.rest_framework import DjangoFilterBackend

from rest_framework import generics, permissions, status, views
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError

from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes

from domains.orders.models import Purchase, OrderItem
from .serializers import (
    PurchaseReadSerializer,
    PurchaseWriteSerializer,
    OrderItemReadSerializer,   # ✅ OrderItem 조회용
)
from shared.permissions import IsOwnerOrAdmin
from shared.pagination import StandardResultsSetPagination

from domains.carts.services import get_user_cart
from domains.orders.utils import parse_option_key_safe
from .services import (
    cancel_purchase,
    refund_purchase,
    checkout_user_cart,  # ✅ 기존: 카트 → Purchase 다건
)
from .services import checkout, EmptyCartError  # ✅ 신규: 헤더+결제 스텁


# -------------------------------
# Filters (admin listing)
# -------------------------------
class PurchaseFilter(df.FilterSet):
    status = df.CharFilter()
    user_id = df.UUIDFilter(field_name="user_id")
    product_id = df.UUIDFilter(field_name="product_id")
    date_from = df.IsoDateTimeFilter(field_name="purchased_at", lookup_expr="gte")
    date_to = df.IsoDateTimeFilter(field_name="purchased_at", lookup_expr="lte")

    class Meta:
        model = Purchase
        fields = ["status", "user_id", "product_id", "date_from", "date_to"]


# -------------------------------
# GET (admin list) / POST (create)
# -------------------------------
class PurchaseListCreateAPI(generics.ListCreateAPIView):
    """
    GET  /api/v1/purchases        (관리자만, 필터/정렬/페이징)
    POST /api/v1/purchases        (로그인 필요, 결제 성공으로 간주하여 구매 생성)
    """
    queryset = Purchase.objects.all().order_by("-purchased_at")
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = PurchaseFilter
    ordering_fields = ["purchased_at", "amount"]
    pagination_class = StandardResultsSetPagination

    def get_permissions(self):
        return (
            [permissions.IsAdminUser()]
            if self.request.method == "GET"
            else [permissions.IsAuthenticated()]
        )

    def get_serializer_class(self):
        return PurchaseWriteSerializer if self.request.method == "POST" else PurchaseReadSerializer

    @extend_schema(operation_id="ListPurchases")
    def get(self, *args, **kwargs):
        return super().get(*args, **kwargs)

    @transaction.atomic
    @extend_schema(
        operation_id="CreatePurchase",
        request=PurchaseWriteSerializer,
        responses={201: PurchaseReadSerializer},
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user, status=Purchase.STATUS_PAID)


# -------------------------------
# POST-only create (separate endpoint)
# -------------------------------
class PurchaseCreateAPI(generics.CreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = PurchaseWriteSerializer
    queryset = Purchase.objects.none()

    @transaction.atomic
    @extend_schema(
        operation_id="CreatePurchaseOnly",
        request=PurchaseWriteSerializer,
        responses={201: PurchaseReadSerializer},
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user, status=Purchase.STATUS_PAID)


# -------------------------------
# My purchases (list)
# -------------------------------
class PurchaseMeListAPI(generics.ListAPIView):
    """GET /api/v1/purchases/me"""
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = PurchaseReadSerializer
    pagination_class = StandardResultsSetPagination
    queryset = Purchase.objects.none()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False) or not self.request.user.is_authenticated:
            return Purchase.objects.none()
        return Purchase.objects.filter(user_id=self.request.user.id).order_by("-purchased_at")


# -------------------------------
# Detail
# -------------------------------
class PurchaseDetailAPI(generics.RetrieveAPIView):
    """GET /api/v1/purchases/{purchase_id}"""
    lookup_url_kwarg = "purchase_id"
    queryset = Purchase.objects.all()
    permission_classes = [IsOwnerOrAdmin]
    serializer_class = PurchaseReadSerializer


# -------------------------------
# Status transitions (with stock restore)
# -------------------------------
class PurchaseCancelAPI(generics.UpdateAPIView):
    lookup_url_kwarg = "purchase_id"
    queryset = Purchase.objects.all()
    permission_classes = [IsOwnerOrAdmin]
    serializer_class = PurchaseReadSerializer
    http_method_names = ["patch", "options", "head"]

    @extend_schema(
        tags=["Orders"],
        summary="주문 취소",
        request=None,                                      # ✅ 바디 없음
        responses={200: PurchaseReadSerializer},
        operation_id="PurchaseCancel",
    )
    @transaction.atomic
    def patch(self, request, *args, **kwargs):
        obj = self.get_object()
        if obj.status != Purchase.STATUS_PAID:
            return Response(
                {"detail": "only paid can be canceled"},
                status=status.HTTP_409_CONFLICT,
            )
        obj = cancel_purchase(obj)                         # 재고 복원 포함
        data = self.get_serializer(obj).data
        return Response(data, status=status.HTTP_200_OK)


class PurchaseRefundAPI(generics.UpdateAPIView):
    lookup_url_kwarg = "purchase_id"
    queryset = Purchase.objects.all()
    permission_classes = [permissions.IsAdminUser]         # ✅ 관리자만
    serializer_class = PurchaseReadSerializer
    http_method_names = ["patch", "options", "head"]

    @extend_schema(
        tags=["Orders"],
        summary="주문 환불",
        request=None,                                      # ✅ 바디 없음
        responses={200: PurchaseReadSerializer},
        operation_id="PurchaseRefund",
    )
    @transaction.atomic
    def patch(self, request, *args, **kwargs):
        obj = self.get_object()
        if obj.status == Purchase.STATUS_REFUNDED:
            return Response(
                {"detail": "already refunded"},
                status=status.HTTP_409_CONFLICT,
            )
        obj = refund_purchase(obj)                         # 재고 복원 포함
        data = self.get_serializer(obj).data
        return Response(data, status=status.HTTP_200_OK)


# -------------------------------
# Checkout (Cart -> Purchases) [구버전: 다건 Purchase]
# -------------------------------
class CheckoutView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Orders"],
        summary="체크아웃 (요청 바디 없음)",
        request=None,                              # Swagger에서 바디 입력 제거
        responses={201: OpenApiTypes.OBJECT},      # 간단 객체 응답
        description="장바구니의 모든 상품을 주문으로 생성합니다. 장바구니가 비어있으면 400을 반환합니다.",
        operation_id="Checkout",
    )
    def post(self, request):
        # 1) 장바구니 존재/비어있음 체크
        cart = get_user_cart(request.user, create=False)
        if not cart or not cart.items.exists():
            raise ValidationError({"cart": "장바구니가 비어 있습니다."})

        # 2) option_key 형식 안전성 검증(문자열인 경우 파싱)
        for ci in cart.items.select_related("product"):
            if ci.option_key:
                opts = parse_option_key_safe(ci.option_key)
                if not opts:
                    raise ValidationError({"option_key": f"옵션 형식이 잘못되었습니다: {ci.option_key}"})

        # 3) 실제 체크아웃 실행 (구매 생성 + 재고 차감 + 장바구니 비우기)
        purchases = checkout_user_cart(request.user, clear_cart=True)

        # 4) 응답(필요하면 purchases를 직렬화해서 더 자세히 반환해도 됨)
        return Response(
            {
                "count": len(purchases),
                "purchase_ids": [str(p.pk) for p in purchases],
                "detail": "주문이 생성되었고 장바구니가 비워졌습니다.",
            },
            status=status.HTTP_201_CREATED,
        )


# -------------------------------
# Checkout (Cart -> Order header + Payment stub) [신버전]
# -------------------------------
class CheckoutAPI(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Orders"],
        summary="체크아웃(헤더+결제 스텁)",
        request=None,
        responses={201: OpenApiTypes.OBJECT},
        operation_id="CheckoutV2",
        description="장바구니 합계로 주문 헤더를 만들고 결제 스텁을 생성합니다.",
    )
    def post(self, request):
        try:
            order, payment = checkout(request.user)
        except EmptyCartError as e:
            # 장바구니 없음 / 비어있음 -> 400
            return Response(e.detail, status=e.status_code)

        return Response(
            {
                # 프론트 호환을 위해 key는 order_id 유지, 값은 purchase_id 매핑
                "order_id": str(order.purchase_id),
                "purchase_id": str(order.purchase_id),
                "payment_id": str(payment.payment_id),
                "order_number": payment.order_number,   # = purchase_id 문자열
                "amount": str(payment.amount_total),
                "status": order.status,
            },
            status=status.HTTP_201_CREATED,
        )


# ======================================================================
# OrderItem 조회 API (신규)
# ======================================================================
class OrderItemListAPI(generics.ListAPIView):
    """
    GET /api/v1/orders/purchases/{purchase_id}/items/
    - 본인 주문만 조회 가능(관리자는 전체)
    - 필터: product_id, option_key
    """
    serializer_class = OrderItemReadSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        purchase_id = self.kwargs["purchase_id"]
        qs = OrderItem.objects.select_related("order", "product").filter(order__purchase_id=purchase_id)
        # 본인 주문만
        if not self.request.user.is_staff:
            qs = qs.filter(order__user=self.request.user)
        # 간단 필터
        product_id = self.request.query_params.get("product_id")
        if product_id:
            qs = qs.filter(product_id=product_id)
        option_key = self.request.query_params.get("option_key")
        if option_key is not None:
            qs = qs.filter(option_key=option_key)
        return qs.order_by("created_at")

    @extend_schema(
        operation_id="ListOrderItemsByOrder",
        parameters=[
            OpenApiParameter("product_id", OpenApiTypes.STR, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("option_key", OpenApiTypes.STR, OpenApiParameter.QUERY, required=False),
        ],
        responses={200: OrderItemReadSerializer(many=True)},
    )
    def get(self, *args, **kwargs):
        return super().get(*args, **kwargs)


class _IsOwnerOrAdmin(permissions.BasePermission):
    """
    - Admin: 항상 허용
    - 일반 유저: 자신의 주문(Order.purchase_id)의 아이템만 허용
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj: OrderItem):
        if request.user.is_staff:
            return True
        return getattr(obj.order, "user_id", None) == getattr(request.user, "id", None)


class OrderItemDetailAPI(generics.RetrieveAPIView):
    """
    GET /api/v1/orders/order-items/{item_id}/
    """
    lookup_url_kwarg = "item_id"
    serializer_class = OrderItemReadSerializer
    permission_classes = [_IsOwnerOrAdmin]

    def get_queryset(self):
        qs = OrderItem.objects.select_related("order", "product").all()
        if not self.request.user.is_staff:
            qs = qs.filter(order__user=self.request.user)
        return qs

    @extend_schema(operation_id="RetrieveOrderItem", responses={200: OrderItemReadSerializer})
    def get(self, *args, **kwargs):
        return super().get(*args, **kwargs)
