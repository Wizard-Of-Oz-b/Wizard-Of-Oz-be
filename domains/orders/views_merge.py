# domains/orders/views_merge.py
from __future__ import annotations

from drf_spectacular.utils import extend_schema, OpenApiExample
from rest_framework import permissions, serializers, status, views
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from .services_merge import (
    cancel_merged_order,
    delete_ready_orders,
    delete_single_ready_order,
    get_user_ready_orders_summary,
    merge_ready_orders,
)


class MergeOrdersRequestSerializer(serializers.Serializer):
    """주문 통합 요청 시리얼라이저"""
    order_ids = serializers.ListField(
        child=serializers.UUIDField(),
        min_length=2,
        help_text="통합할 주문 ID 목록 (최소 2개)"
    )


class CancelMergedOrderRequestSerializer(serializers.Serializer):
    """통합 주문 취소 요청 시리얼라이저"""
    merged_order_id = serializers.UUIDField(
        help_text="취소할 통합 주문 ID"
    )


class DeleteReadyOrdersRequestSerializer(serializers.Serializer):
    """Ready 주문 삭제 요청 시리얼라이저"""
    order_ids = serializers.ListField(
        child=serializers.UUIDField(),
        min_length=1,
        help_text="삭제할 Ready 상태 주문 ID 목록"
    )


class DeleteSingleReadyOrderRequestSerializer(serializers.Serializer):
    """단일 Ready 주문 삭제 요청 시리얼라이저"""
    order_id = serializers.UUIDField(
        help_text="삭제할 Ready 상태 주문 ID"
    )


class ReadyOrdersSummaryAPI(views.APIView):
    """사용자의 미결제 주문 요약 정보 조회"""
    
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Orders"],
        summary="미결제 주문 요약",
        description="사용자의 미결제(ready) 상태 주문들의 요약 정보를 조회합니다.",
        responses={
            200: {
                "type": "object",
                "properties": {
                    "total_orders": {"type": "integer", "description": "총 미결제 주문 수"},
                    "total_amount": {"type": "string", "description": "총 금액"},
                    "can_merge": {"type": "boolean", "description": "통합 가능 여부"},
                    "orders": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "order_id": {"type": "string", "format": "uuid"},
                                "amount": {"type": "string"},
                                "items_count": {"type": "integer"},
                                "created_at": {"type": "string", "format": "date-time"},
                                "order_name": {"type": "string"}
                            }
                        }
                    }
                }
            }
        }
    )
    def get(self, request):
        summary = get_user_ready_orders_summary(request.user)
        return Response(summary, status=status.HTTP_200_OK)


