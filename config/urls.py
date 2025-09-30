from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include, re_path
from django.views.generic import RedirectView
from django.http import HttpResponse, JsonResponse
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from .views_oauth import oauth_start
from drf_spectacular.renderers import OpenApiJsonRenderer
from rest_framework.permissions import AllowAny

from domains.shipments.views import ShipmentWebhookAPI


def oauth_debug_callback(request):
    code = request.GET.get("code")
    state = request.GET.get("state")
    if not code:
        return HttpResponse("No 'code' in query", status=400)
    return HttpResponse(f"OK<br>code={code}<br>state={state}", content_type="text/html")


def healthz(_):
    return JsonResponse({"ok": True})


class OpenAPIV1JSON(SpectacularAPIView):
    permission_classes = [AllowAny]
    renderer_classes = [OpenApiJsonRenderer]

urlpatterns = [
    # Admin
    path("admin/", admin.site.urls),

    # OpenAPI / Swagger
    path("api/v1/schema/", SpectacularAPIView.as_view(), name="v1-schema")
,
    path("api/v1/docs/",   SpectacularSwaggerView.as_view(url_name="v1-schema"), name="v1-docs"),
    path("api/schema/",    SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/",      SpectacularSwaggerView.as_view(url_name="v1-schema"), name="docs"),

    # 슬래시 없는 접근 → 슬래시 있는 경로로 301 정규화
    re_path(r"^api/v1/schema$", RedirectView.as_view(url="/api/v1/schema/", permanent=True)),
    re_path(r"^api/v1/docs$",   RedirectView.as_view(url="/api/v1/docs/",   permanent=True)),
    re_path(r"^api/schema$",    RedirectView.as_view(url="/api/schema/",    permanent=True)),
    re_path(r"^api/docs$",      RedirectView.as_view(url="/api/docs/",      permanent=True)),

    # API v1 엔드포인트
    path("api/v1/", include("api.v1.urls")),

    # 웹훅
    path("api/v1/webhooks/shipments/<str:carrier>/",
         ShipmentWebhookAPI.as_view(), name="shipment-webhook-root"),

    # 루트 → 문서
    path("", RedirectView.as_view(url="/api/docs/", permanent=False)),

    # 헬스체크
    path("healthz/", healthz),


    path("oauth/start/<str:provider>/", oauth_start, name="oauth-start"),
]

if settings.DEBUG:
    # 개발 환경에서만 미디어/정적 파일 서빙
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

