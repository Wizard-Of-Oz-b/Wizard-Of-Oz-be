from django.contrib import admin
from .models import Admin, AdminLog

@admin.register(Admin)
class AdminAdmin(admin.ModelAdmin):
    list_display = ("id", "user_id", "role", "created_at")
    search_fields = ("user__email", "user__username")

@admin.register(AdminLog)
class AdminLogAdmin(admin.ModelAdmin):
    list_display = ("id", "admin_id", "action", "target_table", "target_id", "created_at")
    list_filter = ("action", "target_table")
    search_fields = ("description",)
