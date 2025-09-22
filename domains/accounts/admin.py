# domains/accounts/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, SocialAccount
from .models import UserAddress

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("email", "username", "role", "status", "is_staff", "is_superuser", "created_at")
    list_filter = ("role", "status", "is_staff", "is_superuser")
    search_fields = ("email", "username", "nickname")
    ordering = ("-created_at",)

    readonly_fields = ("created_at", "updated_at", "is_staff")

    fieldsets = (
        ("기본 정보", {"fields": ("email", "username", "password")}),
        ("개인 정보", {"fields": ("first_name", "last_name", "nickname", "phone_number", "address")}),
        ("권한", {
            "fields": ("role", "is_active", "is_superuser", "groups", "user_permissions"),
            "description": "role을 바꾸면 저장 시 is_staff가 자동 동기화됩니다.",
        }),
        ("중요 일시", {"fields": ("last_login", "created_at", "updated_at")}),
    )

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "username", "password1", "password2", "role", "is_active"),
        }),
    )

@admin.register(SocialAccount)
class SocialAccountAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "provider", "provider_uid", "email", "created_at")
    search_fields = ("provider_uid", "email", "user__email")


@admin.register(UserAddress)
class UserAddressAdmin(admin.ModelAdmin):
    list_display = ("address_id","user","recipient","is_default","is_active","created_at")
    list_filter = ("is_default","is_active")
    search_fields = ("user__email","recipient","address1","postcode")
