import os
from pathlib import Path
from datetime import timedelta
from dotenv import load_dotenv
from celery.schedules import crontab

# Base & Env
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")  # .env 로드

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-secret")
_DEBUG_RAW = os.getenv("DEBUG", "1")
DEBUG = str(_DEBUG_RAW).strip().lower() in ("1", "true", "yes", "on")
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")

# Applications
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
]

AUTH_USER_MODEL = "accounts.User"

# Middleware
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
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

# Database (PostgreSQL)
def env_multi(*keys, default=None):
    for k in keys:
        v = os.getenv(k)
        if v:
            return v
    return default

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env_multi("DB_NAME", "POSTGRES_DB", default="shopapi"),
        "USER": env_multi("DB_USER", "POSTGRES_USER", default="postgres"),
        "PASSWORD": env_multi("DB_PASSWORD", "POSTGRES_PASSWORD", default=""),
        "HOST": env_multi("DB_HOST", "POSTGRES_HOST", default="127.0.0.1"),
        "PORT": env_multi("DB_PORT", "POSTGRES_PORT", default="5432"),
    }
}

# I18N
LANGUAGE_CODE = "ko-kr"
TIME_ZONE = "Asia/Seoul"
USE_I18N = True
USE_TZ = True
LANGUAGES = [("ko", "Korean"), ("en", "English")]
LOCALE_PATHS = [BASE_DIR / "locale"]

# Static / Media
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# DRF & OpenAPI
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.AllowAny",),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_FILTER_BACKENDS": ("django_filters.rest_framework.DjangoFilterBackend",),
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Fashion Shop API",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SERVERS": [{"url": "/"}],
    "ENUM_NAME_OVERRIDES": {
        "Status": "ShipmentStatusEnum",
        "LastEventStatus": "ShipmentLastEventStatusEnum",
    },
}

# JWT (SimpleJWT)
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=int(os.getenv("ACCESS_MIN", "15"))),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=int(os.getenv("REFRESH_DAYS", "7"))),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# Security / CORS / CSRF
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

# 한 곳에서만 정의 (중복 제거)
CSRF_TRUSTED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "https://localhost:3000",
    "http://127.0.0.1:3000",
]

# OAuth / 3rd Party
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

TOSS_CLIENT_KEY = os.getenv("TOSS_CLIENT_KEY", "")
TOSS_SECRET_KEY = os.getenv("TOSS_SECRET_KEY", "")

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "domains.accounts.validators.PasswordComplexityValidator"},
]

# Celery
CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", CELERY_BROKER_URL)
CELERY_TIMEZONE = "Asia/Seoul"
CELERY_TASK_TIME_LIMIT = 60 * 10
CELERY_TASK_TRACK_STARTED = True
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"

CELERY_BEAT_SCHEDULE = {
    "poll-open-shipments-30m": {
        "task": "domains.shipments.tasks.poll_open_shipments",
        "schedule": crontab(minute="*/30"),
    },
}
