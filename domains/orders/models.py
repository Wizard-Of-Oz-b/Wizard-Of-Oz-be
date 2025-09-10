from django.db import models
from django.contrib.auth import get_user_model
from domains.catalog.models import Product

User = get_user_model()

class Purchase(models.Model):
    STATUS_PAID = "paid"
    STATUS_CANCELED = "canceled"
    STATUS_REFUNDED = "refunded"
    STATUS_CHOICES = [
        (STATUS_PAID, "Paid"),
        (STATUS_CANCELED, "Canceled"),
        (STATUS_REFUNDED, "Refunded"),
    ]

    purchase_id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column="user_id", related_name="purchases")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, db_column="product_id", related_name="purchases")
    amount = models.PositiveIntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PAID)
    purchased_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "purchases"
        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["product"]),
            models.Index(fields=["status"]),
            models.Index(fields=["purchased_at"]),
        ]

    def __str__(self):
        return f"Purchase({self.purchase_id}) {self.user_id}->{self.product_id} {self.status}"
