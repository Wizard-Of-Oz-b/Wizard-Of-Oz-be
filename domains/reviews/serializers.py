# domains/reviews/serializers.py
from __future__ import annotations

from rest_framework import serializers
from domains.reviews.models import Review
from domains.orders.models import Purchase


class ReviewReadSerializer(serializers.ModelSerializer):
    # 프로젝트 전역 UUID PK 정책에 맞춰 UUIDField 사용
    review_id = serializers.UUIDField(read_only=True)
    user_id = serializers.UUIDField(read_only=True)
    product_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = Review
        fields = ["review_id", "user_id", "product_id", "rating", "content", "created_at"]


class ReviewWriteSerializer(serializers.ModelSerializer):
    """
    생성(POST)과 부분수정(PATCH) 공용 Serializer.
    - 입력 필드는 rating, content 만 받는다.
    - user/product_id는 뷰/컨텍스트 기반으로 내부에서 주입한다.
    """
    rating = serializers.IntegerField(min_value=1, max_value=5)

    class Meta:
        model = Review
        fields = ["rating", "content"]  # 입력 전용 필드만 노출 (user/product_id는 내부 주입)

    # ---- 내부 유틸: product_id 추출 ----
    def _get_product_id(self):
        """
        우선순위:
        1) self.context["product_id"] (뷰에서 명시적으로 넣어준 경우)
        2) self.context["view"].kwargs["product_id"] (URL kwarg 기반)
        3) 업데이트(PATCH)인 경우 instance에서 가져오기
        """
        pid = self.context.get("product_id")
        if pid is None:
            view = self.context.get("view")
            if view is not None:
                pid = view.kwargs.get("product_id")
        if pid is None and getattr(self, "instance", None) is not None:
            pid = self.instance.product_id
        return pid

    def validate(self, attrs):
        """
        - 생성(POST)일 때만 '구매자만, 1인 1리뷰' 규칙 검증
        - 그 시점에 attrs에 user/product_id를 주입하여 create(**validated_data)만으로 저장 가능하게 함
        """
        request = self.context["request"]
        user = request.user
        product_id = self._get_product_id()

        if product_id is None:
            raise serializers.ValidationError("product_id missing")

        # 업데이트(PATCH)인 경우: 소유권/권한은 permission에서 보장된다고 가정, 추가 검증 없이 통과
        if self.instance:
            return attrs

        # 생성(POST) 검증 로직
        # 1) 구매자만: 해당 product에 대해 'paid' 상태의 구매 이력 필요
        if not Purchase.objects.filter(
            user=user, product_id=product_id, status=Purchase.STATUS_PAID
        ).exists():
            raise serializers.ValidationError("you must have a paid purchase for this product")

        # 2) 1인 1리뷰
        if Review.objects.filter(user=user, product_id=product_id).exists():
            raise serializers.ValidationError("review already exists")

        # 생성 시점에 내부 주입: 이후 create()에서 **validated_data 만으로 처리할 수 있게 함
        attrs["user"] = user
        attrs["product_id"] = product_id
        return attrs

    def create(self, validated_data):
        """
        perform_create()가 user/product_id를 save(...)로 넘기든,
        현재 validate()에서 attrs에 주입하든
        결국 여기서는 중복 인자 없이 **validated_data만** 전달해야 한다.
        """
        return Review.objects.create(**validated_data)
