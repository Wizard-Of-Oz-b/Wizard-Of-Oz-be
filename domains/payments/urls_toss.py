from django.urls import path
from .views_toss import (
    TossClientKeyAPI, TossConfirmAPI,
    TossCancelAPI, TossWebhookAPI,  # 취소/웹훅은 선택
)

urlpatterns = [
    path("client-key/", TossClientKeyAPI.as_view()),     # GET  클라이언트 키 전달(프론트 편의)
    path("confirm/",    TossConfirmAPI.as_view()),       # POST 성공 리다이렉트 후 승인
    path("cancel/",     TossCancelAPI.as_view()),        # POST 환불/취소 (선택)
    path("webhook/",    TossWebhookAPI.as_view()),       # POST 웹훅 검증 (선택)
]
