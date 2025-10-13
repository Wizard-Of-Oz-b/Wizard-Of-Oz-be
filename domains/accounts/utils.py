from django.conf import settings
from django import get_version
import re


def refresh_cookie_kwargs(debug: bool = False) -> dict:
    """
    리프레시 쿠키 속성 통일:
    - Path: "/"  (API 전체 경로에 전송되도록)
    - SameSite: "None"  (크로스사이트 허용, withCredentials와 함께 사용)
    - Secure: settings.AUTH_COOKIE_SECURE(기본 True) / 없으면 not debug
    - Domain: (선택) settings.AUTH_COOKIE_DOMAIN 사용, 없으면 host-only
    - Max-Age: settings.AUTH_COOKIE_MAX_AGE(초) / 없으면 14일
    - Django 5.1 이상에서는 SameSite=None 쿠키의 partitioned 속성 추가
    """
    is_dev = debug or settings.DEBUG

    kwargs = dict(
        httponly=True,
        secure=getattr(settings, "AUTH_COOKIE_SECURE", not is_dev),
        samesite="Lax" if is_dev else "None",
        path=getattr(settings, "AUTH_COOKIE_PATH", "/"),
        domain=getattr(settings, "AUTH_COOKIE_DOMAIN", None),
        max_age=getattr(settings, "AUTH_COOKIE_MAX_AGE", 14 * 24 * 3600),
    )

    # Django 5.1 이상이면 partitioned 쿠키 추가
    version_match = re.match(r"(\d+)\.(\d+)", get_version())
    if version_match and tuple(map(int, version_match.groups())) >= (5, 1):
        kwargs["partitioned"] = True

    return kwargs
