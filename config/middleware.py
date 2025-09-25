# config/middleware.py

from django.utils.deprecation import MiddlewareMixin

class StripCSRFCookieMiddleware(MiddlewareMixin):
    """(비활성) 과거 디버그용. 현재는 아무 동작도 하지 않음."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        resp = self.get_response(request)
        resp['X-StripCSRFCookie'] = 'disabled'
        return resp

class ForceInsecureCSRFMiddleware(MiddlewareMixin):
    """모든 응답에서 csrftoken 쿠키의 Secure 속성을 강제로 False로 만든다."""
    def __init__(self, get_response):
        self.get_response = get_response
    def __call__(self, request):
        resp = self.get_response(request)
        c = resp.cookies.get("csrftoken")
        if c:
            c["secure"] = False
        return resp