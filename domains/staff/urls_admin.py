
# api/staff/urls_admin.py
from django.urls import include, path



from rest_framework.routers import DefaultRouter

from domains.staff.views import (
    AdminCategoryViewSet,
    AdminOrderCancelAPI,
    AdminOrderRefundAPI,
    AdminProductStockViewSet,
    AdminProductViewSet,
    AdminPurchaseViewSet,
    AdminUserRoleAPI,
    AdminUserViewSet,
)

router = DefaultRouter()
router.register(r"users", AdminUserViewSet, basename="admin-users")
router.register(r"categories", AdminCategoryViewSet, basename="admin-categories")
router.register(r"products", AdminProductViewSet, basename="admin-products")
router.register(
    r"product-stocks", AdminProductStockViewSet, basename="admin-product-stocks"
)
router.register(r"orders", AdminPurchaseViewSet, basename="admin-orders")

urlpatterns = [
    path("", include(router.urls)),
    path("users/<uuid:user_id>/role/", AdminUserRoleAPI.as_view()),
    path("orders/<uuid:order_id>/cancel/", AdminOrderCancelAPI.as_view()),
    path("orders/<uuid:order_id>/refund/", AdminOrderRefundAPI.as_view()),
]
