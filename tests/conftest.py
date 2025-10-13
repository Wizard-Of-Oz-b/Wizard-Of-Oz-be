# tests/conftest.py
from uuid import uuid4

from django.conf import settings
from django.contrib.auth import get_user_model

import pytest
from rest_framework.test import APIClient

from domains.catalog.models import Category, Product, ProductStock

User = get_user_model()


# ─────────────────────────────────────────────────────────────
# 전역 테스트 환경 최적화(해싱/메일)
# ─────────────────────────────────────────────────────────────
@pytest.fixture(autouse=True, scope="session")
def _fast_password_hasher(django_db_setup, django_db_blocker):
    """
    해시 느린 기본 해셔 대신 MD5 해셔 사용, 이메일은 메모리 백엔드 사용
    """
    with django_db_blocker.unblock():
        settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
        settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"


# ─────────────────────────────────────────────────────────────
# 클라이언트 & 인증
# ─────────────────────────────────────────────────────────────
@pytest.fixture
def api_client():
    return APIClient()


def _model_has_field(model, name: str) -> bool:
    return name in {f.name for f in model._meta.get_fields()}


@pytest.fixture
def user(db):
    """
    기본 로그인 사용자 (username 필수 모델이면 자동 생성)
    """
    kwargs = {}
    if _model_has_field(User, "username"):
        kwargs["username"] = f"user_{uuid4().hex[:6]}"
    if _model_has_field(User, "email"):
        kwargs["email"] = "user@example.com"
    if _model_has_field(User, "role"):
        kwargs["role"] = "user"
    if _model_has_field(User, "status"):
        kwargs["status"] = "active"

    password = "Test1234!A"
    u = User.objects.create_user(password=password, **kwargs)
    # ✅ 로그인 테스트용 원문 비밀번호 보관
    u.raw_password = password
    return u


@pytest.fixture
def admin(db):
    """
    관리자 사용자 (staff/superuser 플래그 세팅)
    """
    kwargs = {}
    if _model_has_field(User, "username"):
        kwargs["username"] = f"admin_{uuid4().hex[:6]}"
    if _model_has_field(User, "email"):
        kwargs["email"] = "admin@example.com"
    if _model_has_field(User, "role"):
        kwargs["role"] = "admin"
    if _model_has_field(User, "status"):
        kwargs["status"] = "active"

    password = "Test1234!A"
    u = User.objects.create_user(password=password, **kwargs)
    if hasattr(u, "is_staff"):
        u.is_staff = True
    if hasattr(u, "is_superuser"):
        u.is_superuser = True
    u.save(update_fields=[f for f in ["is_staff", "is_superuser"] if hasattr(u, f)])
    # ✅ 로그인 테스트용 원문 비밀번호 보관
    u.raw_password = password
    return u


@pytest.fixture
def auth_client(user):
    """
    SimpleJWT 토큰을 받아 Authorization 헤더 세팅된 APIClient 반환
    """
    c = APIClient()
    resp = c.post(
        "/api/v1/auth/token/",
        {
            "email": getattr(user, "email", "user@example.com"),
            "password": user.raw_password,
        },
        format="json",
    )
    assert resp.status_code == 200, getattr(resp, "data", resp.content)
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {resp.data['access']}")
    return c


@pytest.fixture
def admin_client(admin):
    c = APIClient()
    resp = c.post(
        "/api/v1/auth/token/",
        {
            "email": getattr(admin, "email", "admin@example.com"),
            "password": admin.raw_password,
        },
        format="json",
    )
    assert resp.status_code == 200, getattr(resp, "data", resp.content)
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {resp.data['access']}")
    return c


# ─────────────────────────────────────────────────────────────
# 카탈로그 기본 리소스
# ─────────────────────────────────────────────────────────────
@pytest.fixture
def category(db):
    return Category.objects.create(name="상의")


@pytest.fixture
def product(db, category):
    """
    옵션이 있는 기본 상품
    """
    return Product.objects.create(
        category=category,
        name="베이직 티셔츠",
        price="19900",
        is_active=True,
        options={"size": ["S", "M", "L"], "color": ["black", "white"]},
    )


# ─────────────────────────────────────────────────────────────
# 옵션키 정규화 & 재고 유틸
# ─────────────────────────────────────────────────────────────
def _make_option_key(options: dict | None) -> str:
    if not options:
        return ""
    pairs = [f"{k}={options[k]}" for k in sorted(options)]
    return "&".join(pairs)


