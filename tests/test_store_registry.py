import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import store_registry


@pytest.fixture
def registry_path(tmp_path):
    original = store_registry._STORE_REGISTRY_PATH
    path = tmp_path / "stores.json"
    store_registry.set_registry_path(path)
    yield path
    store_registry.set_registry_path(original)


def test_add_store_persists_and_sanitizes(registry_path):
    payload = store_registry.StoreCreate(
        store_domain="BabyShop.MyShopify.com",
        niche="baby",
        shopify_token="shpat_testtoken12345",
        template_pack="baby-branding",
        brand_name="Baby Shop",
    )
    public = store_registry.add_store(payload)

    assert public.store_domain == "babyshop.myshopify.com"
    assert public.has_token is True
    assert public.template_pack == "baby-branding"
    assert public.brand_name == "Baby Shop"

    raw = json.loads(registry_path.read_text(encoding="utf-8"))
    assert raw[0]["shopify_token"] == "shpat_testtoken12345"
    assert raw[0]["store_domain"] == "babyshop.myshopify.com"

    with pytest.raises(ValueError):
        store_registry.add_store(payload)


def test_stores_add_endpoint(monkeypatch, registry_path):
    monkeypatch.setattr("app.shopify_client.validate_shopify_config", lambda: "UTC")
    monkeypatch.setattr("app.shopify_client.requests", None)
    monkeypatch.setenv("SHOPIFY_MODE", "safe")

    import importlib

    main = importlib.reload(__import__("main"))
    client = TestClient(main.app)

    response = client.post(
        "/stores/add",
        json={
            "store_domain": "HomeShop.myshopify.com",
            "niche": "home",
            "shopify_token": "shpat_fakehome12345",
            "template_pack": "home-templates",
            "brand_name": "Home Shop",
        },
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["store_domain"] == "homeshop.myshopify.com"
    assert body["has_token"] is True
    assert "shopify_token" not in body

    stored = json.loads(registry_path.read_text(encoding="utf-8"))
    assert stored[0]["shopify_token"] == "shpat_fakehome12345"
