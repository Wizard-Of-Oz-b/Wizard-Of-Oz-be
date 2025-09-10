from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from .models import User

@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = ("id", "username", "email", "is_staff", "status", "date_joined")
    fieldsets = DjangoUserAdmin.fieldsets + (
        ("Profile", {"fields": ("nickname", "phone_number", "address", "status")}),
    )
