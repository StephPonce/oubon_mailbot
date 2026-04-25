"""
Shopify native Billing API integration.

Required for Shopify Partner App approval — paid plans installed through the
Shopify App Store **must** charge the merchant via Shopify's own Billing API
(``RecurringApplicationCharge`` in REST, ``appSubscriptionCreate`` in
GraphQL). External processors like LemonSqueezy are still allowed for
direct-web signups, but a merchant who installs Ospra from the App Store
needs a Shopify-native upgrade path.

This module is the *thin* GraphQL Admin-API wrapper. It owns three
operations:

1. ``create_app_subscription`` — start a new recurring charge. Returns the
   ``confirmationUrl`` Shopify generates; the merchant must visit that URL
   and click **Approve charge** in their admin. Until they do, the charge
   is in ``PENDING`` state and we MUST NOT mark the user as upgraded.
2. ``get_app_subscription`` — read a charge's current ``status``. Used by
   the activate-callback to flip the user's tier once Shopify reports
   ``ACTIVE``, and by ad-hoc reconciliation jobs.
3. ``cancel_app_subscription`` — explicit cancellation. Shopify also
   auto-cancels charges when the merchant uninstalls the app, so the
   ``app/uninstalled`` webhook handler is a separate enforcement path —
   this function is for in-app downgrades.

Design notes
------------
- API version is pinned to ``2024-10`` to match the rest of the codebase
  (see ``services/shopify/client.py``, ``api/shopify_oauth_routes.py``).
- Functions take ``shop_domain`` + ``access_token`` directly rather than a
  ``Store`` ORM row, so unit tests can mock the HTTP layer without spinning
  up the full DB stack and the same helpers can be reused by the
  ``app/uninstalled`` webhook (which queries the Store row separately).
- All paths raise ``ShopifyBillingError`` for any non-200 / GraphQL-level
  failure. The caller is responsible for logging + UX. We deliberately do
  not swallow errors here because billing failures need to be visible.
- Test mode (``test=True``) is exposed and used in tests; production
  callers should leave it off.

Pass 4d-followup: Shopify Partner App approval blocker
"Shopify Billing API not integrated" (see
``docs/guides/SHOPIFY_PARTNER_APP_APPROVAL_READINESS.md`` §4).
"""

from __future__ import annotations

import logging
from typing import Optional

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)


SHOPIFY_API_VERSION = "2024-10"


# ---------------------------------------------------------------------------
# Plan catalogue
# ---------------------------------------------------------------------------
#
# Single source of truth for tier → Shopify-charge mapping. The values mirror
# the public price points listed in ``api/subscription_routes.py``'s
# ``TIER_PLANS`` so the two never drift. ``trial_days`` defaults to 7 per the
# Partner App readiness doc — short enough to be a real trial, long enough
# for reviewers to validate the upgrade path without a real card.
#
BILLING_PLANS: dict[str, dict] = {
    "flight": {
        "name": "Ospra Flight",
        "price_monthly": 29.0,
        "price_yearly": 290.0,
        "trial_days": 7,
    },
    "soar": {
        "name": "Ospra Soar",
        "price_monthly": 79.0,
        "price_yearly": 790.0,
        "trial_days": 7,
    },
    "stratosphere": {
        "name": "Ospra Stratosphere",
        "price_monthly": 199.0,
        "price_yearly": 1990.0,
        "trial_days": 7,
    },
}


class ShopifyBillingError(RuntimeError):
    """Raised for any GraphQL-level or HTTP-level billing failure."""


class CreatedSubscription(BaseModel):
    """Result of a successful ``create_app_subscription`` call."""

    charge_id: str  # GraphQL gid, e.g. ``gid://shopify/AppSubscription/12345``
    confirmation_url: str  # Where to redirect the merchant
    status: str  # Always ``PENDING`` immediately after creation


class SubscriptionStatus(BaseModel):
    """Result of a successful ``get_app_subscription`` call."""

    charge_id: str
    name: str
    status: str  # PENDING | ACCEPTED | ACTIVE | DECLINED | EXPIRED | CANCELLED | FROZEN
    current_period_end: Optional[str] = None  # ISO timestamp or None for trials


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _normalize_shop_domain(shop_domain: str) -> str:
    """
    Strip protocol and ensure the domain ends in ``.myshopify.com``.

    The wider codebase stores credentials in two formats — sometimes the
    ``shop_url`` includes ``https://``, sometimes it's bare. Normalizing
    here keeps callers (and tests) free of that quirk.
    """
    bare = shop_domain.replace("https://", "").replace("http://", "").rstrip("/")
    if "." not in bare:
        bare = f"{bare}.myshopify.com"
    return bare.lower()


