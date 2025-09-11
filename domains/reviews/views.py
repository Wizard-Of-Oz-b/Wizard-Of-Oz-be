from django.db.models import Avg, Count
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes

from domains.catalog.models import Product
from domains.reviews.models import Review
from domains.reviews.serializers import ReviewReadSerializer, ReviewWriteSerializer
from shared.permissions import IsOwnerOrAdmin
from shared.pagination import StandardResultsSetPagination

class ProductReviewListCreateAPI(generics.ListCreateAPIView):
    """
    GET  /api/v1/products/{product_id}/reviews
    POST /api/v1/products/{product_id}/reviews (구매자만)
    """
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        product_id = self.kwargs["product_id"]
        return Review.objects.filter(product_id=product_id).order_by("-created_at")

    def get_permissions(self):
        return [permissions.IsAuthenticated()] if self.request.method == "POST" else [permissions.AllowAny()]

    def get_serializer_class(self):
        return ReviewWriteSerializer if self.request.method == "POST" else ReviewReadSerializer

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["product_id"] = self.kwargs["product_id"]
        return ctx

    @extend_schema(
        operation_id="ListProductReviews",
        parameters=[OpenApiParameter("product_id", OpenApiTypes.INT, OpenApiParameter.PATH)],
        responses={200: ReviewReadSerializer(many=True)},
    )
    def list(self, request, *args, **kwargs):
        product_id = kwargs["product_id"]
        get_object_or_404(Product, pk=product_id)
        resp = super().list(request, *args, **kwargs)

        agg = Review.objects.filter(product_id=product_id).aggregate(avg=Avg("rating"), count=Count("review_id"))
        resp.data = {"items": resp.data, "avg_rating": round(agg["avg"] or 0, 2), "count": agg["count"]}
        return resp

    @extend_schema(operation_id="CreateProductReview", request=ReviewWriteSerializer, responses={201: ReviewReadSerializer})
    def post(self, request, *args, **kwargs):
        get_object_or_404(Product, pk=kwargs["product_id"])
        return super().post(request, *args, **kwargs)

class ReviewDetailAPI(generics.RetrieveUpdateDestroyAPIView):
    """
    PATCH/DELETE /api/v1/reviews/{review_id}
    """
    lookup_url_kwarg = "review_id"
    queryset = Review.objects.all()
    permission_classes = [IsOwnerOrAdmin]

    def get_serializer_class(self):
        # 부분 수정(평점/내용)
        return ReviewWriteSerializer if self.request.method == "PATCH" else ReviewReadSerializer

    @extend_schema(operation_id="GetReview")
    def get(self, *a, **kw):
        return super().get(*a, **kw)

    @extend_schema(operation_id="UpdateReview", request=ReviewWriteSerializer)
    def patch(self, *a, **kw):
        return super().patch(*a, **kw)

    @extend_schema(operation_id="DeleteReview")
    def delete(self, *a, **kw):
        return super().delete(*a, **kw)
