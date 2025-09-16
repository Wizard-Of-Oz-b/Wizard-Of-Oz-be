# domains/catalog/views_stock.py
import django_filters as df
from rest_framework import viewsets, permissions
from rest_framework.filters import OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema

from .models import ProductStock
from .serializers import ProductStockReadSerializer, ProductStockWriteSerializer

class ProductStockFilter(df.FilterSet):
    product_id = df.UUIDFilter(field_name="product_id")
    option_key = df.CharFilter(lookup_expr="icontains")

    class Meta:
        model = ProductStock
        fields = ["product_id", "option_key"]

class ProductStockViewSet(viewsets.ModelViewSet):
    queryset = ProductStock.objects.select_related("product").all().order_by("-updated_at")
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = ProductStockFilter
    ordering_fields = ["updated_at", "stock_quantity"]

    def get_permissions(self):
        # 읽기는 모두 허용, 쓰기/수정/삭제는 관리자만
        if self.action in ("list", "retrieve"):
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]

    def get_serializer_class(self):
        return ProductStockWriteSerializer if self.action in ("create", "update", "partial_update") else ProductStockReadSerializer

    # 문서용
    @extend_schema(operation_id="ListProductStocks")
    def list(self, *args, **kwargs):
        return super().list(*args, **kwargs)

    @extend_schema(operation_id="CreateProductStock", request=ProductStockWriteSerializer, responses={201: ProductStockReadSerializer})
    def create(self, *args, **kwargs):
        return super().create(*args, **kwargs)
