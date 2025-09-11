# domains/catalog/views_products.py
from django.db.models import Q
import django_filters as df
from rest_framework import permissions, generics
from rest_framework.filters import OrderingFilter
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes

from .models import Product
from .serializers import ProductReadSerializer, ProductWriteSerializer
from shared.pagination import StandardResultsSetPagination
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view

class ProductFilter(df.FilterSet):
    q = df.CharFilter(method="filter_q")
    min_price = df.NumberFilter(field_name="price", lookup_expr="gte")
    max_price = df.NumberFilter(field_name="price", lookup_expr="lte")
    category_id = df.NumberFilter(field_name="category_id")
    is_active = df.BooleanFilter()

    def filter_q(self, qs, name, value):
        return qs.filter(Q(name__icontains=value) | Q(description__icontains=value))

    class Meta:
        model = Product
        fields = ["category_id", "is_active", "min_price", "max_price"]

class ProductListCreateAPI(generics.ListCreateAPIView):
    queryset = Product.objects.all().order_by("-created_at")
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = ProductFilter
    ordering_fields = ["name", "price", "created_at"]
    pagination_class = StandardResultsSetPagination
    serializer_class = ProductReadSerializer  # 기본 읽기

    def get_permissions(self):
        return [permissions.IsAdminUser()] if self.request.method == "POST" else [permissions.AllowAny()]

    def get_serializer_class(self):
        return ProductWriteSerializer if self.request.method == "POST" else ProductReadSerializer

    @extend_schema(
        operation_id="ListProducts",
        parameters=[
            OpenApiParameter("q", OpenApiTypes.STR, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("min_price", OpenApiTypes.INT, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("max_price", OpenApiTypes.INT, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("category_id", OpenApiTypes.INT, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("is_active", OpenApiTypes.BOOL, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("ordering", OpenApiTypes.STR, OpenApiParameter.QUERY, required=False,
                             description="정렬: name, price, created_at (내림차순은 -price 같은 형식)"),
        ],
        responses={200: ProductReadSerializer(many=True)},
    )
    def get(self, *args, **kwargs):
        return super().get(*args, **kwargs)

    @extend_schema(operation_id="CreateProduct", request=ProductWriteSerializer, responses={201: ProductReadSerializer})
    def post(self, *args, **kwargs):
        return super().post(*args, **kwargs)

class ProductDetailAPI(generics.RetrieveUpdateDestroyAPIView):
    http_method_names = ["get", "patch", "delete", "head", "options"]
    lookup_url_kwarg = "product_id"
    queryset = Product.objects.all()
    serializer_class = ProductReadSerializer

    def get_permissions(self):
        # 열람은 모두 허용, 수정/삭제는 관리자만
        return [permissions.IsAdminUser()] if self.request.method in ("PATCH", "DELETE") else [permissions.AllowAny()]

    def get_serializer_class(self):
        # 🔑 수정(PATCH/PUT) 시에는 반드시 쓰기용
        return ProductWriteSerializer if self.request.method in ("PATCH", "PUT") else ProductReadSerializer

    @extend_schema(operation_id="RetrieveProduct", responses={200: ProductReadSerializer})
    def get(self, *args, **kwargs):
        return super().get(*args, **kwargs)

    @extend_schema(operation_id="UpdateProduct", request=ProductWriteSerializer, responses={200: ProductReadSerializer})
    def patch(self, *args, **kwargs):
        return super().patch(*args, **kwargs)

    @extend_schema(operation_id="DeleteProduct", responses={204: None})
    def delete(self, *args, **kwargs):
        return super().delete(*args, **kwargs)