def _graphql_url(shop_domain: str) -> str:
    return f"https://{_normalize_shop_domain(shop_domain)}/admin/api/{SHOPIFY_API_VERSION}/graphql.json"


def _headers(access_token: str) -> dict[str, str]:
    return {
        "X-Shopify-Access-Token": access_token,
        "Content-Type": "application/json",
    }


def _check_user_errors(payload: dict, op: str) -> None:
    """
    Raise ``ShopifyBillingError`` if Shopify reports user-facing errors.

    Shopify GraphQL returns 200 OK even for validation failures and stuffs
    them into ``data.<mutation>.userErrors``. We treat any populated
    ``userErrors`` array as a hard failure — they're typically things like
    "trialDays must be 0..30" that the caller has no way to recover from
    silently.
    """
    data = payload.get("data") or {}
    block = data.get(op) or {}
    user_errors = block.get("userErrors") or []
    if user_errors:
        joined = "; ".join(
            f"{e.get('field') or '?'}: {e.get('message') or 'unknown'}"
            for e in user_errors
        )
        raise ShopifyBillingError(f"Shopify rejected {op}: {joined}")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def create_app_subscription(
    *,
    shop_domain: str,
    access_token: str,
    tier: str,
    billing_cycle: str = "monthly",
    return_url: str,
    test: bool = False,
    api_version: str = SHOPIFY_API_VERSION,
    client: Optional[httpx.AsyncClient] = None,
) -> CreatedSubscription:
    """
    Open a Shopify recurring app charge for the merchant.

    Args:
        shop_domain: ``mystore.myshopify.com`` (with or without protocol).
        access_token: OAuth offline token for the shop.
        tier: One of ``flight``, ``soar``, ``stratosphere``.
        billing_cycle: ``monthly`` (default) or ``yearly``. Yearly creates
            an ``ANNUAL`` interval; monthly creates ``EVERY_30_DAYS``.
        return_url: HTTPS URL the merchant lands on AFTER approving the
            charge. Shopify appends ``?charge_id=...`` to it. Should point
            at our ``/api/subscription/shopify/activate`` endpoint.
        test: If True, Shopify creates a non-billing test charge — used by
            the test suite and during development against a partner store.

    Returns:
        ``CreatedSubscription`` with ``confirmation_url`` to redirect the
        merchant to, and ``charge_id`` to persist for the activate callback.

    Raises:
        ShopifyBillingError: GraphQL ``userErrors`` or HTTP failure.
        ValueError: Unknown tier or billing cycle.
    """
    plan = BILLING_PLANS.get(tier.lower())
    if not plan:
        raise ValueError(f"Unknown billing tier: {tier!r}")

    cycle = (billing_cycle or "monthly").lower()
    if cycle not in {"monthly", "yearly"}:
        raise ValueError(f"Unknown billing cycle: {billing_cycle!r}")

    price_amount = plan["price_yearly"] if cycle == "yearly" else plan["price_monthly"]
    interval = "ANNUAL" if cycle == "yearly" else "EVERY_30_DAYS"

    mutation = """
    mutation appSubscriptionCreate(
      $name: String!,
      $returnUrl: URL!,
      $trialDays: Int,
      $test: Boolean,
      $lineItems: [AppSubscriptionLineItemInput!]!
    ) {
      appSubscriptionCreate(
        name: $name,
        returnUrl: $returnUrl,
        trialDays: $trialDays,
        test: $test,
        lineItems: $lineItems
      ) {
        appSubscription { id name status }
        confirmationUrl
        userErrors { field message }
      }
    }
    """

    variables = {
        "name": plan["name"],
        "returnUrl": return_url,
        "trialDays": int(plan.get("trial_days", 0)),
        "test": bool(test),
        "lineItems": [
            {
                "plan": {
                    "appRecurringPricingDetails": {
                        "price": {"amount": price_amount, "currencyCode": "USD"},
                        "interval": interval,
                    }
                }
            }
        ],
    }

    payload = await _graphql(
        shop_domain=shop_domain,
        access_token=access_token,
        query=mutation,
        variables=variables,
        api_version=api_version,
        client=client,
    )
    _check_user_errors(payload, "appSubscriptionCreate")

    block = (payload.get("data") or {}).get("appSubscriptionCreate") or {}
    sub = block.get("appSubscription") or {}
    confirmation_url = block.get("confirmationUrl")
    if not (sub.get("id") and confirmation_url):
        raise ShopifyBillingError(
            "appSubscriptionCreate succeeded but response was missing id or "
            "confirmationUrl — refusing to proceed."
        )

    return CreatedSubscription(
        charge_id=sub["id"],
        confirmation_url=confirmation_url,
        status=sub.get("status") or "PENDING",
    )


