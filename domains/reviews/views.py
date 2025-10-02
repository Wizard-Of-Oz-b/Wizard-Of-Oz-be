# domains/reviews/views.py
from django.db.models import Avg, Count
from django.shortcuts import get_object_or_404

from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema
from rest_framework import generics, permissions
from rest_framework.response import Response

from domains.catalog.models import Product
from domains.reviews.models import Review
from domains.reviews.serializers import ReviewReadSerializer, ReviewWriteSerializer
from shared.pagination import StandardResultsSetPagination
from shared.permissions import IsOwnerOrAdmin


@extend_schema(
    parameters=[
        OpenApiParameter(
            name="product_id",
            type=OpenApiTypes.UUID,  # 👈 UUID
            location=OpenApiParameter.PATH,
            description="상품 ID (UUID)",
            required=True,
        )
    ]
)
class ProductReviewListCreateAPI(generics.ListCreateAPIView):
    """
    GET  /api/v1/products/{product_id}/reviews
    POST /api/v1/products/{product_id}/reviews  (구매자만)
    """

    pagination_class = StandardResultsSetPagination
    queryset = Review.objects.none()

    def get_queryset(self):
        # 스키마 생성 시에는 빈 쿼리셋
        if getattr(self, "swagger_fake_view", False):
            return Review.objects.none()
        return (
            Review.objects.filter(product_id=self.kwargs.get("product_id"))
            .select_related("user")
            .order_by("-created_at")
        )

    def get_permissions(self):
        return (
            [permissions.IsAuthenticated()]
            if self.request.method == "POST"
            else [permissions.AllowAny()]
        )

    def perform_create(self, serializer):
        """
        ReviewWriteSerializer.validate()에서 이미
        user/product_id를 attrs에 주입하므로 여기서는 단순 save().
        """
        serializer.save()

    def get_serializer_class(self):
        return (
            ReviewWriteSerializer
            if self.request.method == "POST"
            else ReviewReadSerializer
        )

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        # Serializer에서 product_id를 사용할 수 있게 컨텍스트로 전달
        ctx["product_id"] = self.kwargs["product_id"]
        return ctx

    @extend_schema(
        operation_id="ListProductReviews",
        parameters=[
            OpenApiParameter(
                "product_id",
                OpenApiTypes.UUID,
                OpenApiParameter.PATH,
                description="상품 ID (UUID)",
                required=True,
            ),
            OpenApiParameter(
                "page",
                OpenApiTypes.INT,
                OpenApiParameter.QUERY,
                required=False,
                description="페이지 번호",
            ),
            OpenApiParameter(
                "size",
                OpenApiTypes.INT,
                OpenApiParameter.QUERY,
                required=False,
                description="페이지 크기",
            ),
        ],
        # 실제 응답은 {"items": [...], "avg_rating": float, "count": int} 형태지만
        # 스키마 단순화를 위해 items에 대한 타입만 지정
        responses={200: ReviewReadSerializer(many=True)},
        tags=["products"],
    )
    def list(self, request, *args, **kwargs):
        product_id = kwargs["product_id"]
        # 존재 검증
        get_object_or_404(Product, pk=product_id)

        resp = super().list(request, *args, **kwargs)

        agg = Review.objects.filter(product_id=product_id).aggregate(
            avg=Avg("rating"),
            count=Count("review_id"),
        )
        resp.data = {
            "items": resp.data,
            "avg_rating": round(agg["avg"] or 0, 2),
            "count": agg["count"],
        }
        return resp

    @extend_schema(
        operation_id="CreateProductReview",
        request=ReviewWriteSerializer,
        responses={201: ReviewReadSerializer},
        tags=["products"],
    )
    def post(self, request, *args, **kwargs):
        # 유효한 상품인지 선검증
        get_object_or_404(Product, pk=kwargs["product_id"])
        return super().post(request, *args, **kwargs)


class ReviewDetailAPI(generics.RetrieveUpdateDestroyAPIView):
    """
    GET/PATCH/DELETE /api/v1/reviews/{review_id}
    """

    lookup_url_kwarg = "review_id"
    queryset = Review.objects.all()
    permission_classes = [IsOwnerOrAdmin]
    http_method_names = ["get", "patch", "delete", "options", "head"]

    def get_serializer_class(self):
        return (
            ReviewWriteSerializer
            if self.request.method == "PATCH"
            else ReviewReadSerializer
        )

    @extend_schema(operation_id="GetReview", tags=["products"])
    def get(self, *a, **kw):
        return super().get(*a, **kw)

    @extend_schema(
        operation_id="UpdateReview", request=ReviewWriteSerializer, tags=["products"]
    )
    def patch(self, *a, **kw):
        return super().patch(*a, **kw)

    @extend_schema(operation_id="DeleteReview", tags=["products"])
    def delete(self, *a, **kw):
        return super().delete(*a, **kw)
