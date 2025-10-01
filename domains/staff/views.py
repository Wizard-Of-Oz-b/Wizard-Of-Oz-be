from django.contrib.auth import get_user_model
from django.utils import timezone
from django.shortcuts import get_object_or_404

from rest_framework import viewsets, permissions, filters, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

from drf_spectacular.utils import extend_schema, OpenApiExample
from django_filters.rest_framework import DjangoFilterBackend
import django_filters as df

# URL 다운로드(저장 모드)용
import os, uuid, mimetypes
from urllib.parse import urlparse
from urllib.request import urlopen, Request
from django.core.files.base import ContentFile

from domains.accounts.serializers import EmptySerializer
from domains.staff.permissions import IsAdminRole, IsAdminOrManager
from domains.staff.serializers import (
    # Users
    UserMinSerializer, UserRoleUpdateSerializer,
    # Catalog
    CategoryAdminSerializer, ProductAdminSerializer, ProductStockAdminSerializer,
    ProductImageAdminSerializer, ProductImagesUploadSerializer,
    # Orders
    PurchaseAdminSerializer, OrderActionResponseSerializer,
)

from domains.catalog.models import Category, Product, ProductStock, ProductImage
from domains.orders.models import Purchase

User = get_user_model()


# ---------------------------------------------------------
# Users (ADMIN)
# ---------------------------------------------------------
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


# ---------------------------------------------------------
# Categories (ADMIN·MANAGER)
# ---------------------------------------------------------
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


# ---------------------------------------------------------
# Products (ADMIN·MANAGER)
# ---------------------------------------------------------
@extend_schema(tags=["Admin • Products"])
class AdminProductViewSet(viewsets.ModelViewSet):
    """
    /api/v1/admin/products/
    + /api/v1/admin/products/{id}/images/  (GET 목록, POST 업로드)
    """
    queryset = Product.objects.all().select_related("category").order_by("-created_at")
    serializer_class = ProductAdminSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOrManager]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name"]
    ordering_fields = ["created_at", "price", "name"]
    parser_classes = [MultiPartParser, FormParser, JSONParser]  # 파일/JSON 모두 허용

    @extend_schema(
        tags=["Admin • Products"],
        summary="상품 이미지 업로드/목록 (파일, URL 저장, 또는 URL 참조)",
        request=ProductImagesUploadSerializer,
        responses={200: ProductImageAdminSerializer(many=True)},
        operation_id="AdminProductImages",
    )
    @action(
        detail=True,
        methods=["get", "post"],                  # GET/POST 하나로 통합
        url_path="images",
        parser_classes=[MultiPartParser, FormParser, JSONParser],
    )
    def images(self, request, pk=None):
        product = get_object_or_404(Product, pk=pk)

        # ---- 목록 (GET) ----
        if request.method == "GET":
            qs = product.images.order_by("display_order", "created_at")
            ser = ProductImageAdminSerializer(qs, many=True, context={"request": request})
            return Response(ser.data, status=200)

        # ---- 업로드 (POST) ----
        in_ser = ProductImagesUploadSerializer(data=request.data)
        in_ser.is_valid(raise_exception=True)
        data = in_ser.validated_data

        # form-data 파일
        files = list(request.FILES.getlist("images") or [])
        # URL 배열 (form-data/JSON 모두 대응)
        url_list = data.get("image_urls") or []

        # 모드: True면 원격 URL만 참조 저장, False면 URL 다운로드하여 파일 저장
        save_remote = data.get("save_remote", False)

        main_index   = data.get("main_index", -1)
        start_order  = data.get("start_order", 0)
        replace_main = data.get("replace_main", False)
        alt_texts = data.get("alt_texts") or []
        captions  = data.get("captions")  or []

        # 기존 대표 제거
        if replace_main:
            product.images.filter(is_main=True).update(is_main=False)

        created = []
        url_errors = []

        # 1) URL만 참조 (다운로드 X)
        if save_remote and url_list:
            for i, url in enumerate(url_list):
                try:
                    img = ProductImage.objects.create(
                        product=product,
                        remote_url=url,
                        is_remote=True,
                        alt_text=(alt_texts[i] if i < len(alt_texts) else ""),
                        caption=(captions[i]  if i < len(captions)  else ""),
                        is_main=False,
                        display_order=start_order + len(created),
                    )
                    created.append(img)
                except Exception as e:
                    url_errors.append({"url": url, "error": str(e)})

        # 2) URL 다운로드 → 파일 저장 (save_remote=False 일 때만)
        if (not save_remote) and url_list:
            for url in url_list:
                try:
                    if not url.lower().startswith(("http://", "https://")):
                        raise ValueError("only http/https is allowed")
                    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
                    with urlopen(req, timeout=10) as resp:
                        data_bytes = resp.read()
                        content_type = resp.headers.get_content_type() or "application/octet-stream"
                    base = os.path.basename(urlparse(url).path) or f"remote_{uuid.uuid4().hex}"
                    ext = os.path.splitext(base)[1] or (mimetypes.guess_extension(content_type) or ".jpg")
                    name = base if base.endswith(ext) else base + ext
                    files.append(ContentFile(data_bytes, name=name))
                except Exception as e:
                    url_errors.append({"url": url, "error": str(e)})

        # 3) form-data 파일 저장
        for i, f in enumerate(files):
            img = ProductImage.objects.create(
                product=product,
                image=f,
                is_remote=False,
                alt_text=(alt_texts[i] if i < len(alt_texts) else ""),
                caption=(captions[i]  if i < len(captions)  else ""),
                is_main=False,
                display_order=start_order + len(created),
            )
            created.append(img)

        # 대표 지정
        if created:
            set_main = None
            if 0 <= main_index < len(created):
                set_main = created[main_index]
            elif not product.images.filter(is_main=True).exists():
                set_main = created[0]
            if set_main:
                product.images.filter(is_main=True).exclude(pk=set_main.pk).update(is_main=False)
                set_main.is_main = True
                set_main.save(update_fields=["is_main", "updated_at"])

        out = ProductImageAdminSerializer(created, many=True, context={"request": request}).data
        body = {"uploaded": out}
        if url_errors:
            body["url_errors"] = url_errors
        return Response(body, status=status.HTTP_201_CREATED)


# ---------------------------------------------------------
# Stocks (ADMIN·MANAGER)
# ---------------------------------------------------------
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


# ---------------------------------------------------------
# Product Images CRUD (ADMIN·MANAGER)
# ---------------------------------------------------------
@extend_schema(tags=["Admin • Product Images"])
class AdminProductImageViewSet(viewsets.ModelViewSet):
    """
    /api/v1/admin/product-images/
    - 파일 업로드: multipart/form-data (image 필수)
    - 필터: ?product=<uuid>&stock=<uuid>&is_main=true
    """
    queryset = ProductImage.objects.all().select_related("product", "stock").order_by("product_id", "display_order", "-created_at")
    serializer_class = ProductImageAdminSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOrManager]
    parser_classes = [MultiPartParser, FormParser]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["product", "stock", "is_main"]
    ordering_fields = ["display_order", "created_at"]


# ---------------------------------------------------------
# Orders (ADMIN·MANAGER; refund은 ADMIN만)
# ---------------------------------------------------------
class PurchaseFilter(df.FilterSet):
    status = df.CharFilter(field_name="status")
    user_email = df.CharFilter(field_name="user__email", lookup_expr="icontains")
    created_from = df.IsoDateTimeFilter(field_name="purchased_at", lookup_expr="gte")
    created_to   = df.IsoDateTimeFilter(field_name="purchased_at", lookup_expr="lte")

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