class MergeOrdersAPI(views.APIView):
    """여러 개의 ready 상태 주문을 하나로 통합"""
    
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Orders"],
        summary="주문 통합",
        description="여러 개의 미결제 주문을 하나의 새로운 주문으로 통합하고 결제 스텁을 생성합니다.",
        request=MergeOrdersRequestSerializer,
        examples=[
            OpenApiExample(
                "주문 통합 예시",
                value={
                    "order_ids": [
                        "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                        "4fa85f64-5717-4562-b3fc-2c963f66afa7"
                    ]
                },
                request_only=True
            )
        ],
        responses={
            201: {
                "type": "object",
                "properties": {
                    "merged_order_id": {"type": "string", "format": "uuid"},
                    "payment_id": {"type": "string", "format": "uuid"},
                    "order_number": {"type": "string"},
                    "total_amount": {"type": "string"},
                    "merged_count": {"type": "integer"},
                    "message": {"type": "string"}
                }
            },
            400: {
                "type": "object",
                "properties": {
                    "detail": {"type": "string"}
                }
            }
        }
    )
    def post(self, request):
        order_ids = request.data.get("order_ids", [])
        
        if not order_ids:
            return Response(
                {"detail": "통합할 주문 ID 목록이 필요합니다."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if len(order_ids) < 2:
            return Response(
                {"detail": "최소 2개 이상의 주문이 필요합니다."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            merged_order, payment = merge_ready_orders(request.user, order_ids)
            
            return Response({
                "merged_order_id": str(merged_order.purchase_id),
                "payment_id": str(payment.payment_id),
                "order_number": payment.order_number,
                "total_amount": str(payment.amount_total),
                "merged_count": len(order_ids),
                "message": f"{len(order_ids)}개의 주문이 성공적으로 통합되었습니다."
            }, status=status.HTTP_201_CREATED)
            
        except ValidationError as e:
            return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": f"주문 통합 중 오류가 발생했습니다: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CancelMergedOrderAPI(views.APIView):
    """통합 주문 취소 및 원래 주문들 복원"""
    
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Orders"],
        summary="통합 주문 취소",
        description="통합된 주문을 취소하고 가능한 경우 원래 주문들을 복원합니다.",
        request=CancelMergedOrderRequestSerializer,
        examples=[
            OpenApiExample(
                "통합 주문 취소 예시",
                value={
                    "merged_order_id": "5fa85f64-5717-4562-b3fc-2c963f66afa8"
                },
                request_only=True
            )
        ],
        responses={
            200: {
                "type": "object",
                "properties": {
                    "restored_orders": {"type": "integer"},
                    "main_order_id": {"type": "string", "format": "uuid"},
                    "message": {"type": "string"}
                }
            },
            400: {
                "type": "object",
                "properties": {
                    "detail": {"type": "string"}
                }
            },
            404: {
                "type": "object",
                "properties": {
                    "detail": {"type": "string"}
                }
            }
        }
    )
    def post(self, request):
        merged_order_id = request.data.get("merged_order_id")
        
        if not merged_order_id:
            return Response(
                {"detail": "취소할 주문 ID가 필요합니다."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            from .models import Purchase
            
            merged_order = Purchase.objects.get(
                purchase_id=merged_order_id,
                user=request.user
            )
            
            result = cancel_merged_order(merged_order, request.user)
            
            return Response({
                **result,
                "message": f"통합 주문이 취소되고 {result['restored_orders']}개의 주문이 복원되었습니다."
            }, status=status.HTTP_200_OK)
            
        except Purchase.DoesNotExist:
            return Response(
                {"detail": "주문을 찾을 수 없습니다."},
                status=status.HTTP_404_NOT_FOUND
            )
        except ValidationError as e:
            return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": f"주문 취소 중 오류가 발생했습니다: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class DeleteReadyOrdersAPI(views.APIView):
    """여러 개의 Ready 상태 주문을 삭제하고 재고 복구"""
    
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Orders"],
        summary="Ready 주문 일괄 삭제",
        description="여러 개의 미결제(Ready) 상태 주문을 삭제하고 재고를 복구합니다.",
        request=DeleteReadyOrdersRequestSerializer,
        examples=[
            OpenApiExample(
                "Ready 주문 일괄 삭제 예시",
                value={
                    "order_ids": [
                        "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                        "4fa85f64-5717-4562-b3fc-2c963f66afa7"
                    ]
                },
                request_only=True
            )
        ],
        responses={
            200: {
                "type": "object",
                "properties": {
                    "deleted_orders": {"type": "integer"},
                    "deleted_items": {"type": "integer"},
                    "restored_stock": {"type": "integer"},
                    "message": {"type": "string"}
                }
            },
            400: {
                "type": "object",
                "properties": {
                    "detail": {"type": "string"}
                }
            }
        }
    )
    def post(self, request):
        order_ids = request.data.get("order_ids", [])
        
        if not order_ids:
            return Response(
                {"detail": "삭제할 주문 ID 목록이 필요합니다."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            result = delete_ready_orders(request.user, order_ids)
            return Response(result, status=status.HTTP_200_OK)
            
        except ValidationError as e:
            return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": f"주문 삭제 중 오류가 발생했습니다: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class DeleteSingleReadyOrderAPI(views.APIView):
    """단일 Ready 상태 주문을 삭제하고 재고 복구"""
    
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Orders"],
        summary="Ready 주문 단일 삭제",
        description="단일 미결제(Ready) 상태 주문을 삭제하고 재고를 복구합니다.",
        request=DeleteSingleReadyOrderRequestSerializer,
        examples=[
            OpenApiExample(
                "Ready 주문 단일 삭제 예시",
                value={
                    "order_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"
                },
                request_only=True
            )
        ],
        responses={
            200: {
                "type": "object",
                "properties": {
                    "deleted_orders": {"type": "integer"},
                    "deleted_items": {"type": "integer"},
                    "restored_stock": {"type": "integer"},
                    "message": {"type": "string"}
                }
            },
            400: {
                "type": "object",
                "properties": {
                    "detail": {"type": "string"}
                }
            },
            404: {
                "type": "object",
                "properties": {
                    "detail": {"type": "string"}
                }
            }
        }
    )
    def post(self, request):
        order_id = request.data.get("order_id")
        
        if not order_id:
            return Response(
                {"detail": "삭제할 주문 ID가 필요합니다."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            result = delete_single_ready_order(request.user, str(order_id))
            return Response(result, status=status.HTTP_200_OK)
            
        except ValidationError as e:
            return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": f"주문 삭제 중 오류가 발생했습니다: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
