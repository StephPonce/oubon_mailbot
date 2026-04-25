"""
Tests for Shopify Billing API integration.

Covers:
  - ``ospra_os.payments.shopify_billing`` — pure GraphQL helpers
    (``create_app_subscription``, ``get_app_subscription``, ``cancel_app_subscription``)
  - ``ospra_os.api.subscription_routes`` — the two HTTP endpoints
    (``POST /api/subscription/shopify/create-charge``,
    ``GET  /api/subscription/shopify/activate``)

Strategy:
  - Mock the GraphQL transport with ``httpx.MockTransport`` rather than
    monkeypatching the module's ``httpx.AsyncClient``. The helpers accept
    a ``client`` kwarg expressly for this purpose, so we don't have to
    reach into private state.
  - The HTTP-endpoint tests call the helpers via a monkey-patched
    coroutine (``create_app_subscription`` / ``get_app_subscription`` are
    imported at module import time in subscription_routes), so we patch
    those names where they're *used* — see ``ospra_os.api.subscription_routes``.
"""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from ospra_os.database.store_models import Store
from ospra_os.payments import shopify_billing
from ospra_os.payments.shopify_billing import (
    BILLING_PLANS,
    CreatedSubscription,
    ShopifyBillingError,
    SubscriptionStatus,
    create_app_subscription,
    get_app_subscription,
    cancel_app_subscription,
)


# ============================================================================
# Helpers
# ============================================================================

def _mock_client(handler) -> httpx.AsyncClient:
    """Wrap a request handler in an httpx.AsyncClient with MockTransport."""
    transport = httpx.MockTransport(handler)
    return httpx.AsyncClient(transport=transport)


def _ok(json_payload: dict) -> httpx.Response:
    return httpx.Response(200, json=json_payload)


# ============================================================================
# create_app_subscription
# ============================================================================

@pytest.mark.asyncio
async def test_create_app_subscription_returns_confirmation_url():
    """Happy path: Shopify returns id + confirmationUrl, we wrap them."""
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content.decode("utf-8"))
        return _ok({
            "data": {
                "appSubscriptionCreate": {
                    "appSubscription": {
                        "id": "gid://shopify/AppSubscription/777",
                        "name": "Ospra Soar",
                        "status": "PENDING",
                    },
                    "confirmationUrl": "https://mystore.myshopify.com/admin/charges/777/confirm",
                    "userErrors": [],
                }
            }
        })

    async with _mock_client(handler) as client:
        result = await create_app_subscription(
            shop_domain="mystore.myshopify.com",
            access_token="t0k3n",
            tier="soar",
            billing_cycle="monthly",
            return_url="https://app.ospra.os/api/subscription/shopify/activate",
            test=True,
            client=client,
        )

    assert isinstance(result, CreatedSubscription)
    assert result.charge_id == "gid://shopify/AppSubscription/777"
    assert result.confirmation_url.endswith("/confirm")
    assert result.status == "PENDING"

    # Confirm we hit the right endpoint and supplied the right plan.
    assert "/admin/api/2024-10/graphql.json" in captured["url"]
    body = captured["body"]
    assert body["variables"]["name"] == BILLING_PLANS["soar"]["name"]
    assert body["variables"]["test"] is True
    line = body["variables"]["lineItems"][0]
    pricing = line["plan"]["appRecurringPricingDetails"]
    assert pricing["price"]["amount"] == BILLING_PLANS["soar"]["price_monthly"]
    assert pricing["interval"] == "EVERY_30_DAYS"


@pytest.mark.asyncio
async def test_create_app_subscription_yearly_uses_annual_interval():
    """Yearly cycle maps to ANNUAL + price_yearly."""
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content.decode("utf-8"))
        return _ok({
            "data": {
                "appSubscriptionCreate": {
                    "appSubscription": {"id": "gid://shopify/AppSubscription/1", "name": "x", "status": "PENDING"},
                    "confirmationUrl": "https://x/confirm",
                    "userErrors": [],
                }
            }
        })

    async with _mock_client(handler) as client:
        await create_app_subscription(
            shop_domain="mystore.myshopify.com",
            access_token="t",
            tier="flight",
            billing_cycle="yearly",
            return_url="https://app.ospra.os/x",
            client=client,
        )

    pricing = captured["body"]["variables"]["lineItems"][0]["plan"]["appRecurringPricingDetails"]
    assert pricing["interval"] == "ANNUAL"
    assert pricing["price"]["amount"] == BILLING_PLANS["flight"]["price_yearly"]


