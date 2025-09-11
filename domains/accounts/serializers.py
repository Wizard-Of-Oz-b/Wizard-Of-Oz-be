from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.hashers import check_password
from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import SocialAccount
from rest_framework import serializers
from .models import User
User = get_user_model()


class EmptySerializer(serializers.Serializer):
    """본문이 없는 요청/응답에 쓰는 더미"""
    pass


class LoginRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class TokenResponseSerializer(serializers.Serializer):
    access = serializers.CharField()


# ✅ access + refresh 동시 응답용 (스키마 문서화)
class TokenPairResponseSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()


def normalize_email(value: str) -> str:
    v = (value or "").strip()
    v = BaseUserManager.normalize_email(v)
    return v.lower()


class RegisterSerializer(serializers.ModelSerializer):
    # 길이도 8~16으로 UI/스키마 레벨 맞춰줌
    password = serializers.CharField(write_only=True, min_length=8, max_length=16)

    class Meta:
        model = User
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
            username=email,  # ✅ 핵심: username을 반드시 채움(UNIQUE 충돌 방지)
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


class MeSerializer(serializers.ModelSerializer):
    # first_name 을 name 으로 노출
    name = serializers.CharField(source="first_name", read_only=True)

    class Meta:
        model = User
        fields = ("email", "name", "nickname", "phone_number", "address",
                  "status", "created_at", "updated_at")
        read_only_fields = ("email", "status", "created_at", "updated_at")

# 수정용
class MeUpdateSerializer(serializers.ModelSerializer):
    # 쓰기 허용 필드
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
        if (cur is None) ^ (new is None):
            raise serializers.ValidationError({"new_password": "current_password와 new_password는 함께 보내야 합니다."})
        if new:
            user = self.instance or self.context.get("request").user
            if not check_password(cur or "", user.password):
                raise serializers.ValidationError({"current_password": "현재 비밀번호가 올바르지 않습니다."})
            validate_password(new, user=user)  # 우리의 커스텀 복잡도 검증기도 함께 적용됨
        return data

    def update(self, instance, validated):
        # 일반 필드
        for f in ("first_name", "nickname", "phone_number", "address"):
            if f in validated:
                setattr(instance, f, validated[f])

        # 비밀번호
        new = validated.get("new_password")
        if new:
            instance.set_password(new)

        instance.save()
        return instance

class SocialAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = SocialAccount
        fields = ("id", "provider", "provider_uid", "email", "created_at")
        read_only_fields = fields

class UserMeSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        # 노출하고 싶은 필드만 (예시)
        fields = ["id", "email", "username", "nickname", "avatar_url", "created_at", "updated_at"]
        read_only_fields = ["id", "email", "created_at", "updated_at"]