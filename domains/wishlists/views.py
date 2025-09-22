from rest_framework import mixins, viewsets, permissions, filters
from django_filters.rest_framework import DjangoFilterBackend
from domains.wishlists.models import WishlistItem
from .serializers import WishlistItemReadSerializer, WishlistItemWriteSerializer

class MyWishlistViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet):
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields   = ["product__name", "product__description"]
    ordering_fields = ["created_at", "product__price"]

    def get_queryset(self):
        return (WishlistItem.objects
                .filter(user=self.request.user)
                .select_related("product")
                .prefetch_related("product__images")
                .order_by("-created_at"))

    def get_serializer_class(self):
        return WishlistItemWriteSerializer if self.action == "create" else WishlistItemReadSerializer
