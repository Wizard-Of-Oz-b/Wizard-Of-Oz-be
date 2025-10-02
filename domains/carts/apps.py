from django.apps import AppConfig


class CartsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "domains.carts"  # ← 여기!
    label = "carts"  # (선택) 앱 라벨, makemigrations carts 가능하게 유지
