import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
app = Celery("config")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()  # domains.shipments.tasks 자동 발견
CELERY_BEAT_SCHEDULE = {
    "poll-open-shipments-every-120s": {
        "task": "domains.shipments.tasks.poll_open_shipments",
        "schedule": 120.0,
    },
}
