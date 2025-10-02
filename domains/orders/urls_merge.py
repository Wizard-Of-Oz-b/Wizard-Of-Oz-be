# domains/orders/urls_merge.py
from django.urls import path

from .views_merge import (
    CancelMergedOrderAPI,
    DeleteReadyOrdersAPI,
    DeleteSingleReadyOrderAPI,
    MergeOrdersAPI,
    ReadyOrdersSummaryAPI,
)

urlpatterns = [
    path(
        "ready-summary/",
        ReadyOrdersSummaryAPI.as_view(),
        name="ready-orders-summary"
    ),
    path(
        "merge/",
        MergeOrdersAPI.as_view(),
        name="merge-orders"
    ),
    path(
        "cancel-merged/",
        CancelMergedOrderAPI.as_view(),
        name="cancel-merged-order"
    ),
    path(
        "delete-ready/",
        DeleteReadyOrdersAPI.as_view(),
        name="delete-ready-orders"
    ),
    path(
        "delete-ready-single/",
        DeleteSingleReadyOrderAPI.as_view(),
        name="delete-single-ready-order"
    ),
]
