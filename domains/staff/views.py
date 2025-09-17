# api/staff/views.py
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.shortcuts import get_object_or_404

from rest_framework import viewsets, permissions, filters
from rest_framework.response import Response
from rest_framework.views import APIView

from drf_spectacular.utils import extend_schema, OpenApiExample
from django_filters.rest_framework import DjangoFilterBackend
import django_filters as df

from domains.accounts.serializers import EmptySerializer
from domains.staff.permissions import IsAdminRole, IsAdminOrManager
from domains.staff.serializers import (
    UserMinSerializer, UserRoleUpdateSerializer,
    CategoryAdminSerializer, ProductAdminSerializer, ProductStockAdminSerializer,
    PurchaseAdminSerializer, OrderActionResponseSerializer,
)

from domains.catalog.models import Category, Product, ProductStock
from domains.orders.models import Purchase

User = get_user_model()


# ---------- Users (ADMIN) ----------
@extend_schema(tags=["Admin • Users"])
class AdminUserViewSet(viewsets.ReadOnlyModelViewSet):
    """
    GET /api/v1/admin/users/
    GET /api/v1/admin/users/{id}/
    """
    queryset = User.objects.all().order_by("-created_at")
    serializer_class = UserMinSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["email", "nickname"]
    ordering_fields = ["created_at", "email"]


class AdminUserRoleAPI(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    @extend_schema(
        tags=["Admin • Users"],
        summary="사용자 역할 변경(ADMIN)",
        request=UserRoleUpdateSerializer,
        responses={200: UserRoleUpdateSerializer},
        examples=[OpenApiExample("매니저로 변경", value={"role": "manager"})],
        operation_id="AdminChangeUserRole",
    )
    def patch(self, request, user_id):
        ser = UserRoleUpdateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        new_role = ser.validated_data["role"]

        target = get_object_or_404(User, pk=user_id)

        # 자기 자신 강등 금지
        if request.user.pk == target.pk and new_role != "admin":
            return Response({"detail": "자기 자신을 관리자에서 내릴 수 없습니다."}, status=400)

        target.role = new_role
        update_fields = ["role", "is_staff"]
        if hasattr(target, "updated_at"):
            update_fields.append("updated_at")
        target.save(update_fields=update_fields)  # User.save()에서 role→is_staff 동기화

        return Response({"role": target.role}, status=200)


# ---------- Categories (ADMIN·MANAGER) ----------
class CategoryFilter(df.FilterSet):
    name = df.CharFilter(field_name="name", lookup_expr="icontains")
    level = df.CharFilter(field_name="level")
    parent = df.UUIDFilter(field_name="parent_id")

    class Meta:
        model = Category
        fields = ["name", "level", "parent"]


@extend_schema(tags=["Admin • Categories"])
class AdminCategoryViewSet(viewsets.ModelViewSet):
    """
    /api/v1/admin/categories/
    - GET ?level=l1        : 대분류만
    - GET ?parent=<uuid>   : 특정 부모의 하위만
    """
    queryset = Category.objects.all().order_by("path")
    serializer_class = CategoryAdminSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOrManager]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = CategoryFilter
    search_fields = ["name", "path"]
    ordering_fields = ["created_at", "name", "path"]

    # 삭제는 ADMIN만 허용(선택)
    def destroy(self, request, *args, **kwargs):
        if getattr(request.user, "role", "") != "admin":
            return Response({"detail": "카테고리 삭제는 관리자만 가능합니다."}, status=403)
        return super().destroy(request, *args, **kwargs)


# ---------- Products (ADMIN·MANAGER) ----------
@extend_schema(tags=["Admin • Products"])
class AdminProductViewSet(viewsets.ModelViewSet):
    """
    /api/v1/admin/products/
    """
    queryset = Product.objects.all().select_related("category").order_by("-created_at")
    serializer_class = ProductAdminSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOrManager]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name"]
    ordering_fields = ["created_at", "price", "name"]


# ---------- Stocks (ADMIN·MANAGER) ----------
class StockFilter(df.FilterSet):
    product = df.UUIDFilter(field_name="product_id")
    option_key = df.CharFilter(field_name="option_key", lookup_expr="icontains")

    class Meta:
        model = ProductStock
        fields = ["product", "option_key"]


@extend_schema(tags=["Admin • Stocks"])
class AdminProductStockViewSet(viewsets.ModelViewSet):
    """
    /api/v1/admin/product-stocks/
    """
    queryset = ProductStock.objects.all().select_related("product")
    serializer_class = ProductStockAdminSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOrManager]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = StockFilter
    search_fields = ["option_key"]
    ordering_fields = ["stock_quantity"]


# ---------- Orders (ADMIN·MANAGER; refund은 ADMIN만) ----------
class PurchaseFilter(df.FilterSet):
    status = df.CharFilter(field_name="status")
    user_email = df.CharFilter(field_name="user__email", lookup_expr="icontains")
    # created_at → purchased_at 필드에 매핑
    created_from = df.IsoDateTimeFilter(field_name="purchased_at", lookup_expr="gte")
    created_to = df.IsoDateTimeFilter(field_name="purchased_at", lookup_expr="lte")

    class Meta:
        model = Purchase
        fields = ["status", "user_email", "created_from", "created_to"]


@extend_schema(tags=["Admin • Orders"])
class AdminPurchaseViewSet(viewsets.ReadOnlyModelViewSet):
    """
    GET /api/v1/admin/orders/
    GET /api/v1/admin/orders/{id}/
    """
    queryset = Purchase.objects.all().select_related("user").order_by("-purchased_at")
    serializer_class = PurchaseAdminSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOrManager]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter, filters.SearchFilter]
    filterset_class = PurchaseFilter
    search_fields = ["user__email"]
    ordering_fields = ["purchased_at", "amount"]


class AdminOrderCancelAPI(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminOrManager]

    @extend_schema(
        tags=["Admin • Orders"],
        summary="주문 취소(ADMIN·MANAGER)",
        request=EmptySerializer,
        responses={200: OrderActionResponseSerializer},
        operation_id="AdminOrderCancel",
    )
    def patch(self, request, order_id):
        p = get_object_or_404(Purchase, pk=order_id)
        if p.status != "paid":
            return Response({"detail": "paid 상태에서만 취소 가능합니다."}, status=409)

        p.status = "canceled"
        if hasattr(p, "updated_at"):
            p.updated_at = timezone.now()
        fields = ["status"]
        if hasattr(p, "updated_at"):
            fields.append("updated_at")
        p.save(update_fields=fields)

        return Response({"id": str(p.pk), "status": p.status}, status=200)


class AdminOrderRefundAPI(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]  # ADMIN only

    @extend_schema(
        tags=["Admin • Orders"],
        summary="주문 환불(ADMIN)",
        request=EmptySerializer,
        responses={200: OrderActionResponseSerializer},
        operation_id="AdminOrderRefund",
    )
    def patch(self, request, order_id):
        p = get_object_or_404(Purchase, pk=order_id)
        if p.status not in ("paid", "canceled"):
            return Response({"detail": "paid 또는 canceled 상태에서만 환불 가능합니다."}, status=409)

        p.status = "refunded"
        if hasattr(p, "updated_at"):
            p.updated_at = timezone.now()
        fields = ["status"]
        if hasattr(p, "updated_at"):
            fields.append("updated_at")
        p.save(update_fields=fields)

        return Response({"id": str(p.pk), "status": p.status}, status=200)
