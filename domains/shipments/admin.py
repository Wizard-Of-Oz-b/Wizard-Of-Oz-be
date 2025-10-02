from __future__ import annotations

from django.contrib import admin
from django.utils.html import format_html

from . import models


# ---------- 유틸: 동적 필드 접근 ----------
def pick_attr(obj, *candidates, default=None):
    """obj에서 첫 번째로 존재하는 속성을 반환"""
    for name in candidates:
        if hasattr(obj, name):
            return getattr(obj, name)
    return default


# ---------- ShipmentEvent Inline ----------
class ShipmentEventInline(admin.TabularInline):
    model = models.ShipmentEvent
    extra = 0
    can_delete = False
    readonly_fields = ("occurred_at", "status", "location", "description", "provider_code")

    def occurred_at(self, obj):
        return pick_attr(obj, "occurred_at", "time_sweet", "time_trans", "created_at")

    def status(self, obj):
        value = pick_attr(obj, "status", "state", "delivery_status")
        for name in ("status", "state", "delivery_status"):
            disp = f"get_{name}_display"
            if hasattr(obj, disp):
                return getattr(obj, disp)()
        return value

    def location(self, obj):
        return pick_attr(obj, "location", "where")

    def description(self, obj):
        return pick_attr(obj, "description", "details")

    def provider_code(self, obj):
        return pick_attr(obj, "provider_code", "comcode")


# ---------- Shipment Admin ----------
@admin.register(models.Shipment)
class ShipmentAdmin(admin.ModelAdmin):
    inlines = [ShipmentEventInline]

    list_display = (
        "id",
        "user_display",
        "carrier_display",
        "invoice_no_display",
        "status_display",
        "last_event_at",
        "created_at",
    )

    # 'fid' 제거, 실제 존재하는 필드/콜러블만 배치
    readonly_fields = ("id", "created_at", "updated_at", "last_event_at")

    # search_fields 는 모델 실제 필드명만 허용됨
    search_fields = ("id", "tracking_number", "carrier")

    class CarrierFilter(admin.SimpleListFilter):
        title = "Carrier"
        parameter_name = "carrier"

        def lookups(self, request, model_admin):
            # 동적 결정 대신 DB 실필드인 'carrier'만 사용
            qs = (
                models.Shipment.objects
                .order_by()
                .values_list("carrier", flat=True)
                .distinct()[:50]
            )
            return [(v, v) for v in qs if v]

        def queryset(self, request, queryset):
            if self.value():
                return queryset.filter(carrier=self.value())
            return queryset

    class StatusFilter(admin.SimpleListFilter):
        title = "Status"
        parameter_name = "status"

        def lookups(self, request, model_admin):
            field_name = model_admin._status_field_name
            if not field_name:
                return []
            field = models.Shipment._meta.get_field(field_name)
            if getattr(field, "choices", None):
                return list(field.choices)
            qs = (
                models.Shipment.objects
                .order_by()
                .values_list(field_name, flat=True)
                .distinct()[:50]
            )
            return [(v, v) for v in qs if v]

        def queryset(self, request, queryset):
            field_names = {f.name for f in queryset.model._meta.get_fields() if hasattr(f, "name")}
            field_name = next((n for n in ("status", "state", "delivery_status") if n in field_names), None)
            if field_name and self.value():
                return queryset.filter(**{field_name: self.value()})
            return queryset

    list_filter = (CarrierFilter, StatusFilter)

    ordering = ("-id",)

    # ----- 동적 필드 이름 캐시 -----
    @property
    def _carrier_field_name(self):
        for name in ("carrier", "carrier_code", "provider", "shipper"):
            if name in self._field_names:
                return name
        return None

    @property
    def _status_field_name(self):
        for name in ("status", "state", "delivery_status"):
            if name in self._field_names:
                return name
        return None

    @property
    def _last_event_field_name(self):
        for name in ("last_event_at", "last_status_at", "latest_event_at", "updated_at"):
            if name in self._field_names:
                return name
        return None

    @property
    def _field_names(self):
        return {f.name for f in models.Shipment._meta.get_fields() if hasattr(f, "name")}

    # ----- list_display / readonly_fields용 콜러블 -----
    def user_display(self, obj):
        u = pick_attr(obj, "user", "owner", "customer")
        if not u:
            return "-"
        return getattr(u, "email", None) or getattr(u, "username", None) or str(u)
    user_display.short_description = "User"

    def carrier_display(self, obj):
        value = pick_attr(obj, "carrier", "carrier_code", "provider")
        for name in ("carrier", "carrier_code", "provider"):
            disp = f"get_{name}_display"
            if hasattr(obj, disp):
                return getattr(obj, disp)()
        return value or "-"

    def invoice_no_display(self, obj):
        return pick_attr(obj, "invoice_no", "tracking_number", "waybill_no", default="-")
    invoice_no_display.short_description = "Invoice/Tracking"

    def status_display(self, obj):
        value = pick_attr(obj, "status", "state", "delivery_status")
        for name in ("status", "state", "delivery_status"):
            disp = f"get_{name}_display"
            if hasattr(obj, disp):
                return getattr(obj, disp)()
        return value or "-"

    def created_at(self, obj):
        return pick_attr(obj, "created_at", "time_created", "inserted_at")

    def updated_at(self, obj):
        return pick_attr(obj, "updated_at", "modified_at", "time_updated")

    def last_event_at(self, obj):
        fname = self._last_event_field_name
        return getattr(obj, fname) if fname else None


# ---------- ShipmentEvent Admin ----------
@admin.register(models.ShipmentEvent)
class ShipmentEventAdmin(admin.ModelAdmin):
    list_display = ("id", "occurred_at", "status", "location", "description", "provider_code")
    readonly_fields = ("raw_payload",)
    ordering = ("-id",)
    search_fields = ("description", "provider_code")

    def occurred_at(self, obj):
        return pick_attr(obj, "occurred_at", "time_sweet", "time_trans", "created_at")

    def status(self, obj):
        value = pick_attr(obj, "status", "state", "delivery_status")
        for name in ("status", "state", "delivery_status"):
            disp = f"get_{name}_display"
            if hasattr(obj, disp):
                return getattr(obj, disp)()
        return value

    def location(self, obj):
        return pick_attr(obj, "location", "where")

    def description(self, obj):
        return pick_attr(obj, "description", "details")

    def provider_code(self, obj):
        return pick_attr(obj, "provider_code", "comcode")

    def raw_payload(self, obj):
        value = pick_attr(obj, "raw_payload", "payload", "data", "response_json")
        if value is None:
            return "-"
        return format_html("<pre style='white-space:pre-wrap'>{}</pre>", value)
