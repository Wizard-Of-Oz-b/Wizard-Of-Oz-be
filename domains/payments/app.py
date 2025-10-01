from django.apps import AppConfig

class PaymentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "domains.payments"   # 모듈 경로
    label = "payments"          # 앱 라벨 (models 참조/관리자 등에서 사용)
