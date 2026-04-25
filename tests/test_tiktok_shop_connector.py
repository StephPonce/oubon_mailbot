"""
Unit tests for `ospra_os.product_research.connectors.tiktok_shop`.

These tests cover the pure-Python pieces of the connector (signing, canonical
string assembly, payload parsing, velocity normalization) plus a mocked HTTP
round-trip so we can verify request assembly end-to-end without hitting the
real TikTok Shop API. No network I/O.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any, Dict
from unittest.mock import AsyncMock

import httpx
import pytest

from ospra_os.product_research.connectors.base import ProductCandidate
from ospra_os.product_research.connectors.tiktok_shop import (
    API_VERSION,
    TikTokShopConnector,
)


# ---------------------------------------------------------------------- fixtures
@pytest.fixture
def configured_connector(monkeypatch) -> TikTokShopConnector:
    """A connector with all four credentials set to stable test values."""
    # Clear env so explicit kwargs win deterministically.
    for k in (
        "TIKTOK_SHOP_APP_KEY",
        "TIKTOK_SHOP_APP_SECRET",
        "TIKTOK_SHOP_ACCESS_TOKEN",
        "TIKTOK_SHOP_CIPHER",
    ):
        monkeypatch.delenv(k, raising=False)
    return TikTokShopConnector(
        app_key="test-app-key",
        app_secret="test-app-secret",
        access_token="test-access-token",
        shop_cipher="test-shop-cipher",
        region="US",
        api_host="https://example.tiktok-shop.test",
    )


@pytest.fixture
def unconfigured_connector(monkeypatch) -> TikTokShopConnector:
    """No credentials → is_available() must be False and calls return []."""
    for k in (
        "TIKTOK_SHOP_APP_KEY",
        "TIKTOK_SHOP_APP_SECRET",
        "TIKTOK_SHOP_ACCESS_TOKEN",
        "TIKTOK_SHOP_CIPHER",
    ):
        monkeypatch.delenv(k, raising=False)
    return TikTokShopConnector()


# ---------------------------------------------------------------------- identity
def test_identity_constants(configured_connector: TikTokShopConnector) -> None:
    assert configured_connector.name == "TikTok Shop"
    assert configured_connector.source_id == "tiktok_shop"


def test_is_available_requires_all_four_creds(
    unconfigured_connector: TikTokShopConnector,
    configured_connector: TikTokShopConnector,
) -> None:
    assert unconfigured_connector.is_available() is False
    assert configured_connector.is_available() is True


def test_is_available_false_when_missing_cipher(monkeypatch) -> None:
    for k in (
        "TIKTOK_SHOP_APP_KEY",
        "TIKTOK_SHOP_APP_SECRET",
        "TIKTOK_SHOP_ACCESS_TOKEN",
        "TIKTOK_SHOP_CIPHER",
    ):
        monkeypatch.delenv(k, raising=False)
    conn = TikTokShopConnector(
        app_key="k",
        app_secret="s",
        access_token="t",
        shop_cipher=None,
    )
    assert conn.is_available() is False


# ------------------------------------------------------------------- signing
def test_canonicalize_excludes_sign_and_access_token() -> None:
    path = "/product/202309/products/search"
    params = {
        "app_key": "k",
        "timestamp": "1700000000",
        "sign": "should-be-stripped",
        "access_token": "should-be-stripped",
        "shop_cipher": "c",
        "version": API_VERSION,
    }
    body = '{"keyword":"q"}'
    canonical = TikTokShopConnector._canonicalize(path, params, body)
    assert "sign" not in canonical
    assert "should-be-stripped" not in canonical
    # Ensure params are sorted alphabetically (app_key before shop_cipher).
    assert canonical.startswith(path + "app_key")
    assert canonical.endswith(body)


def test_canonicalize_sorts_params_alphabetically() -> None:
    """Params must be sorted by key before concatenation."""
    canonical = TikTokShopConnector._canonicalize(
        path="/p",
        params={"zeta": "1", "alpha": "2", "mu": "3"},
        body=None,
    )
    # Expected: /p + alpha2 + mu3 + zeta1
    assert canonical == "/palpha2mu3zeta1"


def test_sign_matches_hmac_sha256_recipe(
    configured_connector: TikTokShopConnector,
) -> None:
    """Signature must be HMAC-SHA256(secret+canonical+secret, key=secret)."""
    path = "/p"
    params = {"alpha": "1"}
    body = None

    sig = configured_connector._sign(path, params, body)

    # Reproduce the recipe manually.
    canonical = TikTokShopConnector._canonicalize(path, params, body)
    wrapped = (
        f"{configured_connector.app_secret}{canonical}{configured_connector.app_secret}"
    )
    expected = hmac.new(
        configured_connector.app_secret.encode(),
        wrapped.encode(),
        hashlib.sha256,
    ).hexdigest()
    assert sig == expected
    assert sig.islower()  # hex digest must be lowercase


def test_sign_raises_without_secret() -> None:
    conn = TikTokShopConnector(
        app_key="k",
        app_secret=None,
        access_token="t",
        shop_cipher="c",
    )
    with pytest.raises(RuntimeError, match="app_secret"):
        conn._sign("/p", {}, None)


# ----------------------------------------------------------- request assembly
def test_build_request_injects_required_params(
    configured_connector: TikTokShopConnector,
) -> None:
    url, headers, body_str = configured_connector._build_request(
        path="/product/202309/products/search",
        params={"page_size": "20"},
        body={"keyword": "q"},
    )
    assert url.startswith(
        "https://example.tiktok-shop.test/product/202309/products/search?"
    )
    # All four Partner API params must appear in the query string.
    for required in ("app_key=", "shop_cipher=", "sign=", "access_token=", "timestamp="):
        assert required in url, f"missing {required} in url"
    assert headers["Content-Type"] == "application/json"
    # Body should be the sorted, compact JSON we signed over.
    assert body_str == '{"keyword":"q"}'


def test_build_request_body_is_canonical_json(
    configured_connector: TikTokShopConnector,
) -> None:
    """Body JSON is sorted + separatorless so signature reproduction works."""
    _, _, body_str = configured_connector._build_request(
        path="/p",
        params={},
        body={"b": 2, "a": 1},
    )
    assert body_str == '{"a":1,"b":2}'  # keys sorted, no spaces


# ------------------------------------------------------------- velocity math
@pytest.mark.parametrize(
    "units_7d, views_7d, expected_floor, expected_ceil",
    [
        (0, 0, 0.0, 0.0),
        (1000, 500_000, 99.0, 100.0),  # max → saturates near 100
        (50, 10_000, 20.0, 70.0),  # typical mid-range (0.7*0.57 + 0.3*0.70 ≈ 0.61)
        (-5, -10, 0.0, 0.0),  # negatives clamp to 0
    ],
)
def test_normalize_velocity_bounds(
    units_7d: int, views_7d: int, expected_floor: float, expected_ceil: float
) -> None:
    score = TikTokShopConnector._normalize_velocity(units_7d, views_7d)
    assert 0.0 <= score <= 100.0
    assert expected_floor <= score <= expected_ceil


def test_normalize_velocity_weights_units_over_views() -> None:
    """Units-sold should dominate — same score only if ratios balance per spec."""
    # 100 units, 0 views vs 0 units, 500k views: units_norm should win.
    units_heavy = TikTokShopConnector._normalize_velocity(100, 0)
    views_heavy = TikTokShopConnector._normalize_velocity(0, 500_000)
    # With weights 0.7 / 0.3, 500k views caps the view axis at 1.0 * 0.3 = 30,
    # while 100 units → log1p(100)/log1p(1000) ≈ 0.667 * 0.7 ≈ 46.7. Units win.
    assert units_heavy > views_heavy


# ------------------------------------------------------------ payload parsing
def test_to_candidate_happy_path(configured_connector: TikTokShopConnector) -> None:
    raw = {
        "product_id": "SKU-123",
        "title": "Smart WiFi Plug",
        "price": {"original_price": "19.99", "currency": "USD"},
        "main_images": [{"url": "https://cdn.tiktok/img.jpg"}],
        "sale_count_7d": 250,
        "view_count_7d": 120_000,
        "avg_rating": 4.6,
        "product_url": "https://shop.tiktok.com/view/product/SKU-123",
    }
    cand = configured_connector._to_candidate(raw, "smart home")
    assert isinstance(cand, ProductCandidate)
    assert cand.name == "Smart WiFi Plug"
    assert cand.source == "tiktok_shop"
    assert cand.price == pytest.approx(19.99)
    assert cand.currency == "USD"
    assert cand.image_url == "https://cdn.tiktok/img.jpg"
    assert cand.url == "https://shop.tiktok.com/view/product/SKU-123"
    assert cand.supplier_rating == pytest.approx(4.6)
    # Velocity tags must be preserved so the opportunity scorer can read them.
    assert "units_sold_7d:250" in cand.tags
    assert "views_7d:120000" in cand.tags
    assert cand.search_volume == 120_000
    assert cand.social_engagement == 250
    assert 0.0 < cand.trend_score <= 100.0


def test_to_candidate_returns_none_without_name(
    configured_connector: TikTokShopConnector,
) -> None:
    assert configured_connector._to_candidate({"product_id": "x"}, None) is None


def test_to_candidate_handles_missing_price(
    configured_connector: TikTokShopConnector,
) -> None:
    raw = {
        "title": "No Price Widget",
        "product_id": "p1",
        "sale_count_7d": 10,
    }
    cand = configured_connector._to_candidate(raw, None)
    assert cand is not None
    assert cand.price is None
    # Fallback URL is constructed from product_id when permalink is absent.
    assert cand.url == "https://shop.tiktok.com/view/product/p1"


def test_to_candidate_handles_string_price(
    configured_connector: TikTokShopConnector,
) -> None:
    """Some shop regions return a flat string price instead of a price dict."""
    raw = {"title": "X", "product_id": "p", "price": "12.50"}
    cand = configured_connector._to_candidate(raw, None)
    assert cand is not None
    assert cand.price == pytest.approx(12.50)


def test_to_candidate_handles_garbage_price(
    configured_connector: TikTokShopConnector,
) -> None:
    """Non-numeric price strings should not crash — price just becomes None."""
    raw = {"title": "X", "product_id": "p", "price": {"original_price": "not-a-number"}}
    cand = configured_connector._to_candidate(raw, None)
    assert cand is not None
    assert cand.price is None


# --------------------------------------------------------------- integration
@pytest.mark.asyncio
async def test_search_returns_empty_when_unconfigured(
    unconfigured_connector: TikTokShopConnector,
) -> None:
    result = await unconfigured_connector.search("anything")
    assert result == []


@pytest.mark.asyncio
async def test_get_trending_returns_empty_when_unconfigured(
    unconfigured_connector: TikTokShopConnector,
) -> None:
    result = await unconfigured_connector.get_trending()
    assert result == []


@pytest.mark.asyncio
async def test_search_parses_mocked_response(
    configured_connector: TikTokShopConnector,
) -> None:
    """End-to-end: mocked httpx client returns a fixture payload; parser builds candidates."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)

    def _make_response(payload: Dict[str, Any]) -> httpx.Response:
        request = httpx.Request("POST", "https://example/x")
        return httpx.Response(
            status_code=200,
            content=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            request=request,
        )

    mock_client.request = AsyncMock(
        return_value=_make_response(
            {
                "code": 0,
                "message": "ok",
                "data": {
                    "products": [
                        {
                            "product_id": "A",
                            "title": "Alpha",
                            "price": {"original_price": "5.00", "currency": "USD"},
                            "sale_count_7d": 10,
                            "view_count_7d": 1_000,
                        },
                        {
                            "product_id": "B",
                            "title": "Bravo",
                            "price": {"original_price": "8.00", "currency": "USD"},
                            "sale_count_7d": 100,
                            "view_count_7d": 25_000,
                        },
                    ]
                },
            }
        )
    )
    configured_connector._http_client = mock_client

    results = await configured_connector.search("widget", limit=5)
    assert len(results) == 2
    assert {c.name for c in results} == {"Alpha", "Bravo"}
    # Verify the outgoing request was POST to the search endpoint.
    mock_client.request.assert_awaited_once()
    call_kwargs = mock_client.request.await_args.kwargs
    assert call_kwargs["method"] == "POST"
    assert "/product/202309/products/search" in call_kwargs["url"]


