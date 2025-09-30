# config/urls.py — 최종본

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include, re_path
from django.views.generic import RedirectView
from django.http import HttpResponse, JsonResponse

from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from domains.shipments.views import ShipmentWebhookAPI


# --- 디버그용 콜백(선택) ---
def oauth_debug_callback(request):
    code = request.GET.get("code")
    state = request.GET.get("state")
    if not code:
        return HttpResponse("No 'code' in query", status=400)
    return HttpResponse(f"OK<br>code={code}<br>state={state}", content_type="text/html")


def healthz(_):
    return JsonResponse({"ok": True})


urlpatterns = [
    # Admin
    path("admin/", admin.site.urls),

    # OpenAPI / Swagger (v1 스키마를 기준으로 노출)
    path("api/v1/schema/", SpectacularAPIView.as_view(), name="v1-schema"),
    path("api/v1/docs/",   SpectacularSwaggerView.as_view(url_name="v1-schema"), name="v1-docs"),
    path("api/schema/",    SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/",      SpectacularSwaggerView.as_view(url_name="v1-schema"), name="docs"),

    # 슬래시 없는 접근 → 슬래시 붙은 경로로 301 정규화
    re_path(r"^api/v1/schema$", RedirectView.as_view(url="/api/v1/schema/", permanent=True)),
    re_path(r"^api/v1/docs$",   RedirectView.as_view(url="/api/v1/docs/",   permanent=True)),
    re_path(r"^api/schema$",    RedirectView.as_view(url="/api/schema/",    permanent=True)),
    re_path(r"^api/docs$",      RedirectView.as_view(url="/api/docs/",      permanent=True)),

    # === 여기부터 실제 API ===
    # Shipments (절대 지우면 안 됨!)
    path("api/v1/shipments/", include("domains.shipments.urls")),

    # v1 나머지 엔드포인트
    path("api/v1/", include("api.v1.urls")),

    # Webhook (스윗트래커 등)
    path(
        "api/v1/webhooks/shipments/<str:carrier>/",
        ShipmentWebhookAPI.as_view(),
        name="shipment-webhook-root",
    ),

    # 루트 → 문서
    path("", RedirectView.as_view(url="/api/docs/", permanent=False)),

    # 헬스체크
    path("healthz/", healthz),

    # 테스트용 OAuth 콜백(선택)
    path("oauth/callback", oauth_debug_callback),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

