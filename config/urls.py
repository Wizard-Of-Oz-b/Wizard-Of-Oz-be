# config/urls.py
from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView
from django.http import HttpResponse
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from domains.accounts.views_social import SocialLoginView, SocialUnlinkView

def oauth_debug_callback(request):
    code = request.GET.get("code")
    state = request.GET.get("state")
    if not code:
        return HttpResponse("No 'code' in query", status=400)
    return HttpResponse(f"OK<br>code={code}<br>state={state}", content_type="text/html")

urlpatterns = [
    # Django admin
    path("admin/", admin.site.urls),

    # OpenAPI 스키마 & Swagger UI (뷰 클래스 방식 유지)
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),

    # API v1 엔드포인트
    path("api/v1/", include("api.v1.urls")),

    # 임시 OAuth 콜백 (프론트 없이 code 테스트용)
    path("oauth/callback", oauth_debug_callback),

    # 루트 → Swagger로 리다이렉트
    path("", RedirectView.as_view(url="/api/docs", permanent=False)),
    path("api/v1/auth/social/<str:provider>/login", SocialLoginView.as_view(), name="social-login"),
    path("api/v1/auth/social/<str:provider>/unlink", SocialUnlinkView.as_view(), name="social-unlink"),

]
