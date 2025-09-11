from rest_framework import serializers
from domains.reviews.models import Review
from domains.orders.models import Purchase

class ReviewReadSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(read_only=True)
    product_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = Review
        fields = ["review_id", "user_id", "product_id", "rating", "content", "created_at"]


class ReviewWriteSerializer(serializers.ModelSerializer):
    rating = serializers.IntegerField(min_value=1, max_value=5)

    class Meta:
        model = Review
        fields = ["rating", "content"]

    # ---- 내부 유틸: product_id 해석(컨텍스트 or 인스턴스) ----
    def _get_product_id(self):
        pid = self.context.get("product_id")
        if pid is None and getattr(self, "instance", None) is not None:
            pid = self.instance.product_id
        return pid

    def validate(self, attrs):
        request = self.context["request"]
        user = request.user
        product_id = self._get_product_id()
        if product_id is None:
            raise serializers.ValidationError("product_id missing")

        # 업데이트(PATCH)인 경우: 소유권은 permission에서 보장되므로 추가 검증 불필요
        if self.instance:
            return attrs

        # 생성(POST)인 경우만 검증
        if not Purchase.objects.filter(
            user=user, product_id=product_id, status=Purchase.STATUS_PAID
        ).exists():
            raise serializers.ValidationError("you must have a paid purchase for this product")

        if Review.objects.filter(user=user, product_id=product_id).exists():
            raise serializers.ValidationError("review already exists")

        return attrs

    def create(self, validated_data):
        return Review.objects.create(
            user=self.context["request"].user,
            product_id=self._get_product_id(),
            **validated_data
        )
