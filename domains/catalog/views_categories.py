# domains/catalog/views_categories.py
from django.shortcuts import get_object_or_404
from django.db import transaction
from rest_framework import generics, permissions
from rest_framework.response import Response

from drf_spectacular.utils import (
    extend_schema, OpenApiParameter, OpenApiTypes
)

from .models import Category, Product
from .serializers import (
    CategorySerializer, CategoryWriteSerializer, CategoryNodeSerializer
)
from drf_spectacular.utils import extend_schema, extend_schema_view




class CategoryListCreateAPI(generics.ListCreateAPIView):
    """
    GET /api/v1/categories        (리스트 or 트리)
      - ?parent_id=<id> : 해당 부모의 직계 하위만
      - ?tree=true      : 트리 형태 응답(루트 전체 or parent_id 기준 하위 트리)
    POST /api/v1/categories       (관리자)
    """
    serializer_class = CategorySerializer  # 기본(읽기)
    permission_classes = [permissions.AllowAny]

    def get_permissions(self):
        return [permissions.IsAdminUser()] if self.request.method == "POST" else [permissions.AllowAny()]

    def get_queryset(self):
        qs = Category.objects.all().order_by("name")
        parent_id = self.request.query_params.get("parent_id")
        if parent_id:
            qs = qs.filter(parent_id=parent_id)
        return qs

    @extend_schema(
        operation_id="ListCategories",
        parameters=[
            OpenApiParameter("parent_id", OpenApiTypes.INT, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("tree", OpenApiTypes.BOOL, OpenApiParameter.QUERY, required=False),
        ],
        responses={200: CategorySerializer(many=True)},
    )
    def list(self, request, *args, **kwargs):
        # 트리 모드
        as_tree = request.query_params.get("tree") in ("1", "true", "True")
        parent_id = request.query_params.get("parent_id")

        if as_tree:
            if parent_id:
                root = get_object_or_404(Category, pk=parent_id)
                return Response(CategoryNodeSerializer(root).data)
            roots = Category.objects.filter(parent__isnull=True).order_by("name")
            return Response(CategoryNodeSerializer(roots, many=True).data)

        return super().list(request, *args, **kwargs)

    def get_serializer_class(self):
        # 생성 시에는 쓰기 전용
        return CategoryWriteSerializer if self.request.method == "POST" else CategorySerializer

    @transaction.atomic
    @extend_schema(operation_id="CreateCategory", request=CategoryWriteSerializer, responses={201: CategorySerializer})
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class CategoryDetailAPI(generics.RetrieveUpdateDestroyAPIView):
    """
    GET    /api/v1/categories/{id}
    PATCH  /api/v1/categories/{id}      (관리자)
    DELETE /api/v1/categories/{id}      (관리자, 자식/상품 연결 시 409)
    """
    http_method_names = ["get", "patch", "delete", "head", "options"]
    lookup_url_kwarg = "category_id"
    queryset = Category.objects.all()
    serializer_class = CategorySerializer

    def get_permissions(self):
        if self.request.method in ("PATCH", "DELETE"):
            return [permissions.IsAdminUser()]
        return [permissions.AllowAny()]

    def get_serializer_class(self):
        return CategoryWriteSerializer if self.request.method == "PATCH" else CategorySerializer

    @extend_schema(operation_id="RetrieveCategory", responses={200: CategorySerializer})
    def get(self, *args, **kwargs):
        return super().get(*args, **kwargs)

    @transaction.atomic
    @extend_schema(operation_id="UpdateCategory", request=CategoryWriteSerializer, responses={200: CategorySerializer})
    def patch(self, *args, **kwargs):
        return super().patch(*args, **kwargs)

    @transaction.atomic
    @extend_schema(operation_id="DeleteCategory", responses={204: None})
    def delete(self, request, *args, **kwargs):
        obj = self.get_object()
        if obj.children.exists() or Product.objects.filter(category_id=obj.pk).exists():
            return Response({"detail": "cannot delete: has children or products"}, status=409)
        return super().delete(request, *args, **kwargs)
