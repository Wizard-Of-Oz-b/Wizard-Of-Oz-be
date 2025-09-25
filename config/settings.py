# config/settings.py

import os
from pathlib import Path
from datetime import timedelta
from dotenv import load_dotenv
from celery.schedules import crontab

# ──────────────────────────────────────────────────────────────────────────────
# Base & Env (환경별 .env 자동 로딩)
# ──────────────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent

# DJANGO_ENV 에 따라 .env.<DJANGO_ENV> → .env 순서로 로드
# 예) dev → .env.dev, prod → .env.prod
DJANGO_ENV = os.getenv("DJANGO_ENV", "dev").strip().lower()
env_file = BASE_DIR / f".env.{DJANGO_ENV}"
if env_file.exists():
    load_dotenv(env_file, override=True)

# 공통 키 보완용(.env). 이미 로드된 값은 유지(override=False)
common_env = BASE_DIR / ".env"
if common_env.exists():
    load_dotenv(common_env, override=False)

# ──────────────────────────────────────────────────────────────────────────────
# Core Settings
# ──────────────────────────────────────────────────────────────────────────────
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-secret")

# "1/true/yes/on" 다 허용 (대소문자 무시)
_DEBUG_RAW = os.getenv("DEBUG", "1")
DEBUG = str(_DEBUG_RAW).strip().lower() in ("1", "true", "yes", "on")

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
    "django_celery_beat",

    # 3rd party
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "django_filters",
    "drf_spectacular",
    "corsheaders",

    # Domain apps
    "domains.accounts",
    "domains.catalog",
    "domains.reviews",
    "domains.staff",
    "domains.orders",
    "domains.shipments",
    "domains.carts",
    "domains.payments",
    "domains.wishlists",
]

AUTH_USER_MODEL = "accounts.User"

# ──────────────────────────────────────────────────────────────────────────────
# Middleware
# ──────────────────────────────────────────────────────────────────────────────
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    # 다국어: SessionMiddleware 다음, CommonMiddleware 이전
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# ──────────────────────────────────────────────────────────────────────────────
# URL & Templates
# ──────────────────────────────────────────────────────────────────────────────
ROOT_URLCONF = "config.urls"
APPEND_SLASH = True

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
        "NAME": os.getenv("DB_NAME"),
        "USER": os.getenv("DB_USER"),
        "PASSWORD": os.getenv("DB_PASSWORD"),
        "HOST": os.getenv("DB_HOST"),
        "PORT": os.getenv("DB_PORT", "5432"),
        "CONN_MAX_AGE": int(os.getenv("DJANGO_DB_CONN_MAX_AGE", "60")),
        "OPTIONS": {"sslmode": os.getenv("DJANGO_DB_SSLMODE", "require")},
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ──────────────────────────────────────────────────────────────────────────────
# Internationalization
# ──────────────────────────────────────────────────────────────────────────────
LANGUAGE_CODE = "ko-kr"
TIME_ZONE = "Asia/Seoul"
USE_I18N = True
USE_TZ = True
LANGUAGES = [("ko", "Korean"), ("en", "English")]
LOCALE_PATHS = [BASE_DIR / "locale"]

# ──────────────────────────────────────────────────────────────────────────────
# Static & Media Files
# ──────────────────────────────────────────────────────────────────────────────
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

DEFAULT_PRODUCT_PLACEHOLDER_URL = "/static/img/product_placeholder.png"

# ──────────────────────────────────────────────────────────────────────────────
# DRF & OpenAPI
# ──────────────────────────────────────────────────────────────────────────────
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.AllowAny",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
    ],
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Fashion Shop API",
    "DESCRIPTION": "Shop / Admin endpoints with JWT (Bearer).",
    "VERSION": "1.0.0",
    "SCHEMA_PATH_PREFIX": r"/api/v1",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SECURITY": [{"BearerAuth": []}],
    "COMPONENTS": {
        "securitySchemes": {
            "BearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"},
        }
    },
    "DISABLE_ERRORS_AND_WARNINGS": True,
    "SWAGGER_UI_SETTINGS": {
        "deepLinking": True,
        "displayRequestDuration": True,
        "persistAuthorization": True,
    },
    "SERVERS": [{"url": "/"}],
    "ENUM_NAME_OVERRIDES": {
        "Status": "ShipmentStatusEnum",
        "LastEventStatus": "ShipmentLastEventStatusEnum",
    },
}

# ──────────────────────────────────────────────────────────────────────────────
# JWT (SimpleJWT)
# ──────────────────────────────────────────────────────────────────────────────
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=int(os.getenv("ACCESS_MIN", "60"))),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=int(os.getenv("REFRESH_DAYS", "7"))),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# ──────────────────────────────────────────────────────────────────────────────
# Security, CORS & CSRF
# ──────────────────────────────────────────────────────────────────────────────
COOKIE_SECURE = not DEBUG
SESSION_COOKIE_SECURE = COOKIE_SECURE
CSRF_COOKIE_SECURE = COOKIE_SECURE
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
CORS_ALLOW_CREDENTIALS = True

CSRF_TRUSTED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "https://localhost:3000",
    "http://127.0.0.1:3000",
]

# ──────────────────────────────────────────────────────────────────────────────
# OAuth & 3rd Party Services
# ──────────────────────────────────────────────────────────────────────────────
SOCIAL_OAUTH = {
    "google": {
        "client_id": os.getenv("GOOGLE_CLIENT_ID", ""),
        "client_secret": os.getenv("GOOGLE_CLIENT_SECRET", ""),
        "redirect_uri": os.getenv("OAUTH_REDIRECT_URI", ""),
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
        "client_id": os.getenv("KAKAO_CLIENT_ID", ""),
        "client_secret": os.getenv("KAKAO_CLIENT_SECRET", ""),
        "redirect_uri": os.getenv("KAKAO_REDIRECT_URI", ""),
        "token_url": "https://kauth.kakao.com/oauth/token",
        "userinfo_url": "https://kapi.kakao.com/v2/user/me",
    },
}

# Payment & Delivery Services
TOSS_CLIENT_KEY = os.getenv("TOSS_CLIENT_KEY", "")
TOSS_SECRET_KEY = os.getenv("TOSS_SECRET_KEY", "")
SHIPMENTS_NOTIFY_WEBHOOK = os.getenv("SHIPMENTS_NOTIFY_WEBHOOK")

# ──────────────────────────────────────────────────────────────────────────────
# Password Validation
# ──────────────────────────────────────────────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "domains.accounts.validators.PasswordComplexityValidator"},
]

# ──────────────────────────────────────────────────────────────────────────────
# Celery Configuration
# ──────────────────────────────────────────────────────────────────────────────
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")
_result_env = os.environ.get("CELERY_RESULT_BACKEND")
CELERY_RESULT_BACKEND = _result_env or None
CELERY_TIMEZONE = "Asia/Seoul"
CELERY_TASK_TIME_LIMIT = 60 * 10
CELERY_TASK_TRACK_STARTED = True
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_TASK_IGNORE_RESULT = True

CELERY_BEAT_SCHEDULE = {
    "poll-shipments-every-2min": {
        "task": "domains.shipments.tasks.poll_open_shipments",
        "schedule": 120.0,
        "args": [],
        "kwargs": {},
    },
}
