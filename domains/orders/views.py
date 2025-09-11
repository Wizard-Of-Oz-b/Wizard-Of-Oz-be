import django_filters as df
from django.db import transaction
from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.filters import OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema

from domains.orders.models import Purchase
from domains.orders.serializers import PurchaseReadSerializer, PurchaseWriteSerializer
from shared.permissions import IsOwnerOrAdmin
from shared.pagination import StandardResultsSetPagination


# ---- 공통 필터 (Admin 목록용) ----
class PurchaseFilter(df.FilterSet):
    status = df.CharFilter()
    user_id = df.NumberFilter(field_name="user_id")
    product_id = df.NumberFilter(field_name="product_id")
    date_from = df.IsoDateTimeFilter(field_name="purchased_at", lookup_expr="gte")
    date_to = df.IsoDateTimeFilter(field_name="purchased_at", lookup_expr="lte")

    class Meta:
        model = Purchase
        fields = ["status", "user_id", "product_id", "date_from", "date_to"]


# ---- GET(Admin) / POST(Auth) 한 엔드포인트로 합치기 ----
class PurchaseListCreateAPI(generics.ListCreateAPIView):
    """
    GET  /api/v1/purchases        (관리자만, 필터/정렬/페이징)
    POST /api/v1/purchases        (로그인 필요, 결제성공으로 간주하여 구매 생성)
    """
    queryset = Purchase.objects.all().order_by("-purchased_at")
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = PurchaseFilter
    ordering_fields = ["purchased_at", "amount"]
    pagination_class = StandardResultsSetPagination

    def get_permissions(self):
        # 목록은 관리자만, 생성은 로그인 사용자
        return [permissions.IsAdminUser()] if self.request.method == "GET" else [permissions.IsAuthenticated()]

    def get_serializer_class(self):
        return PurchaseWriteSerializer if self.request.method == "POST" else PurchaseReadSerializer

    @extend_schema(operation_id="ListPurchases")
    def get(self, *args, **kwargs):
        return super().get(*args, **kwargs)

    @transaction.atomic
    @extend_schema(operation_id="CreatePurchase", request=PurchaseWriteSerializer, responses={201: PurchaseReadSerializer})
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

    # user/status를 확실히 세팅
    def perform_create(self, serializer):
        serializer.save(user=self.request.user, status=Purchase.STATUS_PAID)


# ---- 내 구매 목록 / 상세 ----
class PurchaseMeListAPI(generics.ListAPIView):
    """GET /api/v1/purchases/me  (로그인 사용자의 본인 구매 목록)"""
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = PurchaseReadSerializer
    pagination_class = StandardResultsSetPagination

    # ✅ 스키마 생성 시 모델 추론용 안전 기본값
    queryset = Purchase.objects.none()

    def get_queryset(self):
        # ✅ 스키마 생성 중이거나 비인증이면 빈 쿼리셋
        if getattr(self, "swagger_fake_view", False) or not self.request.user.is_authenticated:
            return Purchase.objects.none()
        # 성능/타입 안전을 위해 user_id로 필터 권장(= int)
        return (Purchase.objects
                .filter(user_id=self.request.user.id)   # ← 기존 user=self.request.user 도 동작은 OK
                .order_by("-purchased_at"))


class PurchaseDetailAPI(generics.RetrieveAPIView):
    """
    GET /api/v1/purchases/{purchase_id}  (소유자 또는 관리자)
    """
    lookup_url_kwarg = "purchase_id"
    queryset = Purchase.objects.all()
    permission_classes = [IsOwnerOrAdmin]
    serializer_class = PurchaseReadSerializer


# ---- 상태 전이 ----
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
        obj.status = Purchase.STATUS_CANCELED
        obj.save(update_fields=["status"])
        return Response(PurchaseReadSerializer(obj).data)


class PurchaseRefundAPI(generics.UpdateAPIView):
    """
    PATCH /api/v1/purchases/{purchase_id}/refund  (관리자, any -> refunded)
    """
    lookup_url_kwarg = "purchase_id"
    queryset = Purchase.objects.all()
    permission_classes = [permissions.IsAdminUser]  # 관리자/CS만
    serializer_class = PurchaseReadSerializer
    http_method_names = ["get", "patch", "delete", "options", "head"]

    @transaction.atomic
    def patch(self, request, *args, **kwargs):
        obj = self.get_object()
        if obj.status == Purchase.STATUS_REFUNDED:
            return Response({"detail": "already refunded"}, status=409)
        obj.status = Purchase.STATUS_REFUNDED
        obj.save(update_fields=["status"])
        return Response(PurchaseReadSerializer(obj).data)
