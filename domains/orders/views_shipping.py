from drf_spectacular.utils import extend_schema
from rest_framework import views, permissions, status
from rest_framework.response import Response
from django.shortcuts import get_object_or_404

from domains.accounts.models import UserAddress
from .models import Purchase, PurchaseStatus

@extend_schema(summary="체크아웃 생성 (주소 자동 선택/빈값 허용)")
class CheckoutAPI(views.APIView):
    """
    POST /api/v1/orders/checkout/
    body (선택):
      - {"address_id":"uuid"}  또는
      - {"address":{...}, "memo":"..."}  또는
      - {} -> 기본배송지, 없으면 빈 주소로 진행
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        u = request.user
        payload = request.data or {}
        snap = {}

        addr_id = payload.get("address_id")
        inline  = payload.get("address")

        if addr_id:
            a = get_object_or_404(UserAddress, pk=addr_id, user=u, is_active=True)
            snap = dict(
                shipping_recipient=a.recipient, shipping_phone=a.phone,
                shipping_postcode=a.postcode, shipping_address1=a.address1,
                shipping_address2=a.address2, shipping_memo=payload.get("memo",""),
            )
        elif inline:
            snap = dict(
                shipping_recipient=inline.get("recipient",""),
                shipping_phone=inline.get("phone",""),
                shipping_postcode=inline.get("postcode",""),
                shipping_address1=inline.get("address1",""),
                shipping_address2=inline.get("address2",""),
                shipping_memo=inline.get("memo",""),
            )
        else:
            a = UserAddress.objects.filter(user=u, is_active=True, is_default=True).first()
            if a:
                snap = dict(
                    shipping_recipient=a.recipient, shipping_phone=a.phone,
                    shipping_postcode=a.postcode, shipping_address1=a.address1,
                    shipping_address2=a.address2, shipping_memo="",
                )
            else:
                snap = dict(  # 기본배송지도 없으면 빈 값으로 진행
                    shipping_recipient="", shipping_phone="", shipping_postcode="",
                    shipping_address1="", shipping_address2="", shipping_memo="",
                )

        order = Purchase.objects.create(
            user=u,
            items_total=0, grand_total=0,
            status=PurchaseStatus.READY,   # 결제 전 상태로 생성
            **snap
        )
        return Response({"purchase_id": str(order.purchase_id)}, status=201)


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
