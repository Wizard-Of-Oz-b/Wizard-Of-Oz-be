# domains/orders/views.py
from __future__ import annotations

import django_filters as df
from django.db import transaction
from django_filters.rest_framework import DjangoFilterBackend

from rest_framework import generics, permissions, status
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError

from drf_spectacular.utils import extend_schema
from drf_spectacular.types import OpenApiTypes

from domains.orders.models import Purchase
from .serializers import PurchaseReadSerializer, PurchaseWriteSerializer
from shared.permissions import IsOwnerOrAdmin
from shared.pagination import StandardResultsSetPagination

from domains.carts.services import get_user_cart
from domains.orders.utils import parse_option_key_safe
from .services import (
    cancel_purchase,
    refund_purchase,
    checkout_user_cart,  # ✅ 추가: 실제 체크아웃 로직 호출
)

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
        data = self.get_serializer(obj).data               # ✅ 컨텍스트 포함 직렬화
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
# Checkout (Cart -> Purchases)
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