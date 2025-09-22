# domains/accounts/models.py
from __future__ import annotations

import uuid
from django.conf import settings
from django.db import models
from django.contrib.auth.models import AbstractUser


# ----- Enums -------------------------------------------------
class UserStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    INACTIVE = "inactive", "Inactive"
    DELETED = "deleted", "Deleted"


class UserRole(models.TextChoices):
    USER    = "user", "User"
    MANAGER = "manager", "Manager"
    ADMIN   = "admin", "Admin"
    CS      = "cs", "CS"


class ProviderType(models.TextChoices):
    GOOGLE = "google", "Google"
    NAVER  = "naver", "Naver"
    KAKAO  = "kakao", "Kakao"


# ----- Models ------------------------------------------------
class User(AbstractUser):
    """
    커스텀 유저 모델
    - PK: UUID (db_column='user_id')
    - email: unique
    - role/status 필드 추가
    - role 'admin' 이면 장고 어드민 접근(is_staff=True) 자동 허용
    """
    # ✅ 기존 코드와의 호환을 위해 별칭 유지 (User.Role.choices 사용 가능)
    Role = UserRole

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column="user_id",
    )

    # AbstractUser 기본 필드:
    # username(Unique), first_name, last_name, email, is_staff, is_active, is_superuser 등
    email = models.EmailField(max_length=254, unique=True)

    nickname = models.CharField(max_length=150, blank=True)
    phone_number = models.CharField(max_length=50, blank=True)
    address = models.TextField(blank=True)

    status = models.CharField(
        max_length=20,
        choices=UserStatus.choices,
        default=UserStatus.ACTIVE,
    )
    role = models.CharField(
        max_length=16,
        choices=UserRole.choices,
        default=UserRole.USER,  # 일반 고객 기본
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "users"
        indexes = [
            models.Index(fields=["email"]),
            models.Index(fields=["status", "role"]),
        ]
        constraints = [
            models.CheckConstraint(
                name="users_role_allowed_values",
                check=models.Q(role__in=[c for c, _ in UserRole.choices]),
            ),
        ]

    # ---- 편의 프로퍼티 ----
    @property
    def is_admin_role(self) -> bool:
        return self.role == UserRole.ADMIN

    @property
    def is_manager_role(self) -> bool:
        return self.role == UserRole.MANAGER

    @property
    def is_cs_role(self) -> bool:
        return self.role == UserRole.CS

    def __str__(self) -> str:
        # email 우선, 없으면 username
        return self.email or self.username

    # ---- 역할 ↔ 장고 관리자 플래그 동기화 ----
    def save(self, *args, **kwargs):
        """
        - superuser 는 항상 is_staff=True (장고 규약)
        - role == admin 이면 is_staff=True
        - manager/cs/user 는 is_staff=False
          (※ manager도 장고 어드민 접속 허용하려면 or 조건에 MANAGER 추가)
        """
        should_staff = self.is_superuser or self.role == UserRole.ADMIN
        if self.is_staff != should_staff:
            self.is_staff = should_staff
        super().save(*args, **kwargs)


class SocialAccount(models.Model):
    """
    소셜 계정 연결 정보
    - (provider, provider_uid) 유니크
    - (user, provider) 유니크 : 동일 유저에 같은 provider 중복 방지
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column="social_id",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="social_accounts",
        db_column="user_id",
    )
    provider = models.CharField(max_length=20, choices=ProviderType.choices)
    provider_uid = models.CharField(max_length=128)
    email = models.EmailField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "social_accounts"
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "provider_uid"],
                name="uq_social_provider_uid",
            ),
            models.UniqueConstraint(
                fields=["user", "provider"],
                name="uq_social_user_provider",
            ),
        ]
        indexes = [
            models.Index(fields=["provider", "provider_uid"]),
            models.Index(fields=["user", "provider"]),
        ]

    def __str__(self) -> str:
        # FK의 raw id 접근은 <fieldname>_id 로 가능 (여기선 user_id)
        return f"{self.provider}:{self.provider_uid} -> {self.user_id}"


# ----- AddressBook ------------------------------------------------
from django.db.models import Q

class UserAddress(models.Model):
    address_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="addresses")
    recipient  = models.CharField(max_length=50)
    phone      = models.CharField(max_length=20)
    postcode   = models.CharField(max_length=10)
    address1   = models.CharField(max_length=200)                 # 도로명/지번
    address2   = models.CharField(max_length=200, default="", blank=True)  # 상세
    is_default = models.BooleanField(default=False)
    is_active  = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "user_addresses"
        indexes = [models.Index(fields=["user", "-created_at"])]
        constraints = [
            # 사용자당 기본배송지 1개만 허용
            models.UniqueConstraint(fields=["user"], condition=Q(is_default=True), name="uq_user_default_address"),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} / {self.recipient} / {self.address1}"
