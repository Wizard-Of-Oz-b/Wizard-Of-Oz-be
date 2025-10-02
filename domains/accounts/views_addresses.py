from django.shortcuts import get_object_or_404

from rest_framework import generics, permissions, status
from rest_framework.response import Response

from .models import UserAddress
from .serializers_addresses import UserAddressReadSerializer, UserAddressWriteSerializer


class MyAddressListCreateAPI(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return UserAddress.objects.filter(
            user=self.request.user, is_active=True
        ).order_by("-is_default", "-created_at")

    def get_serializer_class(self):
        return (
            UserAddressWriteSerializer
            if self.request.method == "POST"
            else UserAddressReadSerializer
        )

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx

    # 여기 추가: 생성 응답은 ReadSerializer로 내려주기 (address_id 포함)
    def create(self, request, *args, **kwargs):
        write_ser = self.get_serializer(data=request.data)
        write_ser.is_valid(raise_exception=True)
        obj = write_ser.save()
        read_ser = UserAddressReadSerializer(obj, context=self.get_serializer_context())
        headers = self.get_success_headers(read_ser.data)
        return Response(read_ser.data, status=status.HTTP_201_CREATED, headers=headers)


class MyAddressDetailAPI(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [permissions.IsAuthenticated]
    lookup_url_kwarg = "address_id"

    def get_queryset(self):
        return UserAddress.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        return (
            UserAddressWriteSerializer
            if self.request.method in ("PATCH", "PUT")
            else UserAddressReadSerializer
        )

    def delete(self, request, *args, **kwargs):
        # 소프트 삭제
        addr = self.get_object()
        addr.is_active = False
        if addr.is_default:
            addr.is_default = False
        addr.save(update_fields=["is_active", "is_default"])
        return Response(status=status.HTTP_204_NO_CONTENT)


from rest_framework.views import APIView


class SetDefaultAddressAPI(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, address_id):
        u = request.user
        addr = get_object_or_404(UserAddress, pk=address_id, user=u, is_active=True)
        UserAddress.objects.filter(user=u, is_default=True).exclude(pk=addr.pk).update(
            is_default=False
        )
        if not addr.is_default:
            addr.is_default = True
            addr.save(update_fields=["is_default"])
        return Response({"ok": True, "address_id": str(addr.address_id)})
