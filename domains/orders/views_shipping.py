from drf_spectacular.utils import extend_schema
from rest_framework import views, permissions, status
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.utils import timezone

from domains.accounts.models import UserAddress
from .models import Purchase, PurchaseStatus

class UpdatePurchaseAddressAPI(views.APIView):
    """
    PATCH /api/v1/orders/purchases/{purchase_id}/shipping-address/
    - 결제 전(ready) 주문만 변경 가능
    body:
      - {"address_id":"uuid"}  또는
      - {"address":{...}}
    """
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, purchase_id):
        order = get_object_or_404(Purchase, pk=purchase_id, user=request.user)

        # 결제 전만 허용
        if order.status not in (Purchase.STATUS_READY, PurchaseStatus.READY):
            return Response({"detail": "address change not allowed after payment"}, status=409)

        payload = request.data or {}
        if payload.get("address_id"):
            a = get_object_or_404(UserAddress, pk=payload["address_id"], user=request.user, is_active=True)
            order.shipping_recipient=a.recipient; order.shipping_phone=a.phone
            order.shipping_postcode=a.postcode;   order.shipping_address1=a.address1
            order.shipping_address2=a.address2;   order.shipping_memo=payload.get("memo","")
        elif payload.get("address"):
            addr = payload["address"]
            order.shipping_recipient=addr.get("recipient",""); order.shipping_phone=addr.get("phone","")
            order.shipping_postcode=addr.get("postcode","");   order.shipping_address1=addr.get("address1","")
            order.shipping_address2=addr.get("address2","");   order.shipping_memo=addr.get("memo","")
        else:
            return Response({"detail": "address_id or address is required"}, status=400)

        order.save(update_fields=[
            "shipping_recipient","shipping_phone","shipping_postcode",
            "shipping_address1","shipping_address2","shipping_memo","updated_at"
        ])
        return Response({"ok": True})


class BulkUpdateShippingAddressAPI(views.APIView):
    """
    PATCH /api/v1/orders/purchases/bulk-shipping-address/
    - 여러 ready 상태 주문에 한번에 배송지 지정
    body:
      - {"purchase_ids": ["uuid1", "uuid2"], "address_id": "uuid"}  또는
      - {"purchase_ids": ["uuid1", "uuid2"], "address": {...}}
    """
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        summary="여러 주문 일괄 배송지 지정",
        request={
            "type": "object",
            "properties": {
                "purchase_ids": {
                    "type": "array",
                    "items": {"type": "string", "format": "uuid"},
                    "description": "배송지를 변경할 주문 ID 목록"
                },
                "address_id": {
                    "type": "string",
                    "format": "uuid",
                    "description": "등록된 배송지 ID (address와 중복 사용 불가)"
                },
                "address": {
                    "type": "object",
                    "properties": {
                        "recipient": {"type": "string"},
                        "phone": {"type": "string"},
                        "postcode": {"type": "string"},
                        "address1": {"type": "string"},
                        "address2": {"type": "string"},
                        "memo": {"type": "string"}
                    },
                    "description": "새로운 배송지 정보 (address_id와 중복 사용 불가)"
                }
            },
            "required": ["purchase_ids"]
        },
        responses={
            200: {
                "type": "object",
                "properties": {
                    "success_count": {"type": "integer"},
                    "failed_count": {"type": "integer"},
                    "results": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "purchase_id": {"type": "string"},
                                "status": {"type": "string", "enum": ["success", "failed"]},
                                "message": {"type": "string"}
                            }
                        }
                    }
                }
            }
        }
    )
    @transaction.atomic
    def patch(self, request):
        payload = request.data or {}
        purchase_ids = payload.get("purchase_ids", [])
        
        if not purchase_ids:
            return Response({"detail": "purchase_ids is required"}, status=400)

        # 주문들 조회 (ready 상태만)
        orders = Purchase.objects.filter(
            purchase_id__in=purchase_ids,
            user=request.user,
            status__in=[Purchase.STATUS_READY, PurchaseStatus.READY]
        )
        
        if not orders.exists():
            return Response({"detail": "No ready orders found"}, status=404)

        # 배송지 정보 준비
        address_data = {}
        if payload.get("address_id"):
            address = get_object_or_404(
                UserAddress, 
                pk=payload["address_id"], 
                user=request.user, 
                is_active=True
            )
            address_data = {
                "shipping_recipient": address.recipient,
                "shipping_phone": address.phone,
                "shipping_postcode": address.postcode,
                "shipping_address1": address.address1,
                "shipping_address2": address.address2,
                "shipping_memo": payload.get("memo", "")
            }
        elif payload.get("address"):
            addr = payload["address"]
            address_data = {
                "shipping_recipient": addr.get("recipient", ""),
                "shipping_phone": addr.get("phone", ""),
                "shipping_postcode": addr.get("postcode", ""),
                "shipping_address1": addr.get("address1", ""),
                "shipping_address2": addr.get("address2", ""),
                "shipping_memo": addr.get("memo", "")
            }
        else:
            return Response({"detail": "address_id or address is required"}, status=400)

        # 일괄 업데이트
        update_fields = [
            "shipping_recipient", "shipping_phone", "shipping_postcode",
            "shipping_address1", "shipping_address2", "shipping_memo", "updated_at"
        ]
        
        updated_count = orders.update(**address_data)
        
        # 결과 정리
        results = []
        success_count = 0
        failed_count = 0
        
        for order in orders:
            if order.shipping_recipient == address_data["shipping_recipient"]:
                results.append({
                    "purchase_id": str(order.purchase_id),
                    "status": "success",
                    "message": "배송지가 성공적으로 업데이트되었습니다."
                })
                success_count += 1
            else:
                results.append({
                    "purchase_id": str(order.purchase_id),
                    "status": "failed",
                    "message": "배송지 업데이트에 실패했습니다."
                })
                failed_count += 1

        # 요청한 주문 중 처리되지 않은 것들 추가
        requested_ids = set(purchase_ids)
        processed_ids = {str(order.purchase_id) for order in orders}
        not_found_ids = requested_ids - processed_ids
        
        for purchase_id in not_found_ids:
            results.append({
                "purchase_id": purchase_id,
                "status": "failed",
                "message": "주문을 찾을 수 없거나 ready 상태가 아닙니다."
            })
            failed_count += 1

        return Response({
            "success_count": success_count,
            "failed_count": failed_count,
            "results": results
        }, status=200)


