# domains/accounts/serializers.py
from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.hashers import check_password
from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .models import SocialAccount

User = get_user_model()


# ------------------------
# 공용/관리용 Serializer
# ------------------------
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


class EmptySerializer(serializers.Serializer):
    """본문이 없는 요청/응답에 쓰는 더미"""
    pass


class LoginRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class TokenResponseSerializer(serializers.Serializer):
    access = serializers.CharField()


# access + refresh 동시 응답용 (스키마 문서화)
class TokenPairResponseSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()


def normalize_email(value: str) -> str:
    v = (value or "").strip()
    v = BaseUserManager.normalize_email(v)
    return v.lower()


# ------------------------
# 회원가입 / 로그인
# ------------------------
class RegisterSerializer(serializers.ModelSerializer):
    # 길이도 8~16으로 UI/스키마 레벨 맞춤
    password = serializers.CharField(write_only=True, min_length=8, max_length=16)

    class Meta:
        model = User
        # 현재 User 모델에 있다고 확신되는 필드만 명시
        fields = ("email", "password", "nickname", "phone_number", "address")

    def validate(self, data):
        # 전역 비밀번호 검증기(복잡도 포함) 실행
        temp_user = User(email=normalize_email(data.get("email", "")))
        validate_password(data["password"], user=temp_user)
        return data

    def create(self, validated):
        email = normalize_email(validated["email"])
        password = validated["password"]

        user = User(
            email=email,
            username=email,  # UNIQUE 충돌 방지: username을 이메일로 세팅
            nickname=validated.get("nickname", ""),
            phone_number=validated.get("phone_number", ""),
            address=validated.get("address", ""),
        )
        user.set_password(password)
        user.save(using=self.context.get("using") or "default")
        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        email = normalize_email(data["email"])
        password = data["password"]

        # 케이스 무시 검색 + 비밀번호 검증
        user = User.objects.filter(email__iexact=email).first()
        if not user or not check_password(password, user.password):
            raise serializers.ValidationError("Invalid credentials")

        if not getattr(user, "is_active", True) or getattr(user, "status", "") == "deleted":
            raise serializers.ValidationError("Inactive or deleted account")

        data["user"] = user
        return data


# ------------------------
# /users/me (조회/수정)
# ------------------------
class MeSerializer(serializers.ModelSerializer):
    """내 정보 조회용 (GET /users/me) — 안전한 필드만 노출"""
    user_id = serializers.UUIDField(source="id", read_only=True)
    role = serializers.CharField(read_only=True)
    # User 모델에 'name' 필드가 없을 수 있어 계산 필드로 제공
    name = serializers.SerializerMethodField()

    class Meta:
        model = User
        # 존재하는 필드 + 계산/매핑 필드만 나열
        fields = [
            "user_id",
            "email",
            "username",
            "name",          # first_name 기반 계산 필드
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
        # 선호: user.first_name → (없으면 None)
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

    # 비밀번호 변경(옵션)
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
        # 일반 필드 반영 (name은 first_name으로 들어옴)
        for f in ("first_name", "nickname", "phone_number", "address"):
            if f in validated:
                setattr(instance, f, validated[f])

        # 비밀번호 변경
        new = validated.get("new_password")
        if new:
            instance.set_password(new)

        instance.save()
        return instance


# ------------------------
# 소셜 계정
# ------------------------
class SocialAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = SocialAccount
        fields = ("id", "provider", "provider_uid", "email", "created_at")
        read_only_fields = fields
