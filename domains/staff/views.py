from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView, ListAPIView
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiParameter

from shared.permissions import IsAdmin, IsSuperAdmin
from .models import Admin, AdminLog, AdminAction
from .serializers import (
    AdminCreateSerializer, AdminUpdateSerializer, AdminOutSerializer,
    AdminLogOutSerializer
)

# ---------- admins ----------
class AdminListCreateAPI(ListCreateAPIView):
    """
    GET  /api/v1/admins      (Super 전용, 관리자 목록)
    POST /api/v1/admins      (Super 전용, 관리자 부여)
    """
    permission_classes = [IsSuperAdmin]
    serializer_class = AdminOutSerializer
    # 스키마 생성 시 안전
    queryset = Admin.objects.all().select_related("user")
    http_method_names = ["get", "post", "options", "head"]  # PUT 노출 방지

    def get_serializer_class(self):
        return AdminCreateSerializer if self.request.method == "POST" else AdminOutSerializer

    def create(self, request, *args, **kwargs):
        ser = AdminCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        admin = ser.save()
        AdminLog.objects.create(
            admin=getattr(request.user, "admin_profile", None),
            action=AdminAction.CREATE, target_table="admins", target_id=admin.id,
            description=f"grant role={admin.role} to user_id={admin.user_id}",
        )
        return Response(AdminOutSerializer(admin).data, status=status.HTTP_201_CREATED)

class AdminDetailAPI(RetrieveUpdateDestroyAPIView):
    """
    GET    /api/v1/admins/{admin_id}
    PATCH  /api/v1/admins/{admin_id}   (역할 변경)
    DELETE /api/v1/admins/{admin_id}   (권한 해제)
    """
    permission_classes = [IsSuperAdmin]
    queryset = Admin.objects.all().select_related("user")
    lookup_url_kwarg = "admin_id"
    http_method_names = ["get", "patch", "delete", "options", "head"]  # PUT 제거

    def get_serializer_class(self):
        return AdminUpdateSerializer if self.request.method == "PATCH" else AdminOutSerializer

    def patch(self, request, *args, **kwargs):
        admin = self.get_object()
        ser = AdminUpdateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        admin.role = ser.validated_data["role"]
        admin.save(update_fields=["role"])
        AdminLog.objects.create(
            admin=getattr(request.user, "admin_profile", None),
            action=AdminAction.UPDATE, target_table="admins", target_id=admin.id,
            description=f"change role to {admin.role}",
        )
        return Response(AdminOutSerializer(admin).data)

    def delete(self, request, *args, **kwargs):
        admin = self.get_object()
        aid = admin.id
        admin.delete()
        AdminLog.objects.create(
            admin=getattr(request.user, "admin_profile", None),
            action=AdminAction.DELETE, target_table="admins", target_id=aid,
            description="revoke admin",
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

# ---------- admin-logs ----------
@extend_schema(
    parameters=[
        OpenApiParameter(name="admin_id", required=False, type=int),
        OpenApiParameter(name="action", required=False, type=str),
        OpenApiParameter(name="target_table", required=False, type=str),
        OpenApiParameter(name="target_id", required=False, type=int),
        OpenApiParameter(name="date_from", required=False, type=str, description="YYYY-MM-DD"),
        OpenApiParameter(name="date_to", required=False, type=str, description="YYYY-MM-DD"),
    ]
)
class AdminLogListAPI(ListAPIView):
    """
    GET /api/v1/admin-logs   (Admin 이상 열람)
    """
    permission_classes = [IsAdmin]
    serializer_class = AdminLogOutSerializer
    queryset = AdminLog.objects.all().order_by("-created_at")

    def get_queryset(self):
        qs = super().get_queryset()
        p = self.request.query_params
        if aid := p.get("admin_id"):
            qs = qs.filter(admin_id=aid)
        if act := p.get("action"):
            qs = qs.filter(action=act)
        if tt := p.get("target_table"):
            qs = qs.filter(target_table=tt)
        if tid := p.get("target_id"):
            qs = qs.filter(target_id=tid)
        if df := p.get("date_from"):
            qs = qs.filter(created_at__date__gte=df)
        if dt := p.get("date_to"):
            qs = qs.filter(created_at__date__lte=dt)
        return qs