@extend_schema(summary="현재 사용자의 모든 ready 주문 배송지 일괄 변경", tags=["Orders"])
class UpdateAllReadyOrdersShippingAddressAPI(views.APIView):
    """
    PATCH /api/v1/orders/purchases/update-all-ready-shipping-address/
    - 현재 사용자의 모든 ready 상태 주문에 대해 배송지를 일괄 변경
    - purchase_ids를 명시하지 않아도 됨 (자동으로 모든 ready 주문 대상)
    """
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        summary="현재 사용자의 모든 ready 주문 배송지 일괄 변경",
        tags=["Orders"],
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "address_id": {
                        "type": "string",
                        "format": "uuid",
                        "description": "등록된 배송지 ID (address와 중복 사용 불가)"
                    },
                    "address": {
                        "type": "object",
                        "properties": {
                            "recipient": {"type": "string"},
                            "phone": {"type": "string"},
                            "postcode": {"type": "string"},
                            "address1": {"type": "string"},
                            "address2": {"type": "string"},
                            "memo": {"type": "string"}
                        },
                        "description": "새로운 배송지 정보 (address_id와 중복 사용 불가)"
                    },
                    "memo": {
                        "type": "string",
                        "description": "배송 메모 (선택사항)"
                    }
                }
            }
        },
        responses={
            200: {
                "type": "object",
                "properties": {
                    "success_count": {"type": "integer"},
                    "failed_count": {"type": "integer"},
                    "updated_purchase_ids": {
                        "type": "array",
                        "items": {"type": "string", "format": "uuid"}
                    },
                    "message": {"type": "string"}
                }
            },
            400: {"type": "object"},
            404: {"type": "object"}
        }
    )
    @transaction.atomic
    def patch(self, request):
        user = request.user
        payload = request.data or {}
        
        address_id = payload.get("address_id")
        inline_address = payload.get("address")
        memo = payload.get("memo", "")

        # 배송지 정보 준비
        address_data = {}
        
        if address_id:
            # 기존 주소 ID로 가져오기
            try:
                a = UserAddress.objects.get(pk=address_id, user=user, is_active=True)
                address_data = {
                    "shipping_recipient": a.recipient,
                    "shipping_phone": a.phone,
                    "shipping_postcode": a.postcode,
                    "shipping_address1": a.address1,
                    "shipping_address2": a.address2,
                    "shipping_memo": memo,
                }
            except UserAddress.DoesNotExist:
                return Response({"detail": "UserAddress not found or not active"}, status=404)
        elif inline_address:
            # 인라인 주소 정보 사용
            address_data = {
                "shipping_recipient": inline_address.get("recipient", ""),
                "shipping_phone": inline_address.get("phone", ""),
                "shipping_postcode": inline_address.get("postcode", ""),
                "shipping_address1": inline_address.get("address1", ""),
                "shipping_address2": inline_address.get("address2", ""),
                "shipping_memo": memo,
            }
        else:
            return Response({"detail": "address_id or address is required"}, status=400)

        # 현재 사용자의 모든 ready 상태 주문 조회
        orders_to_update = Purchase.objects.filter(
            user=user,
            status__in=[Purchase.STATUS_READY, PurchaseStatus.READY]
        ).select_for_update()

        if not orders_to_update.exists():
            return Response({
                "success_count": 0,
                "failed_count": 0,
                "updated_purchase_ids": [],
                "message": "업데이트할 ready 상태 주문이 없습니다."
            }, status=200)

        # 일괄 업데이트 실행
        updated_count = orders_to_update.update(**address_data)
        
        # 업데이트된 주문 ID 목록
        updated_purchase_ids = list(orders_to_update.values_list('purchase_id', flat=True))

        return Response({
            "success_count": updated_count,
            "failed_count": 0,
            "updated_purchase_ids": [str(pid) for pid in updated_purchase_ids],
            "message": f"{updated_count}개의 주문 배송지가 성공적으로 업데이트되었습니다."
        }, status=status.HTTP_200_OK)