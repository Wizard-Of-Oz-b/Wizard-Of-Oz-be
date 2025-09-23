from rest_framework import serializers
from .models import UserAddress

class UserAddressReadSerializer(serializers.ModelSerializer):
    address_id = serializers.UUIDField(read_only=True)
    class Meta:
        model = UserAddress
        fields = (
            "address_id","recipient","phone","postcode","address1","address2",
            "is_default","is_active","created_at","updated_at"
        )

class UserAddressWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserAddress
        fields = ("recipient","phone","postcode","address1","address2","is_default","is_active")

    def create(self, validated):
        u = self.context["request"].user
        obj = UserAddress.objects.create(user=u, **validated)
        # 첫 주소는 자동 기본 지정
        if not UserAddress.objects.filter(user=u, is_default=True, is_active=True).exists():
            obj.is_default = True
            obj.save(update_fields=["is_default"])
        return obj
