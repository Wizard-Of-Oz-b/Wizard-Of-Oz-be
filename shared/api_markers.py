# shared/api_markers.py
"""
API 문서화용 마커 클래스들

이 모듈은 @extend_schema에서 사용되는 빈 시리얼라이저들을 정의합니다.
주로 요청 바디가 없는 API 엔드포인트의 문서화에 사용됩니다.
"""
from rest_framework import serializers


class EmptySerializer(serializers.Serializer):
    """
    본문이 없는 요청/응답에 쓰는 더미 시리얼라이저
    
    사용 예시:
    @extend_schema(
        request=EmptySerializer,
        responses={200: SomeResponseSerializer},
    )
    class SomeAPI(APIView):
        def post(self, request):
            # 요청 바디가 없는 API
            pass
    """
    pass


class EmptyRequestSerializer(serializers.Serializer):
    """
    요청 바디가 없는 API용 시리얼라이저
    
    EmptySerializer와 동일하지만 의미상 구분을 위해 별도 정의.
    향후 요청 전용 로직이 추가될 수 있습니다.
    """
    pass


class SimpleResponseSerializer(serializers.Serializer):
    """
    단순 응답용 기본 클래스
    
    기본적인 응답 구조를 제공하는 마커 클래스입니다.
    """
    pass


class ActionResponseSerializer(serializers.Serializer):
    """
    액션 결과 응답용 기본 클래스
    
    일반적인 액션 결과 응답에 사용되는 기본 필드들을 제공합니다.
    """
    id = serializers.UUIDField()
    status = serializers.CharField()
