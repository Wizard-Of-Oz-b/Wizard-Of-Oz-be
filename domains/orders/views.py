# domains/orders/views.py
from __future__ import annotations
from drf_spectacular.utils import extend_schema
from .serializers import PurchaseReadSerializer
import django_filters as df
from django.db import transaction
from django.core.exceptions import ValidationError

from rest_framework import generics, permissions, status
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema

from domains.orders.models import Purchase
from .serializers import PurchaseReadSerializer, PurchaseWriteSerializer
from shared.permissions import IsOwnerOrAdmin
from shared.pagination import StandardResultsSetPagination

from .services import (
    checkout_user_cart,
    cancel_purchase,
    refund_purchase,
)

# -------------------------------
# Filters (admin listing)
# -------------------------------
class PurchaseFilter(df.FilterSet):
    status = df.CharFilter()
    # UUID 기반 필터
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
    queryset = Purchase.objects.none()  # schema-safe

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
    """
    PATCH /api/v1/purchases/{purchase_id}/cancel  (소유자/관리자, paid -> canceled)
    """
    lookup_url_kwarg = "purchase_id"
    queryset = Purchase.objects.all()
    permission_classes = [IsOwnerOrAdmin]
    serializer_class = PurchaseReadSerializer
    http_method_names = ["patch", "options", "head"]

    @transaction.atomic
    def patch(self, request, *args, **kwargs):
        obj = self.get_object()
        if obj.status != Purchase.STATUS_PAID:
            return Response({"detail": "only paid can be canceled"}, status=409)
        obj = cancel_purchase(obj)  # 재고 복원 포함
        return Response(PurchaseReadSerializer(obj).data)


class PurchaseRefundAPI(generics.UpdateAPIView):
    """
    PATCH /api/v1/purchases/{purchase_id}/refund  (관리자, any -> refunded)
    """
    lookup_url_kwarg = "purchase_id"
    queryset = Purchase.objects.all()
    permission_classes = [permissions.IsAdminUser]
    serializer_class = PurchaseReadSerializer
    http_method_names = ["patch", "options", "head"]

    @transaction.atomic
    def patch(self, request, *args, **kwargs):
        obj = self.get_object()
        if obj.status == Purchase.STATUS_REFUNDED:
            return Response({"detail": "already refunded"}, status=409)
        obj = refund_purchase(obj)  # 재고 복원 포함
        return Response(PurchaseReadSerializer(obj).data)


# -------------------------------
# Checkout (Cart -> Purchases)
# -------------------------------
class CheckoutView(APIView):
    """
    POST /api/v1/orders/checkout/
    - 로그인 사용자의 장바구니를 주문으로 전환
    - 재고 부족/미등록 옵션 시 409 반환
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = PurchaseReadSerializer
    queryset = Purchase.objects.none()

    @extend_schema(
        operation_id="Checkout",
        responses={201: PurchaseReadSerializer(many=True)},
        tags=["Orders"],
    )

    def post(self, request):
        purchases = checkout_user_cart(request.user)
        return Response(PurchaseReadSerializer(purchases, many=True).data, status=201)