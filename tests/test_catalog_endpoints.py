import pytest
from rest_framework.test import APIClient

@pytest.mark.django_db
def test_catalog_list_and_product_detail(product_factory):
    p = product_factory()
    c = APIClient()

    r = c.get("/api/v1/categories/")
    assert r.status_code == 200

    r = c.get("/api/v1/products/")
    assert r.status_code == 200

    r = c.get(f"/api/v1/products/{p.id}/")
    assert r.status_code == 200
