from django.conf import settings
from django.db import models
from domains.accounts.models import UserRole

class AdminRole(models.TextChoices):
    SUPER = "super", "Super"
    MANAGER = "manager", "Manager"
    CS = "cs", "CS"

class Admin(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="staff_admin",
    )
    role = models.CharField(max_length=20, choices=UserRole.choices, default=UserRole.MANAGER)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "staff_admins"
        verbose_name = "admin"
        verbose_name_plural = "admins"

    def __str__(self):
        return f"{self.user_id}:{self.role}"

class AdminAction(models.TextChoices):
    CREATE = "CREATE", "CREATE"
    UPDATE = "UPDATE", "UPDATE"
    DELETE = "DELETE", "DELETE"
    LOGIN  = "LOGIN",  "LOGIN"

class AdminLog(models.Model):
    admin = models.ForeignKey("Admin", null=True, blank=True,
                              on_delete=models.SET_NULL, related_name="logs")
    action = models.CharField(max_length=20, choices=AdminAction.choices)
    target_table = models.CharField(max_length=50)
    target_id = models.IntegerField(null=True, blank=True)
    description = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["admin"]),
            models.Index(fields=["action"]),
            models.Index(fields=["target_table", "target_id"]),
            models.Index(fields=["created_at"]),
        ]
