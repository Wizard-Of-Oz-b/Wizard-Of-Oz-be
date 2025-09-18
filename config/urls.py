# config/urls.py
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView
from django.http import HttpResponse, JsonResponse
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

# 소셜 로그인 뷰 (기존 그대로)
from domains.accounts.views_social import SocialLoginView, SocialUnlinkView  # noqa: F401
from domains.shipments.views import ShipmentWebhookAPI


def oauth_debug_callback(request):
    code = request.GET.get("code")
    state = request.GET.get("state")
    if not code:
        return HttpResponse("No 'code' in query", status=400)
    return HttpResponse(f"OK<br>code={code}<br>state={state}", content_type="text/html")


def healthz(_):
    return JsonResponse({"ok": True})


urlpatterns = [
    # Django admin
    path("admin/", admin.site.urls),

    # OpenAPI 스키마 & Swagger UI (뷰 클래스 방식 유지)
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),

    # API v1 엔드포인트
    path("api/v1/", include("api.v1.urls")),                 # 기존 유지
    path("api/v1/shipments/", include("domains.shipments.urls")),  # 목록/상세/동기화

    # 🔒 소셜 로그인
    path("api/v1/auth/social/<str:provider>/login", SocialLoginView.as_view(), name="social-login"),

    # ✅ 최종 명세 경로: /api/v1/webhooks/shipments/{carrier}
    path(
        "api/v1/webhooks/shipments/<str:carrier>/",
        ShipmentWebhookAPI.as_view(),
        name="shipment-webhook-root",
    ),

    # 임시 OAuth 콜백 & 루트 리다이렉트
    path("oauth/callback", oauth_debug_callback),

    # 루트 → Swagger로 리다이렉트
    path("", RedirectView.as_view(url="/api/docs", permanent=False)),
    path("api/v1/auth/social/<str:provider>/login", SocialLoginView.as_view(), name="social-login"),
    path("api/v1/auth/social/<str:provider>/unlink", SocialUnlinkView.as_view(), name="social-unlink"),
    static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    # 헬스체크
    path("healthz/", healthz),
]

def healthz(_): return JsonResponse({"ok": True})
urlpatterns += [path("healthz/", healthz)]