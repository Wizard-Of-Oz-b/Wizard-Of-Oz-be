# tests/conftest.py
import pytest
from django.contrib.auth import get_user_model
from domains.catalog.models import Category, Product


@pytest.fixture
def user_factory(db):
    """
    사용법:
        user = user_factory(username="alice", password="pw1234")
    반환: 저장된 User 인스턴스 (user.raw_password 로 평문도 들고 있음)
    """
    def _make_user(**kwargs):
        User = get_user_model()
        password = kwargs.pop("password", "pass1234!")
        # username 미지정 시 유니크로 자동 생성
        if "username" not in kwargs:
            from uuid import uuid4
            kwargs["username"] = f"u{uuid4().hex[:6]}"

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
    """
    사용법:
        product = product_factory(name="Tee", price=10000)
    """
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
