import re
import pytest

import responses

from types import SimpleNamespace

from app.shopify_client import _get_shopify_env, _shopify_get


@responses.activate
def test_shopify_get():
    responses.add(
        responses.GET,
        re.compile(r".*/shop\.json"),
        json={"shop": {"iana_timezone": "UTC"}},
        status=200,
    )
    assert _shopify_get("/shop.json", {})["shop"]["iana_timezone"] == "UTC"

    responses.add(responses.GET, re.compile(r".*/shop\.json"), status=404)
    assert _shopify_get("/shop.json", {}) is None


def test_shopify_env_type_error(mocker):
    mocker.patch(
        "app.shopify_client.Settings",
        return_value=SimpleNamespace(
            SHOPIFY_API_TOKEN=123,
            SHOPIFY_STORE="oubonshop.myshopify.com",
            SHOPIFY_MODE="safe",
            SHOPIFY_API_VERSION="2025-10",
        ),
    )
    with pytest.raises(ValueError):
        _get_shopify_env()