async def get_app_subscription(
    *,
    shop_domain: str,
    access_token: str,
    charge_id: str,
    api_version: str = SHOPIFY_API_VERSION,
    client: Optional[httpx.AsyncClient] = None,
) -> Optional[SubscriptionStatus]:
    """
    Look up the current state of a charge by its GraphQL gid.

    Returns ``None`` if Shopify reports no such node — that can happen if
    the merchant uninstalled the app between create and activate, since
    Shopify nukes pending subscriptions on uninstall.
    """
    query = """
    query appSubscription($id: ID!) {
      node(id: $id) {
        ... on AppSubscription {
          id
          name
          status
          currentPeriodEnd
        }
      }
    }
    """
    payload = await _graphql(
        shop_domain=shop_domain,
        access_token=access_token,
        query=query,
        variables={"id": charge_id},
        api_version=api_version,
        client=client,
    )
    node = ((payload.get("data") or {}).get("node")) or None
    if not node:
        return None
    return SubscriptionStatus(
        charge_id=node["id"],
        name=node.get("name") or "",
        status=node.get("status") or "UNKNOWN",
        current_period_end=node.get("currentPeriodEnd"),
    )


async def cancel_app_subscription(
    *,
    shop_domain: str,
    access_token: str,
    charge_id: str,
    api_version: str = SHOPIFY_API_VERSION,
    client: Optional[httpx.AsyncClient] = None,
) -> bool:
    """
    Cancel an active app subscription.

    Returns True on success. Raises ``ShopifyBillingError`` on failure so
    the caller can decide whether to roll back the user's tier change.
    """
    mutation = """
    mutation appSubscriptionCancel($id: ID!) {
      appSubscriptionCancel(id: $id) {
        appSubscription { id status }
        userErrors { field message }
      }
    }
    """
    payload = await _graphql(
        shop_domain=shop_domain,
        access_token=access_token,
        query=mutation,
        variables={"id": charge_id},
        api_version=api_version,
        client=client,
    )
    _check_user_errors(payload, "appSubscriptionCancel")
    return True


# ---------------------------------------------------------------------------
# Transport
# ---------------------------------------------------------------------------

async def _graphql(
    *,
    shop_domain: str,
    access_token: str,
    query: str,
    variables: dict,
    api_version: str,
    client: Optional[httpx.AsyncClient],
) -> dict:
    """
    Execute one GraphQL operation. Splits HTTP and JSON failures.

    The optional ``client`` parameter lets tests inject a pre-configured
    ``httpx.AsyncClient`` (e.g. one with a ``MockTransport``); production
    callers leave it None and we open a short-lived client here.
    """
    url = (
        f"https://{_normalize_shop_domain(shop_domain)}"
        f"/admin/api/{api_version}/graphql.json"
    )
    body = {"query": query, "variables": variables}

    async def _do(c: httpx.AsyncClient) -> httpx.Response:
        return await c.post(url, json=body, headers=_headers(access_token), timeout=30.0)

    if client is not None:
        response = await _do(client)
    else:
        async with httpx.AsyncClient() as c:
            response = await _do(c)

    if response.status_code >= 400:
        raise ShopifyBillingError(
            f"Shopify Billing API HTTP {response.status_code}: {response.text[:300]}"
        )

    try:
        payload = response.json()
    except Exception as exc:  # pragma: no cover — only fires on truly malformed responses
        raise ShopifyBillingError(f"Shopify Billing API returned non-JSON: {exc}") from exc

    if "errors" in payload and payload["errors"]:
        # Top-level GraphQL errors (auth, schema mismatch, etc.) are different
        # from per-mutation ``userErrors``. Surface both with a clear marker.
        joined = "; ".join(e.get("message", "?") for e in payload["errors"])
        raise ShopifyBillingError(f"Shopify GraphQL errors: {joined}")

    return payload
