# tests/conftest.py
import pytest
from uuid import uuid4
from django.contrib.auth import get_user_model
from domains.catalog.models import Category, Product

@pytest.fixture
def user_factory(db):
    def _make_user(**kwargs):
        User = get_user_model()

        password = kwargs.pop("password", "pass1234!")
        # username 없으면 유니크 값 생성
        if "username" not in kwargs:
            kwargs["username"] = f"u{uuid4().hex[:6]}"

        # email 없으면 username 기반으로 고유 이메일 생성
        if "email" not in kwargs:
            kwargs["email"] = f"{kwargs['username']}@test.local"

        user = User(**kwargs)
        user.is_active = kwargs.get("is_active", True)
        user.set_password(password)
        user.save()
        user.raw_password = password
        return user
    return _make_user


@pytest.fixture
def category(db):
    return Category.objects.create(name="Top")


@pytest.fixture
def product_factory(db, category):
    def _make_product(**kwargs):
        defaults = dict(
            name=kwargs.pop("name", "Tee"),
            description=kwargs.pop("description", ""),
            price=kwargs.pop("price", 10000),
            category=kwargs.pop("category", category),
            is_active=kwargs.pop("is_active", True),
        )
        return Product.objects.create(**defaults)
    return _make_product