@pytest.mark.asyncio
async def test_get_trending_parses_items_key(
    configured_connector: TikTokShopConnector,
) -> None:
    """Trend feed returns `data.items` (different from search's `data.products`)."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)

    def _response(payload: Dict[str, Any]) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            content=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            request=httpx.Request("GET", "https://example/x"),
        )

    mock_client.request = AsyncMock(
        return_value=_response(
            {
                "code": 0,
                "data": {
                    "items": [
                        {
                            "product_id": "T1",
                            "title": "Trending 1",
                            "sale_count_7d": 500,
                            "view_count_7d": 80_000,
                        },
                    ]
                },
            }
        )
    )
    configured_connector._http_client = mock_client

    results = await configured_connector.get_trending(category="123", limit=10)
    assert len(results) == 1
    assert results[0].name == "Trending 1"
    call_kwargs = mock_client.request.await_args.kwargs
    assert call_kwargs["method"] == "GET"
    assert "/product/202309/trend/feed" in call_kwargs["url"]
    assert "category_id=123" in call_kwargs["url"]


@pytest.mark.asyncio
async def test_request_returns_empty_payload_on_missing_credentials(
    unconfigured_connector: TikTokShopConnector,
) -> None:
    payload = await unconfigured_connector._request("GET", "/p")
    assert payload == {"code": 0, "data": {}, "message": "credentials missing"}


@pytest.mark.asyncio
async def test_api_error_code_logged_but_not_raised(
    configured_connector: TikTokShopConnector, caplog
) -> None:
    """TikTok wraps errors as {code != 0}. We log and return the payload."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.request = AsyncMock(
        return_value=httpx.Response(
            status_code=200,
            content=json.dumps(
                {"code": 105001, "message": "Invalid shop cipher", "data": {}}
            ).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            request=httpx.Request("GET", "https://example/x"),
        )
    )
    configured_connector._http_client = mock_client

    with caplog.at_level("WARNING"):
        results = await configured_connector.get_trending()

    assert results == []
    assert any("API error" in rec.message for rec in caplog.records)
