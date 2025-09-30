# domains/accounts/serializers.py
from __future__ import annotations

import uuid
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.hashers import check_password
from django.contrib.auth.password_validation import validate_password
from django.utils.text import slugify
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .models import SocialAccount

User = get_user_model()


# ─────────────────────────────────────────────────────────────
# 공용/관리용
# ─────────────────────────────────────────────────────────────
class UserRoleUpdateSerializer(serializers.ModelSerializer):
    role = serializers.ChoiceField(choices=[c[0] for c in User.Role.choices])

    class Meta:
        model = User
        fields = ["role"]

    def validate_role(self, value):
        valid = [c[0] for c in User.Role.choices]
        if value not in valid:
            raise serializers.ValidationError(f"허용되지 않는 역할입니다: {value}")
        return value


class TokenResponseSerializer(serializers.Serializer):
    access = serializers.CharField()


class TokenPairResponseSerializer(serializers.Serializer):
    """access + refresh 동시 응답용 (스키마 문서화)"""
    access = serializers.CharField()
    refresh = serializers.CharField()


def normalize_email(value: str) -> str:
    v = (value or "").strip()
    v = BaseUserManager.normalize_email(v)
    return v.lower()


def username_from_email(email: str) -> str:
    base = (email or "").split("@")[0]
    base = slugify(base) or "user"
    return f"{base}_{uuid.uuid4().hex[:6]}"


# ─────────────────────────────────────────────────────────────
# 회원가입 / 로그인
# ─────────────────────────────────────────────────────────────
class RegisterSerializer(serializers.ModelSerializer):
    """회원가입: username이 없으면 이메일 기반으로 자동 생성"""
    password = serializers.CharField(write_only=True, min_length=8, max_length=16, trim_whitespace=False)
    # username은 옵션 (없으면 자동 생성)
    username = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = User
        fields = ("email", "username", "password", "nickname", "phone_number", "address")

    def validate(self, data):
        email = normalize_email(data.get("email", ""))
        if not email:
            raise serializers.ValidationError({"email": "This field is required."})
        temp_user = User(email=email)
        validate_password(data["password"], user=temp_user)
        data["email"] = email
        return data

    def create(self, validated):
        email = validated["email"]
        username = (validated.get("username") or "").strip() or username_from_email(email)
        password = validated["password"]

        user = User(
            email=email,
            username=username,
            nickname=validated.get("nickname", ""),
            phone_number=validated.get("phone_number", ""),
            address=validated.get("address", ""),
        )
        user.set_password(password)
        user.save(using=self.context.get("using") or "default")
        return user


class LoginRequestSerializer(serializers.Serializer):
    """email 또는 username + password 허용"""
    email = serializers.EmailField(required=False, allow_blank=True)
    username = serializers.CharField(required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, attrs):
        email = (attrs.get("email") or "").strip()
        username = (attrs.get("username") or "").strip()
        password = attrs.get("password") or ""

        if not password:
            raise serializers.ValidationError({"password": "This field is required."})
        if not email and not username:
            raise serializers.ValidationError({"detail": "email or username is required."})

        # email만 왔으면 username 매핑
        if email and not username:
            try:
                u = User.objects.get(email__iexact=normalize_email(email))
                username = getattr(u, "username", None) or getattr(u, User.USERNAME_FIELD, None) or ""
            except User.DoesNotExist:
                raise serializers.ValidationError({"detail": "Invalid credentials"})

        attrs["username"] = username
        attrs["password"] = password
        return attrs


class LoginSerializer(LoginRequestSerializer):
    """LoginView에서 실제 인증 수행"""
    def validate(self, attrs):
        attrs = super().validate(attrs)
        user = authenticate(self.context.get("request"), username=attrs["username"], password=attrs["password"])
        if not user:
            # 동일 메시지로 노출 (보안)
            raise serializers.ValidationError({"detail": "Invalid credentials"})

        if not getattr(user, "is_active", True) or getattr(user, "status", "") == "deleted":
            raise serializers.ValidationError({"detail": "Inactive or deleted account"})

        attrs["user"] = user
        return attrs


# ─────────────────────────────────────────────────────────────
# /users/me (조회/수정)
# ─────────────────────────────────────────────────────────────
class MeSerializer(serializers.ModelSerializer):
    """내 정보 조회용 (GET /users/me) — 안전한 필드만 노출"""
    user_id = serializers.UUIDField(source="id", read_only=True)
    role = serializers.CharField(read_only=True)
    name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "user_id",
            "email",
            "username",
            "name",
            "nickname",
            "phone_number",
            "address",
            "status",
            "is_active",
            "role",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_name(self, obj):
        fn = getattr(obj, "first_name", None)
        ln = getattr(obj, "last_name", None)
        if fn and ln:
            return f"{fn} {ln}"
        return fn or None


class MeUpdateSerializer(serializers.ModelSerializer):
    """
    내 정보 수정용 (PATCH /users/me)
    - name -> first_name 로 매핑
    - 비밀번호 변경(current/new) 옵션
    """
    name = serializers.CharField(source="first_name", required=False, allow_blank=True, max_length=150)
    nickname = serializers.CharField(required=False, allow_blank=True, max_length=150)
    phone_number = serializers.CharField(required=False, allow_blank=True, max_length=50)
    address = serializers.CharField(required=False, allow_blank=True)

    current_password = serializers.CharField(write_only=True, required=False, trim_whitespace=False)
    new_password = serializers.CharField(write_only=True, required=False, min_length=8, max_length=16, trim_whitespace=False)

    class Meta:
        model = User
        fields = ("name", "nickname", "phone_number", "address", "current_password", "new_password")

    def validate(self, data):
        cur = data.get("current_password")
        new = data.get("new_password")

        # 둘 중 하나만 오면 오류
        if (cur is None) ^ (new is None):
            raise serializers.ValidationError({"new_password": "current_password와 new_password는 함께 보내야 합니다."})

        if new:
            user = self.instance or self.context.get("request").user
            if not check_password(cur or "", user.password):
                raise serializers.ValidationError({"current_password": "현재 비밀번호가 올바르지 않습니다."})
            validate_password(new, user=user)
        return data

    def update(self, instance, validated):
        # 일반 필드 반영
        for f in ("first_name", "nickname", "phone_number", "address"):
            if f in validated:
                setattr(instance, f, validated[f])
        # 비밀번호 변경
        new = validated.get("new_password")
        if new:
            instance.set_password(new)
        instance.save()
        return instance


# ─────────────────────────────────────────────────────────────
# 소셜 계정
# ─────────────────────────────────────────────────────────────
class SocialAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = SocialAccount
        fields = ("id", "provider", "provider_uid", "email", "created_at")
        read_only_fields = fields
