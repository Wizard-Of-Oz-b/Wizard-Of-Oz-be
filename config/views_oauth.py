import os, secrets, urllib.parse
from django.conf import settings
from django.http import HttpResponseBadRequest, HttpResponseRedirect

def oauth_start(request, provider: str):
    provider = provider.lower()
    state = secrets.token_urlsafe(24)
    request.session['oauth_state'] = state

    if provider == "kakao":
        client_id = os.getenv("KAKAO_CLIENT_ID")
        redirect_uri = os.getenv("KAKAO_REDIRECT_URI")
        auth = "https://kauth.kakao.com/oauth/authorize"
        qs = {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "state": state,
        }

    elif provider == "google":
        client_id = os.getenv("GOOGLE_CLIENT_ID")
        redirect_uri = os.getenv("GOOGLE_REDIRECT_URI")
        auth = "https://accounts.google.com/o/oauth2/v2/auth"
        qs = {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": "openid email profile",
            "access_type": "online",
            "include_granted_scopes": "true",
            "prompt": "consent",
            "state": state,
        }

    elif provider == "naver":
        client_id = os.getenv("NAVER_CLIENT_ID")
        redirect_uri = os.getenv("NAVER_REDIRECT_URI")
        auth = "https://nid.naver.com/oauth2.0/authorize"
        qs = {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "state": state,
        }
    else:
        return HttpResponseBadRequest("unknown provider")

    url = f"{auth}?{urllib.parse.urlencode(qs)}"
    return HttpResponseRedirect(url)

