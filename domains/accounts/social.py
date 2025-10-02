import logging
import os

from django.conf import settings

import requests

logger = logging.getLogger(__name__)


class SocialAuthError(Exception):
    pass


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, getattr(settings, name, default))


def get_provider_keys(provider: str) -> dict:
    """제공자 키 정보 반환 (기존 _provider_config와 동일)"""
    return _provider_config(provider)


def _provider_config(provider: str) -> dict:
    p = provider.lower()
    # settings.SOCIAL_OAUTH 우선 사용
    so = getattr(settings, "SOCIAL_OAUTH", {})
    cfg = (so.get(p) or {}).copy()
    if cfg.get("client_id"):  # settings에 제대로 들어있으면 그대로 반환
        return cfg

    # settings에 없거나 비어있으면 env로 폴백
    if p == "google":
        return {
            "client_id": _env("GOOGLE_CLIENT_ID"),
            "client_secret": _env("GOOGLE_CLIENT_SECRET"),
            "redirect_uri": _env("GOOGLE_REDIRECT_URI"),
            "token_url": "https://oauth2.googleapis.com/token",
            "userinfo_url": "https://openidconnect.googleapis.com/v1/userinfo",
        }
    if p == "naver":
        return {
            "client_id": _env("NAVER_CLIENT_ID"),
            "client_secret": _env("NAVER_CLIENT_SECRET"),
            "redirect_uri": _env("NAVER_REDIRECT_URI"),
            "token_url": "https://nid.naver.com/oauth2.0/token",
            "userinfo_url": "https://openapi.naver.com/v1/nid/me",
        }
    if p == "kakao":
        cid = _env("KAKAO_CLIENT_ID") or _env("KAKAO_REST_API_KEY")  # 둘 다 지원
        return {
            "client_id": cid,
            "client_secret": _env("KAKAO_CLIENT_SECRET"),
            "redirect_uri": _env("KAKAO_REDIRECT_URI"),
            "token_url": "https://kauth.kakao.com/oauth/token",
            "userinfo_url": "https://kapi.kakao.com/v2/user/me",
        }
    raise SocialAuthError(f"Unsupported provider: {provider}")


# -------------------------
# OAuth 인가 URL 생성
# -------------------------
def generate_authorize_url(provider: str, request) -> str:
    """OAuth 인가 URL 생성"""
    cfg = _provider_config(provider)
    client_id = cfg["client_id"]

    # 콜백 URL 생성 (현재 도메인 기준)
    from django.urls import reverse

    callback_url = request.build_absolute_uri(
        reverse("accounts_auth:social-callback", kwargs={"provider": provider})
    )
    redirect_uri = callback_url

    # state 파라미터 생성 (CSRF 보호)
    import secrets

    state = secrets.token_urlsafe(32)

    if provider == "google":
        scope = "openid email profile"
        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": scope,
            "response_type": "code",
            "state": state,
            "access_type": "offline",
            "prompt": "consent",
        }
        base_url = "https://accounts.google.com/o/oauth2/v2/auth"

    elif provider == "naver":
        scope = "name,email,profile_image"
        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "state": state,
            "scope": scope,
        }
        base_url = "https://nid.naver.com/oauth2.0/authorize"

    elif provider == "kakao":
        scope = "profile_nickname,account_email"
        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "state": state,
            "scope": scope,
        }
        base_url = "https://kauth.kakao.com/oauth/authorize"

    else:
        raise SocialAuthError(f"Unsupported provider: {provider}")

    # URL 파라미터 생성
    import urllib.parse

    query_string = urllib.parse.urlencode(params)
    return f"{base_url}?{query_string}"


# -------------------------
# 코드 → 토큰 교환
# -------------------------
def exchange_code_for_tokens(
    provider: str, code: str, redirect_uri: str, state: str = ""
) -> dict:
    cfg = _provider_config(provider)
    timeout = 10

    if provider == "google":
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": cfg["client_id"],
            "client_secret": cfg["client_secret"],
            "redirect_uri": redirect_uri or cfg["redirect_uri"],
        }
        resp = requests.post(cfg["token_url"], data=data, timeout=timeout)

    elif provider == "naver":
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": cfg["client_id"],
            "client_secret": cfg["client_secret"],
            "redirect_uri": redirect_uri or cfg["redirect_uri"],
        }
        if state:
            data["state"] = state
        resp = requests.post(cfg["token_url"], data=data, timeout=timeout)

    elif provider == "kakao":
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": cfg["client_id"],
            "redirect_uri": redirect_uri or cfg["redirect_uri"],
        }
        # 콘솔에서 Client Secret 사용 중일 때만 포함
        if cfg.get("client_secret"):
            data["client_secret"] = cfg["client_secret"]
        resp = requests.post(cfg["token_url"], data=data, timeout=timeout)

    else:
        raise SocialAuthError(f"Unsupported provider: {provider}")

    try:
        body = resp.json()
    except Exception:
        body = {"_raw": resp.text}

    if resp.status_code != 200 or "access_token" not in body:
        logger.warning(
            "%s token error: status=%s body=%s", provider, resp.status_code, body
        )
        # 가능한 한 원인 문구를 돌려보냄
        msg = body.get("error_description") or body.get("error") or body
        raise SocialAuthError(str(msg))

    return body


# -------------------------
# 유저 프로필 조회 → 표준화
# 반환: {"provider_uid", "email", "name", "nickname", "picture"}
# -------------------------
def fetch_userinfo(provider: str, access_token: str) -> dict:
    cfg = _provider_config(provider)
    timeout = 10
    headers = {"Authorization": f"Bearer {access_token}"}

    if provider == "naver":
        r = requests.get(cfg["userinfo_url"], headers=headers, timeout=timeout)
        try:
            data = r.json()
        except Exception:
            data = {"_raw": r.text}
        if r.status_code != 200 or data.get("resultcode") != "00":
            raise SocialAuthError(f"Naver userinfo error: {data}")
        resp = data.get("response", {}) or {}
        return {
            "provider": "naver",
            "provider_uid": str(resp.get("id") or ""),
            "email": resp.get("email"),
            "name": resp.get("name") or resp.get("nickname"),
            "nickname": resp.get("nickname") or resp.get("name"),
            "picture": resp.get("profile_image"),
        }

    if provider == "google":
        r = requests.get(cfg["userinfo_url"], headers=headers, timeout=timeout)
        try:
            data = r.json()
        except Exception:
            data = {"_raw": r.text}
        if r.status_code != 200 or not data.get("sub"):
            raise SocialAuthError(f"Google userinfo error: {data}")
        return {
            "provider": "google",
            "provider_uid": str(data.get("sub")),
            "email": data.get("email"),
            "name": data.get("name") or data.get("given_name"),
            "nickname": data.get("name"),
            "picture": data.get("picture"),
        }

    if provider == "kakao":
        r = requests.get(cfg["userinfo_url"], headers=headers, timeout=timeout)
        try:
            data = r.json()
        except Exception:
            data = {"_raw": r.text}
        if r.status_code != 200 or not data.get("id"):
            raise SocialAuthError(f"Kakao userinfo error: {data}")

        kakao_account = data.get("kakao_account", {}) or {}
        profile = kakao_account.get("profile", {}) or {}
        email = kakao_account.get("email")
        nickname = profile.get("nickname")
        picture = profile.get("profile_image_url") or profile.get("thumbnail_image_url")

        return {
            "provider": "kakao",
            "provider_uid": str(data.get("id")),
            "email": email,
            "name": nickname,
            "nickname": nickname,
            "picture": picture,
        }

    raise SocialAuthError(f"Unsupported provider: {provider}")
