from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password
from django.contrib.auth.base_user import BaseUserManager
from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password

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
    class Meta:
        model = User
        fields = ("email", "nickname", "phone_number", "address", "status", "created_at", "updated_at")
        read_only_fields = ("email", "status", "created_at", "updated_at")
