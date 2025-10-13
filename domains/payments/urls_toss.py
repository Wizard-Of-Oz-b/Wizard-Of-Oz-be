from django.urls import path

from .views_toss import PaymentRetrieveAPI, TossCancelAPI, TossConfirmAPI, TossSyncAPI

app_name = "payments_toss"

urlpatterns = [
    path("confirm/", TossConfirmAPI.as_view(), name="confirm"),  # POST
    path("<uuid:payment_id>/", PaymentRetrieveAPI.as_view(), name="retrieve"),  # GET
    path("<uuid:payment_id>/cancel/", TossCancelAPI.as_view(), name="cancel"),  # POST
    path("<uuid:payment_id>/sync/", TossSyncAPI.as_view(), name="sync"),  # POST
]
