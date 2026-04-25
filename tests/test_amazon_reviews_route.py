"""
Tests for POST /api/oi/amazon-reviews — the on-demand fetch route.

The route delegates to ``ProductDiscoveryEngine.fetch_amazon_review_text``
which is already covered in ``test_on_demand_amazon_review_text.py``.
These tests verify the HTTP contract: status codes, response shape,
auth requirement, and how the route handles the various "no data"
states cleanly.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


def _product_with_asin(asin="B0XYZ56789"):
    return {
        "title": "Smart Plug",
        "amazon_evidence": {
            "found_matches": True,
            "top_matches": [
                {
                    "asin": asin,
                    "url": f"https://www.amazon.com/dp/{asin}",
                    "title": "Smart Plug",
                }
            ],
        },
    }


# ---------------------------------------------------------------------------
# Auth gate
# ---------------------------------------------------------------------------

def test_requires_auth(client):
    """Unauthenticated requests get rejected."""
    response = client.post(
        "/api/oi/amazon-reviews",
        json={"product_data": _product_with_asin()},
    )
    assert response.status_code in (401, 403)


# ---------------------------------------------------------------------------
# "No data" responses are 200 with structured reason — frontend renders
# a clean "no Amazon reviews available" state, not an error toast.
# ---------------------------------------------------------------------------

def test_returns_unavailable_when_no_amazon_match(auth_client):
    response = auth_client.post(
        "/api/oi/amazon-reviews",
        json={"product_data": {"title": "Smart Plug"}},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["available"] is False
    assert body["reason"] == "no_amazon_match"
    assert body["title"] == "Smart Plug"


def test_returns_unavailable_when_connector_unavailable(auth_client):
    """If the engine has no Apify connector, the route returns a clean
    'connector_unavailable' state instead of erroring."""
    from ospra_os.api.product_analysis_routes import _get_engine
    from ospra_os.intelligence.product_discovery import ProductDiscoveryEngine

    # Build a stub engine and inject it as the singleton — this
    # bypasses real connector init.
    stub = ProductDiscoveryEngine.__new__(ProductDiscoveryEngine)
    stub.amazon_reviews_text_available = False
    stub.amazon_reviews_text = None

    import ospra_os.api.product_analysis_routes as mod
    mod._engine_singleton = stub

    try:
        response = auth_client.post(
            "/api/oi/amazon-reviews",
            json={"product_data": _product_with_asin()},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["available"] is False
        assert body["reason"] == "amazon_review_text_connector_unavailable"
    finally:
        mod._engine_singleton = None


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

def test_happy_path_returns_review_payload(auth_client):
    from ospra_os.intelligence.product_discovery import ProductDiscoveryEngine
    import ospra_os.api.product_analysis_routes as mod

    stub_engine = ProductDiscoveryEngine.__new__(ProductDiscoveryEngine)
    stub_engine.amazon_reviews_text_available = True
    stub_engine.amazon_reviews_text = type("Stub", (), {})()

    fake_payload = {
        "available": True,
        "asin": "B0XYZ56789",
        "review_count_returned": 2,
        "average_rating": 4.5,
        "verified_share": 1.0,
        "reviews": [
            {"text": "Great.", "rating": 5, "verified": True},
            {"text": "Mostly fine.", "rating": 4, "verified": True},
        ],
        "cached": False,
    }

    async def fake_fetch(product, max_reviews=15):
        product["amazon_review_text"] = fake_payload
        return fake_payload

    stub_engine.fetch_amazon_review_text = fake_fetch
    mod._engine_singleton = stub_engine

    try:
        response = auth_client.post(
            "/api/oi/amazon-reviews",
            json={"product_data": _product_with_asin(), "max_reviews": 5},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["available"] is True
        assert body["asin"] == "B0XYZ56789"
        assert body["review_count_returned"] == 2
        assert body["average_rating"] == 4.5
        assert len(body["reviews"]) == 2
        assert body["cached"] is False
    finally:
        mod._engine_singleton = None


def test_engine_returns_none_route_returns_unavailable(auth_client):
    from ospra_os.intelligence.product_discovery import ProductDiscoveryEngine
    import ospra_os.api.product_analysis_routes as mod

    stub_engine = ProductDiscoveryEngine.__new__(ProductDiscoveryEngine)
    stub_engine.amazon_reviews_text_available = True
    stub_engine.amazon_reviews_text = type("Stub", (), {})()
    stub_engine.fetch_amazon_review_text = AsyncMock(return_value=None)

    mod._engine_singleton = stub_engine

    try:
        response = auth_client.post(
            "/api/oi/amazon-reviews",
            json={"product_data": _product_with_asin()},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["available"] is False
        assert body["reason"] == "actor_returned_no_data"
    finally:
        mod._engine_singleton = None


def test_engine_exception_returns_502(auth_client):
    from ospra_os.intelligence.product_discovery import ProductDiscoveryEngine
    import ospra_os.api.product_analysis_routes as mod

    stub_engine = ProductDiscoveryEngine.__new__(ProductDiscoveryEngine)
    stub_engine.amazon_reviews_text_available = True
    stub_engine.amazon_reviews_text = type("Stub", (), {})()
    stub_engine.fetch_amazon_review_text = AsyncMock(
        side_effect=RuntimeError("Apify outage")
    )

    mod._engine_singleton = stub_engine

    try:
        response = auth_client.post(
            "/api/oi/amazon-reviews",
            json={"product_data": _product_with_asin()},
        )
        assert response.status_code == 502
        body = response.json()
        # The framework wraps HTTPExceptions as ``{"error": {"code": ..., "message": ...}}``
        # in some configs and as ``{"detail": ...}`` in others. Accept either.
        msg = (
            body.get("detail")
            or body.get("error", {}).get("message", "")
        )
        assert "Apify" in msg or "failed" in msg
    finally:
        mod._engine_singleton = None


def test_max_reviews_clamped_to_safe_range(auth_client):
    """Frontend can't burn $$ by asking for 1000 reviews. Cap is 25."""
    from ospra_os.intelligence.product_discovery import ProductDiscoveryEngine
    import ospra_os.api.product_analysis_routes as mod

    stub_engine = ProductDiscoveryEngine.__new__(ProductDiscoveryEngine)
    stub_engine.amazon_reviews_text_available = True
    stub_engine.amazon_reviews_text = type("Stub", (), {})()

    captured = {}

    async def fake_fetch(product, max_reviews=15):
        captured["max_reviews"] = max_reviews
        return {
            "available": True, "asin": "B0XYZ56789",
            "review_count_returned": 0, "average_rating": None,
            "verified_share": 0.0, "reviews": [], "cached": False,
        }

    stub_engine.fetch_amazon_review_text = fake_fetch
    mod._engine_singleton = stub_engine

    try:
        # Way too many — should be clamped to 25
        auth_client.post(
            "/api/oi/amazon-reviews",
            json={"product_data": _product_with_asin(), "max_reviews": 1000},
        )
        assert captured["max_reviews"] == 25

        # Way too few — should be clamped up to 1
        auth_client.post(
            "/api/oi/amazon-reviews",
            json={"product_data": _product_with_asin(), "max_reviews": 0},
        )
        assert captured["max_reviews"] == 1
    finally:
        mod._engine_singleton = None
