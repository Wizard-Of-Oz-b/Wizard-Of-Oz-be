# domains/catalog/urls_stock.py
from rest_framework.routers import SimpleRouter

from .views_stock import ProductStockViewSet

router = SimpleRouter()
# api/v1에서 "product-stocks/" 프리픽스에 붙일 거라 여기 prefix는 비워 둡니다.
router.register(r"", ProductStockViewSet, basename="product-stock")

urlpatterns = router.urls
