from rest_framework.routers import DefaultRouter
from .views import MyWishlistViewSet
router = DefaultRouter()
router.register(r"wishlist/items", MyWishlistViewSet, basename="my-wishlist")
urlpatterns = router.urls
