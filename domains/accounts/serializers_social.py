# domains/accounts/serializers_social.py
from rest_framework import serializers


class SocialAuthRequestSerializer(serializers.Serializer):
    code = serializers.CharField()
    state = serializers.CharField(required=False, allow_blank=True)
    redirect_uri = serializers.CharField(required=False)  # 프론트에서 보낸 값 우선


class SocialUnlinkRequestSerializer(serializers.Serializer):
    provider = serializers.ChoiceField(choices=["google", "naver"])
