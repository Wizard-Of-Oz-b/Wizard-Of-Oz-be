from django.db import models

class Category(models.Model):
    category_id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=255)
    parent = models.ForeignKey("self", null=True, blank=True,
                               on_delete=models.SET_NULL, db_column="parent_id",
                               related_name="children")
    class Meta:
        db_table = "categories"
        indexes = [models.Index(fields=["parent"]), models.Index(fields=["name"])]

class Product(models.Model):
    product_id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    price = models.IntegerField()
    category = models.ForeignKey(Category, null=True, blank=True,
                                 on_delete=models.SET_NULL, db_column="category_id",
                                 related_name="products")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = "products"
        indexes = [models.Index(fields=["name"]), models.Index(fields=["price"])]
