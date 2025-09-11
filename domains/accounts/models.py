# models.py (권장 형태)
from django.conf import settings
from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    id = models.BigAutoField(primary_key=True, db_column="user_id")
    email = models.EmailField(unique=True)
    nickname = models.CharField(max_length=150, blank=True)
    phone_number = models.CharField(max_length=50, blank=True)
    address = models.TextField(blank=True)
    status = models.CharField(max_length=20, default="active")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "users"

class SocialAccount(models.Model):
    PROVIDER_CHOICES = [("google", "Google"), ("naver", "Naver"), ("kakao", "Kakao")]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="social_accounts")
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES)
    provider_uid = models.CharField(max_length=128)
    email = models.EmailField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = (("provider", "provider_uid"),)
        indexes = [models.Index(fields=["provider", "provider_uid"])]

    def __str__(self):
        return f"{self.provider}:{self.provider_uid} -> {self.user_id}"
