from __future__ import annotations

import mimetypes
import os
import uuid
from urllib.parse import urlparse
from urllib.request import urlopen

from django import forms
from django.contrib import admin
from django.core.files.base import ContentFile
from django.utils.html import format_html

from .models import Category, Product, ProductImage, ProductStock


# ---- 안전 URL 헬퍼 -------------------------------------------------
def _safe_file_url(f) -> str | None:
    """
    ImageFieldFile 같은 파일 객체에서, 실제 파일이 있을 때만 .url 반환.
    """
    try:
        if not f:
            return None
        name = getattr(f, "name", "")
        if not name:
            return None
        return f.url  # 여기서만 접근
    except Exception:
        return None


def _thumb_html(image_url: str | None, size: int = 60) -> str:
    if not image_url:
        return "—"
    return format_html(
        '<img src="{}" style="height:{}px;width:auto;border-radius:8px;" />',
        image_url,
        size,
    )


# -------- Category -------------------------------------------------
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "parent", "level", "path", "created_at")
    list_filter = ("level",)
    search_fields = ("name", "path")
    ordering = ("path",)


# -------- Inline: ProductStock ------------------------------------
class ProductStockInline(admin.TabularInline):
    model = ProductStock
    extra = 0
    fields = ("option_key", "stock_quantity")
    ordering = ("option_key",)


# -------- Inline: ProductImage (파일/URL/원격 다운로드) -------------
class ProductImageInlineForm(forms.ModelForm):
    fetch_remote = forms.BooleanField(
        required=False,
        label="원격 URL을 파일로 저장",
        help_text="체크 시 remote_url 이미지를 받아 image 파일로 저장합니다.",
    )

    class Meta:
        model = ProductImage
        fields = "__all__"

    def save(self, commit=True):
        obj: ProductImage = super().save(commit=False)

        if (
            self.cleaned_data.get("fetch_remote")
            and not obj.image
            and getattr(obj, "remote_url", "")
        ):
            try:
                resp = urlopen(obj.remote_url, timeout=10)
                data = resp.read()

                parsed = urlparse(obj.remote_url)
                base = os.path.basename(parsed.path) or uuid.uuid4().hex
                if "." not in base:
                    ext = (
                        mimetypes.guess_extension(resp.headers.get_content_type() or "")
                        or ".jpg"
                    )
                    base = base + ext

                obj.image.save(base, ContentFile(data), save=False)
            except Exception:
                pass

        if commit:
            obj.save()
            self.save_m2m()
        return obj


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    form = ProductImageInlineForm
    extra = 1
    fields = (
        "preview",
        "image",
        "remote_url",
        "alt_text",
        "caption",
        "is_main",
        "display_order",
        "fetch_remote",
    )
    readonly_fields = ("preview",)

    def preview(self, obj: ProductImage):
        url = _safe_file_url(getattr(obj, "image", None)) or getattr(
            obj, "remote_url", None
        )
        return _thumb_html(url)


# -------- Product --------------------------------------------------
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    inlines = [ProductStockInline, ProductImageInline]
    list_display = (
        "name",
        "category",
        "price",
        "is_active",
        "image_count",
        "main_thumb",
        "updated_at",
    )
    list_filter = ("is_active", "category")
    search_fields = ("name",)
    autocomplete_fields = ("category",)
    ordering = ("-updated_at",)

    def image_count(self, obj: Product):
        return obj.images.count()

    image_count.short_description = "이미지 수"

    def main_thumb(self, obj: Product):
        main = (
            obj.images.filter(is_main=True).first()
            or obj.images.order_by("display_order", "created_at").first()
        )
        url = _safe_file_url(getattr(main, "image", None)) or (
            getattr(main, "remote_url", None) if main else None
        )
        return _thumb_html(url, size=48)

    main_thumb.short_description = "대표"


# -------- ProductImage (개별 관리) ---------------------------------
@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = (
        "thumb",
        "product",
        "is_main",
        "display_order",
        "remote_url",
        "created_at",
    )
    list_filter = ("is_main", "product")
    search_fields = ("product__name", "alt_text", "caption")
    ordering = ("product", "display_order", "-created_at")
    readonly_fields = ("thumb",)
    fields = (
        "thumb",
        "product",
        "stock",
        "image",
        "remote_url",
        "alt_text",
        "caption",
        "is_main",
        "display_order",
    )

    def thumb(self, obj: ProductImage):
        url = _safe_file_url(getattr(obj, "image", None)) or getattr(
            obj, "remote_url", None
        )
        return _thumb_html(url)

    actions = ["set_as_main"]

    def set_as_main(self, request, queryset):
        grouped: dict[Product, list[ProductImage]] = {}
        for img in queryset:
            grouped.setdefault(img.product, []).append(img)

        for product, imgs in grouped.items():
            ProductImage.objects.filter(product=product, is_main=True).update(
                is_main=False
            )
            imgs[0].is_main = True
            imgs[0].save(update_fields=["is_main"])

    set_as_main.short_description = "선택 이미지를 대표로 지정(상품별 1개)"


# -------- ProductStock --------------------------------------------
@admin.register(ProductStock)
class ProductStockAdmin(admin.ModelAdmin):
    list_display = ("product", "option_key", "stock_quantity", "updated_at")
    search_fields = ("product__name", "option_key")
    autocomplete_fields = ("product",)
    ordering = ("product", "option_key")
