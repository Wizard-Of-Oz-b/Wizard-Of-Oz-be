from django.conf import settings

def refresh_cookie_kwargs(debug: bool = False) -> dict:
    """
    리프레시 쿠키 속성 통일:
    - Path: "/"  (API 전체 경로에 전송되도록)
    - SameSite: "None"  (크로스사이트 허용, withCredentials와 함께 사용)
    - Secure: settings.AUTH_COOKIE_SECURE(기본 True) / 없으면 not debug
    - Domain: (선택) settings.AUTH_COOKIE_DOMAIN 사용, 없으면 host-only
    - Max-Age: settings.AUTH_COOKIE_MAX_AGE(초) / 없으면 14일
    """
    return dict(
        httponly=True,
        secure=getattr(settings, "AUTH_COOKIE_SECURE", not debug),
        samesite=getattr(settings, "AUTH_COOKIE_SAMESITE", "None"),
        path=getattr(settings, "AUTH_COOKIE_PATH", "/"),
        domain=getattr(settings, "AUTH_COOKIE_DOMAIN", None),  # 예: "ozshop.duckdns.org" 또는 ".ozshop.duckdns.org"
        max_age=getattr(settings, "AUTH_COOKIE_MAX_AGE", 14 * 24 * 3600),
    )
