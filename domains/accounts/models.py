from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    # ERD 맞춤: DB 컬럼명을 user_id로 저장 (Django 내부 필드명은 id)
    id = models.BigAutoField(primary_key=True, db_column="user_id")

    # AbstractUser 이미 username, email, password 등을 가짐
    # 이메일은 로그인 전환 전까지 unique만 보장(추후 이메일 로그인으로 바꿀 수 있음)
    email = models.EmailField(unique=True)

    nickname = models.CharField(max_length=150, blank=True)
    phone_number = models.CharField(max_length=50, blank=True)
    address = models.TextField(blank=True)
    status = models.CharField(max_length=20, default="active")  # active/inactive/deleted
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "users"
