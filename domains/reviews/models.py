import uuid
from django.db import models
from django.contrib.auth import get_user_model
from domains.catalog.models import Product

User = get_user_model()

class Review(models.Model):
    review_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column="user_id", related_name="reviews")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, db_column="product_id", related_name="reviews")
    rating = models.PositiveSmallIntegerField()  # 1~5
    content = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "reviews"
        constraints = [
            models.UniqueConstraint(fields=["user", "product"], name="uniq_review_user_product"),  # 한 상품 1인 1리뷰
        ]
        indexes = [
            models.Index(fields=["product"]),
            models.Index(fields=["user"]),
        ]

    def __str__(self):
        return f"Review({self.review_id}) {self.user_id}->{self.product_id}"