@pytest.mark.asyncio
async def test_create_app_subscription_raises_on_user_errors():
    """Shopify userErrors come back as 200 OK — we still need to raise."""
    def handler(request: httpx.Request) -> httpx.Response:
        return _ok({
            "data": {
                "appSubscriptionCreate": {
                    "appSubscription": None,
                    "confirmationUrl": None,
                    "userErrors": [
                        {"field": ["trialDays"], "message": "must be 0..30"},
                    ],
                }
            }
        })

    async with _mock_client(handler) as client:
        with pytest.raises(ShopifyBillingError) as excinfo:
            await create_app_subscription(
                shop_domain="mystore.myshopify.com",
                access_token="t",
                tier="soar",
                billing_cycle="monthly",
                return_url="https://app.ospra.os/x",
                client=client,
            )
    assert "trialDays" in str(excinfo.value)


@pytest.mark.asyncio
async def test_create_app_subscription_raises_on_http_error():
    """HTTP 401 from Shopify (bad token) becomes ShopifyBillingError."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="Unauthorized")

    async with _mock_client(handler) as client:
        with pytest.raises(ShopifyBillingError) as excinfo:
            await create_app_subscription(
                shop_domain="mystore.myshopify.com",
                access_token="bad",
                tier="flight",
                billing_cycle="monthly",
                return_url="https://app.ospra.os/x",
                client=client,
            )
    assert "401" in str(excinfo.value)


@pytest.mark.asyncio
async def test_create_app_subscription_rejects_unknown_tier():
    """Unknown tier short-circuits before any HTTP call is made."""
    with pytest.raises(ValueError):
        await create_app_subscription(
            shop_domain="x",
            access_token="t",
            tier="not-a-real-tier",
            billing_cycle="monthly",
            return_url="https://app.ospra.os/x",
        )


# ============================================================================
# get_app_subscription
# ============================================================================

@pytest.mark.asyncio
async def test_get_app_subscription_returns_status():
    def handler(request: httpx.Request) -> httpx.Response:
        return _ok({
            "data": {
                "node": {
                    "id": "gid://shopify/AppSubscription/777",
                    "name": "Ospra Soar",
                    "status": "ACTIVE",
                    "currentPeriodEnd": "2026-05-24T00:00:00Z",
                }
            }
        })

    async with _mock_client(handler) as client:
        sub = await get_app_subscription(
            shop_domain="mystore.myshopify.com",
            access_token="t",
            charge_id="gid://shopify/AppSubscription/777",
            client=client,
        )
    assert isinstance(sub, SubscriptionStatus)
    assert sub.status == "ACTIVE"
    assert sub.current_period_end == "2026-05-24T00:00:00Z"


@pytest.mark.asyncio
async def test_get_app_subscription_returns_none_for_missing_node():
    def handler(request: httpx.Request) -> httpx.Response:
        return _ok({"data": {"node": None}})

    async with _mock_client(handler) as client:
        sub = await get_app_subscription(
            shop_domain="mystore.myshopify.com",
            access_token="t",
            charge_id="gid://shopify/AppSubscription/missing",
            client=client,
        )
    assert sub is None


# ============================================================================
# cancel_app_subscription
# ============================================================================

@pytest.mark.asyncio
async def test_cancel_app_subscription_success():
    def handler(request: httpx.Request) -> httpx.Response:
        return _ok({
            "data": {
                "appSubscriptionCancel": {
                    "appSubscription": {"id": "gid://shopify/AppSubscription/777", "status": "CANCELLED"},
                    "userErrors": [],
                }
            }
        })

    async with _mock_client(handler) as client:
        ok = await cancel_app_subscription(
            shop_domain="mystore.myshopify.com",
            access_token="t",
            charge_id="gid://shopify/AppSubscription/777",
            client=client,
        )
    assert ok is True


@pytest.mark.asyncio
async def test_cancel_app_subscription_propagates_user_errors():
    def handler(request: httpx.Request) -> httpx.Response:
        return _ok({
            "data": {
                "appSubscriptionCancel": {
                    "appSubscription": None,
                    "userErrors": [{"field": ["id"], "message": "not found"}],
                }
            }
        })

    async with _mock_client(handler) as client:
        with pytest.raises(ShopifyBillingError):
            await cancel_app_subscription(
                shop_domain="mystore.myshopify.com",
                access_token="t",
                charge_id="gid://shopify/AppSubscription/zzz",
                client=client,
            )


# ============================================================================
# /shopify/create-charge endpoint
# ============================================================================

@pytest.fixture
def shopify_billing_env(monkeypatch):
    """
    Configure the env vars the create-charge endpoint requires.

    Sets a public app URL and enables the test-mode flag so test=True is
    honored (would otherwise be silently downgraded to False).
    """
    monkeypatch.setenv("OSPRA_APP_PUBLIC_URL", "https://app.ospra.os")
    monkeypatch.setenv("OSPRA_SHOPIFY_BILLING_TEST", "1")


def test_create_charge_returns_confirmation_url(
    auth_client, db_session, test_user, shopify_billing_env, monkeypatch
):
    """Happy path: store exists, GraphQL mock returns success, we get back a confirmation URL."""
    # Seed a Shopify store owned by test_user
    store = Store(
        user_id=test_user.id,
        store_name="My Store",
        platform="shopify",
        store_url="mystore.myshopify.com",
        credentials={"shop_url": "mystore.myshopify.com", "access_token": "t0k3n"},
        is_active=True,
    )
    db_session.add(store)
    db_session.commit()
    db_session.refresh(store)

    # Patch where it's imported (the routes module)
    from ospra_os.api import subscription_routes

    async def fake_create(**kwargs):
        # Light shape check — the endpoint should pass tier/billing_cycle
        assert kwargs["tier"] == "soar"
        assert kwargs["billing_cycle"] == "monthly"
        assert kwargs["return_url"].startswith("https://app.ospra.os")
        return CreatedSubscription(
            charge_id="gid://shopify/AppSubscription/abc",
            confirmation_url="https://mystore.myshopify.com/admin/charges/abc/confirm",
            status="PENDING",
        )

    monkeypatch.setattr(subscription_routes, "create_app_subscription", fake_create)

    response = auth_client.post(
        "/api/subscription/shopify/create-charge",
        json={"tier": "soar", "billing_cycle": "monthly", "test": True},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True
    assert body["charge_id"] == "gid://shopify/AppSubscription/abc"
    assert body["confirmation_url"].endswith("/confirm")

    # Pending charge id should now be persisted on the store. The endpoint
    # writes via ``store.set_credentials`` which encrypts, so we must read
    # back through ``get_credentials`` rather than the raw column.
    db_session.refresh(store)
    creds = store.get_credentials()
    assert creds.get("pending_app_subscription_id") == "gid://shopify/AppSubscription/abc"
    assert creds.get("pending_app_subscription_tier") == "soar"


def _detail_message(response) -> str:
    """
    Pull the user-facing error message out of an Ospra error response.

    The custom exception handler in ``ospra_os.observability`` wraps
    HTTPException as ``{"error": {"code": "HTTP_400", "message": "..."}}``
    rather than FastAPI's default ``{"detail": "..."}``.
    """
    body = response.json()
    if isinstance(body, dict):
        if "error" in body and isinstance(body["error"], dict):
            return body["error"].get("message", "") or ""
        if "detail" in body:
            d = body["detail"]
            return d if isinstance(d, str) else str(d)
    return ""


def test_create_charge_rejects_when_no_shopify_store(
    auth_client, db_session, test_user, shopify_billing_env
):
    """User with no Shopify store gets a clear 400, not an opaque 500."""
    response = auth_client.post(
        "/api/subscription/shopify/create-charge",
        json={"tier": "soar", "billing_cycle": "monthly"},
    )
    assert response.status_code == 400
    assert "shopify" in _detail_message(response).lower()


def test_create_charge_rejects_unknown_tier(
    auth_client, db_session, test_user, shopify_billing_env
):
    """Tier validation runs BEFORE we look up the store."""
    response = auth_client.post(
        "/api/subscription/shopify/create-charge",
        json={"tier": "nest", "billing_cycle": "monthly"},
    )
    assert response.status_code == 400
    assert "paid plan" in _detail_message(response).lower()


def test_create_charge_requires_https_app_url(
    auth_client, db_session, test_user, monkeypatch
):
    """Missing OSPRA_APP_PUBLIC_URL → 503 with a config-fix hint."""
    monkeypatch.delenv("OSPRA_APP_PUBLIC_URL", raising=False)
    # Seed store so we get past tier/store gates
    db_session.add(
        Store(
            user_id=test_user.id,
            store_name="My Store",
            platform="shopify",
            store_url="mystore.myshopify.com",
            credentials={"shop_url": "mystore.myshopify.com", "access_token": "t"},
            is_active=True,
        )
    )
    db_session.commit()

    response = auth_client.post(
        "/api/subscription/shopify/create-charge",
        json={"tier": "flight", "billing_cycle": "monthly"},
    )
    assert response.status_code == 503
    assert "OSPRA_APP_PUBLIC_URL" in _detail_message(response)


# ============================================================================
# /shopify/activate endpoint
# ============================================================================

def test_activate_flips_user_tier_when_charge_active(
    client, db_session, test_user, monkeypatch, shopify_billing_env
):
    """End-to-end activate: pending id matches, Shopify says ACTIVE → user upgraded."""
    store = Store(
        user_id=test_user.id,
        store_name="My Store",
        platform="shopify",
        store_url="mystore.myshopify.com",
        credentials={
            "shop_url": "mystore.myshopify.com",
            "access_token": "t0k3n",
            "pending_app_subscription_id": "gid://shopify/AppSubscription/abc",
            "pending_app_subscription_tier": "soar",
            "pending_app_subscription_cycle": "monthly",
        },
        is_active=True,
    )
    db_session.add(store)
    db_session.commit()
    db_session.refresh(store)

    from ospra_os.api import subscription_routes

    async def fake_get(**kwargs):
        assert kwargs["charge_id"] == "gid://shopify/AppSubscription/abc"
        return SubscriptionStatus(
            charge_id=kwargs["charge_id"],
            name="Ospra Soar",
            status="ACTIVE",
            current_period_end=None,
        )

    monkeypatch.setattr(subscription_routes, "get_app_subscription", fake_get)

    response = client.get(
        "/api/subscription/shopify/activate",
        params={
            "charge_id": "gid://shopify/AppSubscription/abc",
            "store_id": store.id,
            "return_path": "/settings",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["location"] == "/settings"

    # User tier flipped + pending fields cleared, active ones written.
    # Re-read both rows through expire_all so we observe the writes the
    # endpoint made via its own DB session.
    db_session.expire_all()
    user = db_session.query(type(test_user)).filter_by(id=test_user.id).first()
    assert getattr(user.subscription_tier, "value", str(user.subscription_tier)).lower() == "soar"
    fresh_store = db_session.query(Store).filter_by(id=store.id).first()
    creds = fresh_store.get_credentials()
    assert creds.get("app_subscription_id") == "gid://shopify/AppSubscription/abc"
    assert "pending_app_subscription_id" not in creds


def test_activate_rejects_mismatched_charge_id(
    client, db_session, test_user, monkeypatch, shopify_billing_env
):
    """If charge_id doesn't match the stored pending id, refuse."""
    store = Store(
        user_id=test_user.id,
        store_name="My Store",
        platform="shopify",
        store_url="mystore.myshopify.com",
        credentials={
            "shop_url": "mystore.myshopify.com",
            "access_token": "t",
            "pending_app_subscription_id": "gid://shopify/AppSubscription/abc",
            "pending_app_subscription_tier": "soar",
            "pending_app_subscription_cycle": "monthly",
        },
        is_active=True,
    )
    db_session.add(store)
    db_session.commit()
    db_session.refresh(store)

    response = client.get(
        "/api/subscription/shopify/activate",
        params={
            "charge_id": "gid://shopify/AppSubscription/SOMEONE_ELSE",
            "store_id": store.id,
        },
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert "does not match" in _detail_message(response).lower()


def test_activate_clears_pending_when_charge_declined(
    client, db_session, test_user, monkeypatch, shopify_billing_env
):
    """If Shopify reports the charge as DECLINED, we clear pending state and 400."""
    store = Store(
        user_id=test_user.id,
        store_name="My Store",
        platform="shopify",
        store_url="mystore.myshopify.com",
        credentials={
            "shop_url": "mystore.myshopify.com",
            "access_token": "t",
            "pending_app_subscription_id": "gid://shopify/AppSubscription/abc",
            "pending_app_subscription_tier": "soar",
            "pending_app_subscription_cycle": "monthly",
        },
        is_active=True,
    )
    db_session.add(store)
    db_session.commit()
    db_session.refresh(store)

    from ospra_os.api import subscription_routes

    async def fake_get(**kwargs):
        return SubscriptionStatus(
            charge_id=kwargs["charge_id"],
            name="Ospra Soar",
            status="DECLINED",
            current_period_end=None,
        )

    monkeypatch.setattr(subscription_routes, "get_app_subscription", fake_get)

    response = client.get(
        "/api/subscription/shopify/activate",
        params={
            "charge_id": "gid://shopify/AppSubscription/abc",
            "store_id": store.id,
        },
        follow_redirects=False,
    )
    assert response.status_code == 400
    db_session.expire_all()
    fresh = db_session.query(Store).filter_by(id=store.id).first()
    creds = fresh.get_credentials()
    assert "pending_app_subscription_id" not in creds
