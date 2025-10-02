from __future__ import annotations

from django.db import transaction

from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema
from rest_framework import generics, permissions, status
from rest_framework.response import Response

from .models import Category, Product
from .serializers import CategorySerializer, CategoryWriteSerializer


# /api/v1/categories
class CategoryListCreateAPI(generics.ListCreateAPIView):
    """
    GET  /api/v1/categories         (전체 목록)
    POST /api/v1/categories         (관리자 전용, name만 생성)
    """

    queryset = Category.objects.all().order_by("name")

    def get_permissions(self):
        return (
            [permissions.IsAdminUser()]
            if self.request.method == "POST"
            else [permissions.AllowAny()]
        )

    def get_serializer_class(self):
        return (
            CategoryWriteSerializer
            if self.request.method == "POST"
            else CategorySerializer
        )

    @extend_schema(
        operation_id="ListCategories",
        responses={200: CategorySerializer(many=True)},
    )
    def get(self, *args, **kwargs):
        return super().get(*args, **kwargs)

    @transaction.atomic
    @extend_schema(
        operation_id="CreateCategory",
        request=CategoryWriteSerializer,
        responses={201: CategorySerializer},
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


# /api/v1/categories/{category_id}
class CategoryDetailAPI(generics.RetrieveUpdateDestroyAPIView):
    """
    GET    /api/v1/categories/{category_id}
    PATCH  /api/v1/categories/{category_id}   (관리자)
    DELETE /api/v1/categories/{category_id}   (관리자, 해당 카테고리에 상품 있으면 409)
    """

    lookup_url_kwarg = "category_id"
    queryset = Category.objects.all()

    def get_permissions(self):
        return (
            [permissions.IsAdminUser()]
            if self.request.method in ("PATCH", "DELETE")
            else [permissions.AllowAny()]
        )

    def get_serializer_class(self):
        return (
            CategoryWriteSerializer
            if self.request.method == "PATCH"
            else CategorySerializer
        )

    @extend_schema(
        operation_id="RetrieveCategory",
        parameters=[
            OpenApiParameter("category_id", OpenApiTypes.UUID, OpenApiParameter.PATH)
        ],
        responses={200: CategorySerializer},
    )
    def get(self, *args, **kwargs):
        return super().get(*args, **kwargs)

    @transaction.atomic
    @extend_schema(
        operation_id="UpdateCategory",
        parameters=[
            OpenApiParameter("category_id", OpenApiTypes.UUID, OpenApiParameter.PATH)
        ],
        request=CategoryWriteSerializer,
        responses={200: CategorySerializer},
    )
    def patch(self, *args, **kwargs):
        return super().patch(*args, **kwargs)

    @transaction.atomic
    @extend_schema(
        operation_id="DeleteCategory",
        parameters=[
            OpenApiParameter("category_id", OpenApiTypes.UUID, OpenApiParameter.PATH)
        ],
        responses={204: None, 409: None},
    )
    def delete(self, request, *args, **kwargs):
        obj = self.get_object()
        # parent/children 개념이 없으므로 제품 존재만 체크
        if Product.objects.filter(category_id=obj.pk).exists():
            return Response(
                {"detail": "cannot delete: category has products"},
                status=status.HTTP_409_CONFLICT,
            )
        return super().delete(request, *args, **kwargs)
