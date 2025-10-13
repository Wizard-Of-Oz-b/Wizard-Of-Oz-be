import itertools
from uuid import uuid4

from django.contrib.auth import get_user_model

from domains.catalog.models import Category, Product

_email_seq = itertools.count(1)
User = get_user_model()


def unique_email(prefix="user", domain="example.com"):
    return f"{prefix}{next(_email_seq)}@{domain}"


def _model_has_field(model, field_name: str) -> bool:
    return field_name in {f.name for f in model._meta.get_fields()}


def create_user(
    email=None, password="Test1234!A", role="user", status="active", **extra
):
    """
    - username 필드가 있는 모델(AbstractUser 계열)이면 username을 자동 세팅
    - role/status 같은 커스텀 필드는 모델에 있을 때만 넣음
    """
    if email is None:
        email = unique_email()

    fields = {}
    if _model_has_field(User, "email"):
        fields["email"] = email
    if _model_has_field(User, "username"):
        # 이메일 앞부분으로 username 생성(중복 방지 suffix)
        base = email.split("@")[0]
        fields["username"] = f"{base}_{uuid4().hex[:6]}"
    if _model_has_field(User, "role"):
        fields["role"] = role
    if _model_has_field(User, "status"):
        fields["status"] = status

    fields.update(extra)
    return User.objects.create_user(password=password, **fields)


def create_product(
    name="베이직 티셔츠",
    price="19900",
    options=None,
    category_name="상의",
    is_active=True,
):
    cat, _ = Category.objects.get_or_create(name=category_name)
    return Product.objects.create(
        category=cat,
        name=name,
        price=price,
        is_active=is_active,
        options=options or {},
    )


def make_option_key(options: dict | None):
    if not options:
        return ""
    pairs = [f"{k}={options[k]}" for k in sorted(options)]
    return "&".join(pairs)
