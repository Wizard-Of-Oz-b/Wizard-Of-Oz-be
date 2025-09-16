from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from .models import User, SocialAccount

@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = ("email", "username", "role", "status", "is_staff")
    fieldsets = DjangoUserAdmin.fieldsets + (
        ("Extra", {"fields": ("nickname", "phone_number", "address", "status", "role")}),
    )

@admin.register(SocialAccount)
class SocialAccountAdmin(admin.ModelAdmin):
    list_display = ("provider", "provider_uid", "user", "created_at")
    search_fields = ("provider_uid", "user__email")
