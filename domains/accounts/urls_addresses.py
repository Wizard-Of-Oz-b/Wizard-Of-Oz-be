from django.urls import path

from .views_addresses import (
    MyAddressDetailAPI,
    MyAddressListCreateAPI,
    SetDefaultAddressAPI,
)

urlpatterns = [
    path("users/me/addresses/", MyAddressListCreateAPI.as_view(), name="my-addresses"),
    path(
        "users/me/addresses/<uuid:address_id>/",
        MyAddressDetailAPI.as_view(),
        name="my-address-detail",
    ),
    path(
        "users/me/addresses/<uuid:address_id>/set-default/",
        SetDefaultAddressAPI.as_view(),
        name="my-address-set-default",
    ),
]
