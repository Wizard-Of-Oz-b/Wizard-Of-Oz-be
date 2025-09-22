# domains/catalog/views_products.py
from django.db.models import Q
from django.shortcuts import get_object_or_404
import django_filters as df
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import permissions, generics
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response
from drf_spectacular.utils import (
    extend_schema, OpenApiParameter, OpenApiTypes
)

from .models import Product
from .serializers import (
    ProductReadSerializer, ProductWriteSerializer, ProductImageSlim
)
from shared.pagination import StandardResultsSetPagination


# ─────────────────────────────────────────────────────────────────────────────
# 내부 유틸 (이미지 액세서/정렬)
# ─────────────────────────────────────────────────────────────────────────────
def _image_accessor_for_product() -> str | None:
    """
    Product -> ProductImage 역참조 accessor 이름을 런타임에 탐색한다.
    (예: 'images', 'product_images', 'productimage_set')
    """
    for f in Product._meta.get_fields():
        if f.auto_created and f.is_relation and getattr(f, "related_model", None):
            if f.related_model.__name__ in ("ProductImage", "Image"):
                return f.get_accessor_name()
    return None


def _order_images(qs):
    """
    대표 우선 정렬: is_main DESC → display_order ASC → created_at ASC
    필드가 없으면 가능한 범위에서만 정렬.
    """
    try:
        return qs.order_by("-is_main", "display_order", "created_at")
    except Exception:
        try:
            return qs.order_by("-is_main", "created_at")
        except Exception:
            try:
                return qs.order_by("created_at")
            except Exception:
                return qs


# ─────────────────────────────────────────────────────────────────────────────
# Filters
# ─────────────────────────────────────────────────────────────────────────────
class ProductFilter(df.FilterSet):
    q = df.CharFilter(method="filter_q")
    min_price = df.NumberFilter(field_name="price", lookup_expr="gte")
    max_price = df.NumberFilter(field_name="price", lookup_expr="lte")
    # UUID 필터 (라이브러리 버전에 따라 UUIDFilter 없으면 CharFilter 대체)
    try:
        category_id = df.UUIDFilter(field_name="category_id")
    except AttributeError:
        category_id = df.CharFilter(field_name="category_id")
    is_active = df.BooleanFilter()

    def filter_q(self, qs, name, value):
        return qs.filter(Q(name__icontains=value) | Q(description__icontains=value))

    class Meta:
        model = Product
        fields = ["category_id", "is_active", "min_price", "max_price"]


# ─────────────────────────────────────────────────────────────────────────────
# List & Create
# ─────────────────────────────────────────────────────────────────────────────
class ProductListCreateAPI(generics.ListCreateAPIView):
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = ProductFilter
    ordering_fields = ["name", "price", "created_at"]
    pagination_class = StandardResultsSetPagination
    serializer_class = ProductReadSerializer  # 기본 읽기

    def get_queryset(self):
        qs = Product.objects.all().select_related("category").order_by("-created_at")
        acc = _image_accessor_for_product()
        if acc:
            qs = qs.prefetch_related(acc)
        return qs

    def get_permissions(self):
        # 목록은 공개, 생성은 관리자
        return [permissions.IsAdminUser()] if self.request.method == "POST" else [permissions.AllowAny()]

    def get_serializer_class(self):
        return ProductWriteSerializer if self.request.method == "POST" else ProductReadSerializer

    # 절대 URL 생성을 위해 request 전달
    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx

    @extend_schema(
        operation_id="ListProducts",
        parameters=[
            OpenApiParameter("q", OpenApiTypes.STR, OpenApiParameter.QUERY, required=False, description="이름/설명 검색"),
            OpenApiParameter("min_price", OpenApiTypes.NUMBER, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("max_price", OpenApiTypes.NUMBER, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("category_id", OpenApiTypes.UUID, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("is_active", OpenApiTypes.BOOL, OpenApiParameter.QUERY, required=False),
            OpenApiParameter(
                "ordering",
                OpenApiTypes.STR,
                OpenApiParameter.QUERY,
                required=False,
                description="정렬: name, price, created_at (내림차순은 -price 형식)",
            ),
        ],
        responses={200: ProductReadSerializer(many=True)},
    )
    def get(self, *args, **kwargs):
        return super().get(*args, **kwargs)

    @extend_schema(operation_id="CreateProduct", request=ProductWriteSerializer, responses={201: ProductReadSerializer})
    def post(self, *args, **kwargs):
        return super().post(*args, **kwargs)


# ─────────────────────────────────────────────────────────────────────────────
# Retrieve / Update / Delete
# ─────────────────────────────────────────────────────────────────────────────
class ProductDetailAPI(generics.RetrieveUpdateDestroyAPIView):
    http_method_names = ["get", "patch", "delete", "head", "options"]
    lookup_url_kwarg = "product_id"
    serializer_class = ProductReadSerializer

    def get_queryset(self):
        qs = Product.objects.all().select_related("category")
        acc = _image_accessor_for_product()
        if acc:
            qs = qs.prefetch_related(acc)
        return qs

    def get_permissions(self):
        # 열람은 모두 허용, 수정/삭제는 관리자만
        return [permissions.IsAdminUser()] if self.request.method in ("PATCH", "DELETE") else [permissions.AllowAny()]

    def get_serializer_class(self):
        return ProductWriteSerializer if self.request.method in ("PATCH", "PUT") else ProductReadSerializer

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx

    @extend_schema(operation_id="RetrieveProduct", responses={200: ProductReadSerializer})
    def get(self, *args, **kwargs):
        return super().get(*args, **kwargs)

    @extend_schema(operation_id="UpdateProduct", request=ProductWriteSerializer, responses={200: ProductReadSerializer})
    def patch(self, *args, **kwargs):
        return super().patch(*args, **kwargs)

    @extend_schema(operation_id="DeleteProduct", responses={204: None})
    def delete(self, *args, **kwargs):
        return super().delete(*args, **kwargs)


# ─────────────────────────────────────────────────────────────────────────────
# Public: /api/v1/products/{product_id}/images/
# ─────────────────────────────────────────────────────────────────────────────
class ProductImagesAPI(generics.GenericAPIView):
    """
    상품의 이미지 리스트를 공개로 반환.
    응답: ProductImageSlim[]
    """
    permission_classes = [permissions.AllowAny]
    lookup_url_kwarg = "product_id"  # urls에서 <uuid:product_id>와 매칭

    @extend_schema(operation_id="ListProductImages", responses=ProductImageSlim(many=True))
    def get(self, request, *args, **kwargs):
        product = get_object_or_404(Product, pk=kwargs.get(self.lookup_url_kwarg))
        acc = _image_accessor_for_product()
        images_qs = _order_images(getattr(product, acc).all()) if acc else []
        data = [ProductImageSlim.from_instance(img, request) for img in images_qs]
        return Response(data, status=200)
