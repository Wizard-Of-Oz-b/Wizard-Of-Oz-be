from django.apps import AppConfig


class WishlistsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "domains.wishlists"
    label = "wishlists"  # 충돌 방지
