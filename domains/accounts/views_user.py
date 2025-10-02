from django.shortcuts import get_object_or_404

from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import User
from .permissions import IsSelf
from .serializers import UserMeSerializer


# 1) /api/v1/users/  -> 본인만 1건 리스트로 반환 (Swagger에 기존 경로 유지용)
class UserSelfOnlyListAPI(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserMeSerializer

    def get_queryset(self):
        return User.objects.filter(pk=self.request.user.pk)


# 2) /api/v1/users/{user_id}/ -> 경로에 id가 있어도 "본인 것"만 허용
class UserSelfOnlyRetrieveAPI(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated, IsSelf]
    serializer_class = UserMeSerializer
    queryset = User.objects.all()

    # 객체 가져온 뒤 IsSelf로 최종 검증
    # (RetrieveAPIView 기본 동작으로도 되지만 가독성 위해 명시)
    def get_object(self):
        obj = get_object_or_404(User, pk=self.kwargs["pk"])
        self.check_object_permissions(self.request, obj)
        return obj


# 3) /api/v1/users/me/ (GET/PATCH/DELETE)
class UserMeAPI(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated, IsSelf]
    serializer_class = UserMeSerializer

    def get_object(self):
        # 항상 본인
        obj = self.request.user
        self.check_object_permissions(self.request, obj)
        return obj

    # 필요 시 PATCH 허용 필드 제한은 serializer에서 처리됨
