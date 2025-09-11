from django.contrib.auth import get_user_model
from rest_framework import serializers
from .models import Admin, AdminLog, AdminRole

User = get_user_model()

class AdminCreateSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    role = serializers.ChoiceField(choices=AdminRole.choices)

    def validate_user_id(self, v):
        if not User.objects.filter(pk=v).exists():
            raise serializers.ValidationError("user not found")
        if Admin.objects.filter(user_id=v).exists():
            raise serializers.ValidationError("already admin")
        return v

    def create(self, validated_data):
        return Admin.objects.create(**validated_data)

class AdminUpdateSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=AdminRole.choices)

# domains/staff/serializers.py

class AdminOutSerializer(serializers.ModelSerializer):
    admin_id = serializers.IntegerField(source="id", read_only=True)  # OK (다름)
    user_id  = serializers.IntegerField(read_only=True)               # ✅ source 제거

    class Meta:
        model  = Admin
        fields = ("admin_id", "user_id", "role")


class AdminLogOutSerializer(serializers.ModelSerializer):
    admin_id = serializers.IntegerField(read_only=True)               # ✅ source 제거

    class Meta:
        model  = AdminLog
        fields = ("admin_id", "action", "target_table", "target_id", "description", "created_at")


