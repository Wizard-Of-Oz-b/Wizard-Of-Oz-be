from rest_framework import serializers
from domains.wishlists.models import WishlistItem
from domains.catalog.models import Product
from domains.catalog.serializers import ProductImageSlim

class WishlistItemReadSerializer(serializers.ModelSerializer):
    wishlist_id  = serializers.UUIDField(read_only=True)
    user_id      = serializers.UUIDField(source="user.id", read_only=True)
    product_id   = serializers.UUIDField(source="product.id", read_only=True)
    product_name = serializers.CharField(source="product.name", read_only=True)
    price        = serializers.DecimalField(source="product.price", max_digits=12, decimal_places=2, read_only=True)
    primary_image = serializers.SerializerMethodField()

    class Meta:
        model  = WishlistItem
        fields = ("wishlist_id","user_id","product_id","product_name","price","option_key","options","primary_image","created_at")

    def get_primary_image(self, obj):
        request = self.context.get("request")
        imgs = getattr(obj.product, "images", None)
        if imgs is None:
            return None
        items = [ProductImageSlim.from_instance(img, request) for img in imgs.all()]
        for it in items:
            if it.get("url"):
                return it
        return None

class WishlistItemWriteSerializer(serializers.ModelSerializer):
    product_id = serializers.UUIDField()
    option_key = serializers.CharField(required=False, allow_blank=True, default="")
    options    = serializers.JSONField(required=False, default=dict)

    class Meta:
        model  = WishlistItem
        fields = ("product_id","option_key","options")

    def validate_product_id(self, v):
        if not Product.objects.filter(pk=v).exists():
            raise serializers.ValidationError("product not found")
        return v

    def create(self, validated):
        user = self.context["request"].user
        pid  = validated.pop("product_id")
        validated.setdefault("option_key", "")
        validated.setdefault("options", {})
        obj, created = WishlistItem.objects.get_or_create(
            user=user, product_id=pid, option_key=validated["option_key"],
            defaults={"options": validated["options"]}
        )
        if not created and validated.get("options"):
            obj.options = validated["options"]; obj.save(update_fields=["options"])
        return obj
