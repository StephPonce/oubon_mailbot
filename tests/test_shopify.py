import re
from types import SimpleNamespace

import responses

from app.shopify_client import _shopify_get


@responses.activate
def test_shopify_get(monkeypatch):
    monkeypatch.setattr(
        "app.shopify_client._get_shopify_env",
        lambda: ("shpat_testtoken", "example.myshopify.com", "safe"),
    )
    monkeypatch.setattr(
        "app.shopify_client.Settings",
        lambda: SimpleNamespace(SHOPIFY_API_VERSION="2024-10"),
    )

    responses.add(
        responses.GET,
        re.compile(r".*/shop\.json"),
        json={"shop": {"iana_timezone": "UTC"}},
        status=200,
    )
    assert _shopify_get("/shop.json", {})["shop"]["iana_timezone"] == "UTC"

    responses.add(responses.GET, re.compile(r".*/shop\.json"), status=404)
    assert _shopify_get("/shop.json", {}) is None


@responses.activate
def test_shopify_get_bad_token(monkeypatch):
    monkeypatch.setattr(
        "app.shopify_client._get_shopify_env",
        lambda: ("bad_token", "example.myshopify.com", "safe"),
    )
    monkeypatch.setattr(
        "app.shopify_client.Settings",
        lambda: SimpleNamespace(SHOPIFY_API_VERSION="2024-10"),
    )

    responses.add(responses.GET, re.compile(r".*/shop\.json"), status=401)
    assert _shopify_get("/shop.json", {}) is None


@responses.activate
def test_shopify_get_rate_limit(monkeypatch):
    monkeypatch.setattr(
        "app.shopify_client._get_shopify_env",
        lambda: ("shpat_rate", "example.myshopify.com", "safe"),
    )
    monkeypatch.setattr(
        "app.shopify_client.Settings",
        lambda: SimpleNamespace(SHOPIFY_API_VERSION="2024-10"),
    )

    responses.add(responses.GET, re.compile(r".*/shop\.json"), status=429)
    assert _shopify_get("/shop.json", {}) is None


@responses.activate
def test_shopify_get_timeout(monkeypatch):
    monkeypatch.setattr(
        "app.shopify_client._get_shopify_env",
        lambda: ("shpat_timeout", "example.myshopify.com", "safe"),
    )
    monkeypatch.setattr(
        "app.shopify_client.Settings",
        lambda: SimpleNamespace(SHOPIFY_API_VERSION="2024-10"),
    )

    responses.add(responses.GET, re.compile(r".*/shop\.json"), body=b"Timeout", status=504)
    assert _shopify_get("/shop.json", {}) is None


@responses.activate
def test_shopify_get_missing_data(monkeypatch):
    monkeypatch.setattr(
        "app.shopify_client._get_shopify_env",
        lambda: ("shpat_missing", "example.myshopify.com", "safe"),
    )
    monkeypatch.setattr(
        "app.shopify_client.Settings",
        lambda: SimpleNamespace(SHOPIFY_API_VERSION="2024-10"),
    )

    responses.add(responses.GET, re.compile(r".*/shop\.json"), json={}, status=200)
    assert _shopify_get("/shop.json", {}) is None


@responses.activate
def test_shopify_get_partial_data(monkeypatch):
    monkeypatch.setattr(
        "app.shopify_client._get_shopify_env",
        lambda: ("shpat_partial", "example.myshopify.com", "safe"),
    )
    monkeypatch.setattr(
        "app.shopify_client.Settings",
        lambda: SimpleNamespace(SHOPIFY_API_VERSION="2024-10"),
    )

    responses.add(responses.GET, re.compile(r".*/shop\.json"), json={"shop": {}}, status=200)
    assert _shopify_get("/shop.json", {}) is None


@responses.activate
def test_shopify_get_invalid_url(monkeypatch):
    monkeypatch.setattr(
        "app.shopify_client._get_shopify_env",
        lambda: ("shpat_invalid", "example.myshopify.com", "safe"),
    )
    monkeypatch.setattr(
        "app.shopify_client.Settings",
        lambda: SimpleNamespace(SHOPIFY_API_VERSION="2024-10"),
    )

    responses.add(responses.GET, re.compile(r".*/invalid-shop\.json"), status=404)
    assert _shopify_get("/invalid-shop.json", {}) is None


@responses.activate
def test_shopify_get_slow_response(monkeypatch):
    monkeypatch.setattr(
        "app.shopify_client._get_shopify_env",
        lambda: ("shpat_slow", "example.myshopify.com", "safe"),
    )
    monkeypatch.setattr(
        "app.shopify_client.Settings",
        lambda: SimpleNamespace(SHOPIFY_API_VERSION="2024-10"),
    )

    responses.add(
        responses.GET,
        re.compile(r".*/shop\.json"),
        json={"shop": {"iana_timezone": "UTC"}},
        status=200,
        match_querystring=False,
        adding_headers={"X-Response-Time": "2000ms"},
    )
    assert _shopify_get("/shop.json", {})["shop"]["iana_timezone"] == "UTC"


@responses.activate
def test_shopify_get_large_response(monkeypatch):
    monkeypatch.setattr(
        "app.shopify_client._get_shopify_env",
        lambda: ("shpat_large", "example.myshopify.com", "safe"),
    )
    monkeypatch.setattr(
        "app.shopify_client.Settings",
        lambda: SimpleNamespace(SHOPIFY_API_VERSION="2024-10"),
    )

    large_data = {
        "shop": {"iana_timezone": "UTC"},
        "products": [{"id": str(i), "title": f"Product {i}"} for i in range(1000)],
    }
    responses.add(responses.GET, re.compile(r".*/shop\.json"), json=large_data, status=200)
    result = _shopify_get("/shop.json", {})
    assert result is not None and result.get("shop", {}).get("iana_timezone") == "UTC"
