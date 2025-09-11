from rest_framework import serializers
from domains.orders.models import Purchase
from domains.catalog.models import Product

class PurchaseReadSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(read_only=True)
    product_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = Purchase
        fields = ["purchase_id", "user_id", "product_id", "amount", "status", "purchased_at"]

class PurchaseWriteSerializer(serializers.ModelSerializer):
    product_id = serializers.IntegerField()
    amount = serializers.IntegerField(min_value=1)

    class Meta:
        model = Purchase
        fields = ["product_id", "amount"]

    def validate_product_id(self, value):
        # 유효 상품 여부 체크(원하면 is_active 조건 제거/변경)
        if not Product.objects.filter(pk=value).exists():
            raise serializers.ValidationError("product not found")
        return value
    # ⛔ create()는 정의하지 않습니다. (user/status는 view에서 넣음)
