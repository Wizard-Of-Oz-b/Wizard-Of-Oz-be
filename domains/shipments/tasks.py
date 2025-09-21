# domains/shipments/tasks.py
from celery import shared_task

@shared_task(
    bind=True,
    acks_late=True,
    max_retries=3,
    retry_backoff=True,
    retry_jitter=True,
    name="domains.shipments.tasks.poll_shipment",
)
def poll_shipment(self, carrier: str, tracking_number: str):
    # 지연 임포트(순환/초기화 이슈 회피)
    from .adapters import get_adapter
    from .services import sync_by_tracking
    try:
        ad = get_adapter(carrier)
        # fetch_tracking -> parse_events -> upsert까지 services가 처리
        created = sync_by_tracking(carrier, tracking_number, ad)
        return created
    except Exception as e:
        raise self.retry(exc=e)


@shared_task(name="domains.shipments.tasks.poll_open_shipments")
def poll_open_shipments():
    from .models import Shipment, ShipmentStatus
    qs = Shipment.objects.filter(
        status__in=[ShipmentStatus.PENDING, ShipmentStatus.IN_TRANSIT, ShipmentStatus.OUT_FOR_DELIVERY]
    )
    for s in qs.iterator():
        poll_shipment.delay(s.carrier, s.tracking_number)
