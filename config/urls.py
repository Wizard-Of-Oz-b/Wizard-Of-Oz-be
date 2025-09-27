from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView
from django.http import HttpResponse, JsonResponse
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from drf_spectacular.renderers import OpenApiJsonRenderer
from rest_framework.permissions import AllowAny

# 소셜 로그인 뷰 (기존 유지)
from domains.accounts.views_social import SocialLoginView, SocialUnlinkView
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
    # Django admin
    path("admin/", admin.site.urls),

    # ✅ v1 스키마 & Swagger (둘 다 동일 스키마 보게)
    path("api/v1/schema/", OpenAPIV1JSON.as_view(), name="v1-schema"),
    path("api/v1/docs/", SpectacularSwaggerView.as_view(url_name="v1-schema"), name="v1-docs"),

    # ✅ 글로벌 경로도 v1 스키마로 통일 (JSON 고정)
    path("api/schema/", OpenAPIV1JSON.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="v1-schema"), name="docs"),

    # API v1 엔드포인트 (그대로 유지)
    path("api/v1/shipments/", include("domains.shipments.urls")),
    path("api/v1/", include("api.v1.urls")),

    # 🔒 소셜 로그인 (그대로)
    path("api/v1/auth/social/<str:provider>/login", SocialLoginView.as_view(), name="social-login"),
    path("api/v1/auth/social/<str:provider>/unlink", SocialUnlinkView.as_view(), name="social-unlink"),

    # ✅ 최종 명세 경로 (그대로)
    path(
        "api/v1/webhooks/shipments/<str:carrier>/",
        ShipmentWebhookAPI.as_view(),
        name="shipment-webhook-root",
    ),

    # 루트 리다이렉트는 원하면 /api/v1/docs 로 바꿔도 됨
    path("oauth/callback", oauth_debug_callback),
    path("", RedirectView.as_view(url="/api/docs", permanent=False)),

    # 헬스체크
    path("healthz/", healthz),
]


if settings.DEBUG:
    # 개발 환경에서만 미디어/정적 파일 서빙
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

