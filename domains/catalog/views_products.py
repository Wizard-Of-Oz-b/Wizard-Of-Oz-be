# domains/catalog/views_products.py
from django.db.models import Q
import django_filters as df
from rest_framework import permissions, generics
from rest_framework.filters import OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter, OpenApiTypes

from .models import Product
from .serializers import ProductReadSerializer, ProductWriteSerializer
from shared.pagination import StandardResultsSetPagination


# ─────────────────────────────────────────────────────────────────────────────
# Filters
# ─────────────────────────────────────────────────────────────────────────────
class ProductFilter(df.FilterSet):
    q = df.CharFilter(method="filter_q")
    min_price = df.NumberFilter(field_name="price", lookup_expr="gte")
    max_price = df.NumberFilter(field_name="price", lookup_expr="lte")
    # UUID 필터 (django-filters에 UUIDFilter가 있음. 없다면 CharFilter로 대체 가능)
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

    # 이미지/카테고리 프리패치 + 최신순
    def _image_accessor(self):
        # Product -> ProductImage 역참조 이름을 런타임에 탐색
        for f in Product._meta.get_fields():
            if f.auto_created and f.is_relation and getattr(f, "related_model", None):
                if f.related_model.__name__ in ("ProductImage", "Image",):
                    return f.get_accessor_name()  # ex) "images" 또는 "productimage_set"
        return None

    def get_queryset(self):
        qs = Product.objects.all().select_related("category").order_by("-created_at")
        acc = self._image_accessor()
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
            OpenApiParameter("q", OpenApiTypes.STR, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("min_price", OpenApiTypes.NUMBER, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("max_price", OpenApiTypes.NUMBER, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("category_id", OpenApiTypes.UUID, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("is_active", OpenApiTypes.BOOL, OpenApiParameter.QUERY, required=False),
            OpenApiParameter(
                "ordering",
                OpenApiTypes.STR,
                OpenApiParameter.QUERY,
                required=False,
                description="정렬: name, price, created_at (내림차순은 -price 같은 형식)",
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
        acc = None
        for f in Product._meta.get_fields():
            if f.auto_created and f.is_relation and getattr(f, "related_model", None):
                if f.related_model.__name__ in ("ProductImage", "Image",):
                    acc = f.get_accessor_name()
                    break
        if acc:
            qs = qs.prefetch_related(acc)
        return qs

    def get_permissions(self):
        # 열람은 모두 허용, 수정/삭제는 관리자만
        return [permissions.IsAdminUser()] if self.request.method in ("PATCH", "DELETE") else [permissions.AllowAny()]

    def get_serializer_class(self):
        # 수정 시에는 쓰기용
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
