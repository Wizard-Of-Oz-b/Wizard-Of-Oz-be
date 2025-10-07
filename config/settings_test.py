from .settings import *  # noqa: F403, F401

# ──────────────────────────────────────────────
# DB: SQLite 인메모리 (Postgres 없이 테스트용)
# ──────────────────────────────────────────────
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# ──────────────────────────────────────────────
# 빠른 테스트 전용 설정
# ──────────────────────────────────────────────
DEBUG = False
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# Celery / Cache / Redis 등 실제 연결 비활성화
CELERY_TASK_ALWAYS_EAGER = True
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}
