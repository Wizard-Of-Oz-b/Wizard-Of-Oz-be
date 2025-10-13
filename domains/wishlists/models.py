import uuid

from django.conf import settings
from django.db import models

from domains.catalog.models import Product


class WishlistItem(models.Model):
    wishlist_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="wishlist_items",
    )
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="wishlisted_by"
    )
    option_key = models.CharField(max_length=64, default="", blank=True)
    options = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "wishlist_items"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "product", "option_key"],
                name="uq_wishlist_user_product_option",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["product"]),
        ]

    def __str__(self):
        return f"{self.user_id} ♥ {self.product_id} ({self.option_key or '-'})"
