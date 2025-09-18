# domains/shipments/tasks.py
from celery import shared_task

@shared_task(bind=True, max_retries=3, retry_backoff=True, retry_jitter=True)
def poll_shipment(self, carrier: str, tracking_number: str):
    # 지연 임포트(순환/초기화 이슈 회피)
    from .adapters import get_adapter
    from .services import sync_by_tracking
    try:
        ad = get_adapter(carrier)
        sync_by_tracking(carrier, tracking_number, ad)
    except Exception as e:
        raise self.retry(exc=e)

@shared_task
def poll_open_shipments():
    from .models import Shipment
    qs = Shipment.objects.filter(status__in=["pending", "in_transit", "out_for_delivery"])
    for s in qs.iterator():
        poll_shipment.delay(s.carrier, s.tracking_number)