@pytest.fixture
def make_option_key():
    return _make_option_key


@pytest.fixture
def create_stock(db):
    """
    사용법: create_stock(product, {"size":"L","color":"black"}, 5)
    """

    def _create(product, options: dict | None, quantity: int):
        ok = _make_option_key(options)
        return ProductStock.objects.create(
            product=product, option_key=ok, stock_quantity=quantity
        )

    return _create


@pytest.fixture
def get_stock_quantity(db):
    def _get(product, options: dict | None):
        ok = _make_option_key(options)
        return ProductStock.objects.get(product=product, option_key=ok).stock_quantity

    return _get


@pytest.fixture
def set_stock_quantity(db):
    def _set(product, options: dict | None, qty: int):
        ok = _make_option_key(options)
        ps = ProductStock.objects.get(product=product, option_key=ok)
        ps.stock_quantity = qty
        ps.save(update_fields=["stock_quantity"])
        return ps

    return _set


# ─────────────────────────────────────────────────────────────
# 장바구니/체크아웃/결제 승인 헬퍼
# ─────────────────────────────────────────────────────────────
@pytest.fixture
def add_to_cart():
    def _add(client: APIClient, product, options: dict | None, qty: int = 1):
        body = {
            "product": str(product.id),
            "options": options or {},
            "quantity": qty,
        }
        r = client.post("/api/v1/carts/items/", body, format="json")  # 끝 슬래시 유지
        assert r.status_code in (200, 201), getattr(r, "data", r.content)
        return r

    return _add


@pytest.fixture
def checkout():
    """
    장바구니 전체 → Purchase 생성
    """

    def _checkout(client: APIClient):
        r = client.post("/api/v1/orders/checkout/")
        assert r.status_code in (200, 201), getattr(r, "data", r.content)
        return r.json()  # {"id": "...", ...}

    return _checkout


@pytest.fixture
def confirm_payment():
    def _confirm(client: APIClient, purchase_id):
        r = client.post(
            f"/api/v1/orders/purchases/{purchase_id}/confirm/"
        )  # 끝 슬래시 유지
        assert r.status_code in (200, 204), getattr(r, "data", r.content)
        return r

    return _confirm


@pytest.fixture
def checkout_and_confirm(add_to_cart, checkout, confirm_payment):
    """
    사용법:
      pid = checkout_and_confirm(client, product, {"size":"L"}, qty=2)
    """

    def _flow(client: APIClient, product, options: dict | None, qty: int = 1):
        add_to_cart(client, product, options, qty)
        purchase = checkout(client)
        purchase_id = purchase["id"]
        confirm_payment(client, purchase_id)
        return purchase_id

    return _flow


# ─────────────────────────────────────────────────────────────
# 팩토리 픽스처 (동적으로 여러 개 만들 때)
# ─────────────────────────────────────────────────────────────
@pytest.fixture
def user_factory(db):
    def _make(**kw):
        email = kw.pop("email", f"user{uuid4().hex[:6]}@example.com")
        password = kw.pop("password", "Test1234!A")

        # username 자동 세팅
        if _model_has_field(User, "username") and "username" not in kw:
            base = email.split("@")[0]
            kw["username"] = f"{base}_{uuid4().hex[:6]}"

        if _model_has_field(User, "role") and "role" not in kw:
            kw["role"] = "user"
        if _model_has_field(User, "status") and "status" not in kw:
            kw["status"] = "active"

        if _model_has_field(User, "email"):
            kw.setdefault("email", email)

        u = User.objects.create_user(password=password, **kw)
        # ✅ 로그인 테스트용 원문 비밀번호 보관
        u.raw_password = password
        return u

    return _make


@pytest.fixture
def product_factory(db):
    def _make(**kw):
        category = kw.pop("category", None)
        if category is None:
            category, _ = Category.objects.get_or_create(
                name=kw.pop("category_name", "상의")
            )

        name = kw.pop("name", "베이직 티셔츠")
        price = kw.pop("price", "19900")
        is_active = kw.pop("is_active", True)
        options = kw.pop("options", {"size": ["S", "M", "L"]})

        return Product.objects.create(
            category=category,
            name=name,
            price=price,
            is_active=is_active,
            options=options,
            **kw,
        )

    return _make
