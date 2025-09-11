# config/settings.py
import os
from pathlib import Path
from datetime import timedelta
from dotenv import load_dotenv

# ──────────────────────────────────────────────────────────────────────────────
# Base & Env
# ──────────────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-secret")
DEBUG = os.getenv("DEBUG", "1") == "1"

ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")

# ──────────────────────────────────────────────────────────────────────────────
# Applications
# ──────────────────────────────────────────────────────────────────────────────
INSTALLED_APPS = [
    # Django
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # 3rd party
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",  # 로그아웃/회전 블랙리스트
    "django_filters",
    "drf_spectacular",

    # Domain apps
    "domains.accounts",   # AUTH_USER_MODEL = "accounts.User"
    "domains.catalog",
    "domains.orders",
    "domains.reviews",
    "domains.staff",
]

AUTH_USER_MODEL = "accounts.User"

# ──────────────────────────────────────────────────────────────────────────────
# Middleware
# ──────────────────────────────────────────────────────────────────────────────
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    # 다국어: SessionMiddleware 다음, CommonMiddleware 이전
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",

    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# ──────────────────────────────────────────────────────────────────────────────
# Database (PostgreSQL)
# ──────────────────────────────────────────────────────────────────────────────
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("POSTGRES_DB", "shopapi"),
        "USER": os.getenv("POSTGRES_USER", "shop"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", "secret"),
        "HOST": os.getenv("POSTGRES_HOST", "127.0.0.1"),
        "PORT": os.getenv("POSTGRES_PORT", "5432"),
        "CONN_MAX_AGE": 60,
        "ATOMIC_REQUESTS": True,
        "OPTIONS": {},
    }
}

# ──────────────────────────────────────────────────────────────────────────────
# Internationalization (ko/en)
# ──────────────────────────────────────────────────────────────────────────────
LANGUAGE_CODE = "ko-kr"          # 폴백 언어
TIME_ZONE = "Asia/Seoul"
USE_I18N = True
USE_TZ = True

LANGUAGES = [
    ("ko", "Korean"),
    ("en", "English"),
]
LOCALE_PATHS = [BASE_DIR / "locale"]

# ──────────────────────────────────────────────────────────────────────────────
# Static
# ──────────────────────────────────────────────────────────────────────────────
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ──────────────────────────────────────────────────────────────────────────────
# DRF & OpenAPI
# ──────────────────────────────────────────────────────────────────────────────
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    # API 기본 접근 정책(문서 페이지/헬스체크 등을 위해 AllowAny, 엔드포인트별로 개별 지정 권장)
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.AllowAny",),

    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_FILTER_BACKENDS": ("django_filters.rest_framework.DjangoFilterBackend",),
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Fashion Shop API",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SERVERS": [{"url": "/"}],
}

# ──────────────────────────────────────────────────────────────────────────────
# JWT (SimpleJWT)
# ──────────────────────────────────────────────────────────────────────────────
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=int(os.getenv("ACCESS_MIN", "15"))),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=int(os.getenv("REFRESH_DAYS", "7"))),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
    # 운영에서 키는 반드시 .env 로 관리
    # "SIGNING_KEY": SECRET_KEY,  # 기본은 Django SECRET_KEY 사용
}

# ──────────────────────────────────────────────────────────────────────────────
# Security / Cookies
# ──────────────────────────────────────────────────────────────────────────────
# 로컬 개발 편의: DEBUG일 땐 쿠키 secure 비활성화
COOKIE_SECURE = not DEBUG
SESSION_COOKIE_SECURE = COOKIE_SECURE
CSRF_COOKIE_SECURE = COOKIE_SECURE

CSRF_TRUSTED_ORIGINS = os.getenv(
    "CSRF_TRUSTED_ORIGINS",
    "http://localhost:3000,https://localhost:3000,http://127.0.0.1:3000",
).split(",")

# (선택) CORS 사용 시
# INSTALLED_APPS += ["corsheaders"]
# MIDDLEWARE = ["corsheaders.middleware.CorsMiddleware"] + MIDDLEWARE
# CORS_ALLOWED_ORIGINS = [
#     "http://localhost:3000",
#     "http://127.0.0.1:3000",
# ]

# config/settings.py (하단 아무 곳)
SOCIAL_OAUTH = {
    "google": {
        "client_id": os.getenv("GOOGLE_CLIENT_ID", ""),
        "client_secret": os.getenv("GOOGLE_CLIENT_SECRET", ""),
        "redirect_uri": os.getenv("OAUTH_REDIRECT_URI", ""),  # 공통 URI 쓰는 전략이면 이걸로 통일
        "token_url": "https://oauth2.googleapis.com/token",
        "userinfo_url": "https://openidconnect.googleapis.com/v1/userinfo",
    },
    "naver": {
        "client_id": os.getenv("NAVER_CLIENT_ID", ""),
        "client_secret": os.getenv("NAVER_CLIENT_SECRET", ""),
        "redirect_uri": os.getenv("OAUTH_REDIRECT_URI", ""),
        "token_url": "https://nid.naver.com/oauth2.0/token",
        "userinfo_url": "https://openapi.naver.com/v1/nid/me",
    },
    "kakao": {
        "client_id": os.getenv("KAKAO_CLIENT_ID", ""),          # ✅ clinet_id 오타 수정 + 변수명 통일
        "client_secret": os.getenv("KAKAO_CLIENT_SECRET", ""),
        "redirect_uri": os.getenv("KAKAO_REDIRECT_URI", ""),    # ✅ 원하면 카카오도 공통 URI로
        "token_url": "https://kauth.kakao.com/oauth/token",      # ✅ 네이버 URL이 들어가 있었음
        "userinfo_url": "https://kapi.kakao.com/v2/user/me",     # ✅ 네이버 URL이 들어가 있었음
    },
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "domains.accounts.validators.PasswordComplexityValidator"},
    # (원하면 추가) {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    # (원하면 추가) {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    # MinimumLength/Numeric은 우리 커스텀에 포함되어 있으니 보통 안 넣습니다.
]