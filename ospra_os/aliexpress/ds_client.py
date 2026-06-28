"""
AliExpress Dropshipping Solution (DS) API client.

================================================================================
WHY THIS EXISTS (Task #24)
================================================================================
The discovery engine has been pricing products off the AE *Affiliate* API
(`aliexpress.affiliate.product.query`). That endpoint returns marketing fields
(`target_sale_price`, `target_original_price`) which do not match the
real merchant cost — `target_sale_price` is the affiliate-promoted price
(~35-45% off AE retail) and `target_original_price` is an inflated MSRP.
Neither field is what the dropshipper actually pays AE when fulfilling.

The AE *Dropshipping Solution* API (`aliexpress.ds.*`) DOES expose explicit
merchant pricing via the SKU-level `sku_price` field on
`aliexpress.ds.product.get`. This client wraps the DS endpoints we need to:

  1. Replace the heuristic `affiliate_price × 1.65` cost estimate with the
     real merchant price the dropshipper would pay AE for that SKU.
  2. Pull DS top-sellers / bestseller feeds as an additional discovery
     source independent of the affiliate-promoted catalog.
  3. Get per-product variable commission rates (the affiliate API hands us
     a single uniform percentage that's actually a promo-bucket default).

================================================================================
SCOPE
================================================================================
This client is intentionally narrow:

  - get_hot_products(feed_name, ...) → DS feed (recommend.feed.get)
  - get_product_details(product_id) → DS per-product detail (product.get)
  - enrich_pricing(products) → batch-enrich a list of products with real
    merchant prices from the DS API

It is NOT a general-purpose DS API wrapper. We add methods here as the
discovery engine needs them.

================================================================================
AUTHENTICATION
================================================================================
DS API requires a separate OAuth credential from the affiliate API. The
dropship token is stored in `aliexpress_tokens` with `api_type="dropship"`
and obtained via `ospra_os/aliexpress/routes.py` OAuth callback. If no
dropship token is configured, `is_available()` returns False and every
public method short-circuits to a no-op result — callers should fall
back to the affiliate-API heuristic.

================================================================================
RATE LIMITING
================================================================================
AE caps DS API calls at ~5 req/sec per app key. We serialize concurrent
calls behind a single asyncio.Lock and pace them at `_min_interval`
seconds. This is conservative; if we hit 429s in practice the lock here
is the place to add exponential backoff (mirror the CJ client pattern).
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import aiohttp

logger = logging.getLogger(__name__)

AE_API_BASE = "https://api-sg.aliexpress.com/sync"


class AliExpressDSClient:
    """Async client for the AliExpress Dropshipping Solution API.

    Lazily loads the dropship OAuth token on first use; treats the absence
    of a token as "DS unavailable" rather than fatal, so the discovery
    engine can fall back to its existing affiliate-API path.
    """

    def __init__(self) -> None:
        # Credentials — DS API uses a different app key than affiliate.
        # Empty string when not configured (env var unset).
        self._app_key = (
            os.getenv("ALIEXPRESS_APP_KEY")
            or os.getenv("OUBONSHOP_ALIEXPRESS_API_KEY", "")
        )
        self._app_secret = (
            os.getenv("ALIEXPRESS_APP_SECRET")
            or os.getenv("OUBONSHOP_ALIEXPRESS_APP_SECRET", "")
        )
        # Lazy-loaded access token from the database (api_type="dropship")
        self._access_token: Optional[str] = None
        self._token_loaded = False

        # Rate limiter — AE allows ~5 req/sec per app key on DS endpoints.
        # We pace at 5 req/sec (0.2s min interval) and serialize concurrent
        # callers behind one lock so we don't race past it. Lazy lock so
        # __init__ works outside an event loop.
        self._min_interval = float(os.getenv("AE_DS_MIN_INTERVAL", "0.25"))
        self._last_request_at = 0.0
        self._lock: Optional[asyncio.Lock] = None

        # Per-process detail cache so enriching a product the user has
        # already looked at this session doesn't re-hit AE. Maps
        # product_id → (timestamp, detail_dict). 6-hour TTL.
        self._detail_cache: Dict[str, tuple[float, Dict[str, Any]]] = {}
        self._detail_cache_ttl = int(os.getenv("AE_DS_DETAIL_TTL_SECONDS", str(6 * 3600)))

    # ------------------------------------------------------------------
    # Availability / token plumbing
    # ------------------------------------------------------------------
    def _load_token(self) -> Optional[str]:
        """Load the stored dropship access token. Returns None if there's
        no token or the database isn't reachable."""
        if self._token_loaded:
            return self._access_token
        self._token_loaded = True

        try:
            from ospra_os.database.aliexpress_tokens import load_token
            payload = load_token("dropship")
        except Exception as exc:
            logger.warning(f"[AE-DS] Could not load dropship token: {exc}")
            return None

        if not payload or not payload.get("access_token"):
            # Fallback: a manually-set ALIEXPRESS_ACCESS_TOKEN env (no DB/OAuth).
            # NOTE: env tokens carry no refresh_token, so they can't self-heal —
            # OAuth (/api/aliexpress/auth/start) is the durable path.
            env_tok = os.getenv("ALIEXPRESS_ACCESS_TOKEN", "").strip()
            if env_tok:
                logger.info("[AE-DS] using ALIEXPRESS_ACCESS_TOKEN env (no DB token)")
                self._access_token = env_tok
                return self._access_token
            logger.info("[AE-DS] No dropship token configured")
            return None

        # Return the token even if the DB says it's expired — let the API be the
        # source of truth. _request() self-heals on IllegalAccessToken via the
        # stored refresh_token, so a stale DB flag shouldn't block the call.
        if payload.get("is_expired"):
            logger.info("[AE-DS] Dropship token marked expired — will refresh on demand")
        self._access_token = payload["access_token"]
        return self._access_token

    async def _refresh_token(self) -> bool:
        """Self-heal an expired DS access token via the stored refresh_token (#AE).

        Mirrors the CJ auto-refresh: read refresh_token from the aliexpress_tokens
        DB, POST grant_type=refresh_token, persist the new token, update memory.
        Returns False (and logs that re-auth is needed) when no refresh_token is
        stored — env-only tokens can't self-heal; OAuth is required to seed one.
        """
        if not (self._app_key and self._app_secret):
            return False
        try:
            from ospra_os.database.aliexpress_tokens import load_token, save_token
            payload = load_token("dropship")
        except Exception:
            payload = None
        refresh_token = (payload or {}).get("refresh_token")
        if not refresh_token:
            logger.warning(
                "[AE-DS] no refresh_token stored — re-authorize at "
                "/api/aliexpress/auth/start to seed one"
            )
            return False
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    AE_API_BASE,
                    data={
                        "client_id": self._app_key,
                        "client_secret": self._app_secret,
                        "grant_type": "refresh_token",
                        "refresh_token": refresh_token,
                    },
                    timeout=15,
                ) as resp:
                    body = await resp.json(content_type=None)
        except Exception as e:
            logger.warning(f"[AE-DS] token refresh transport error: {e}")
            return False
        new_access = body.get("access_token") if isinstance(body, dict) else None
        if not new_access:
            logger.warning(
                f"[AE-DS] token refresh failed: "
                f"{(body or {}).get('error') if isinstance(body, dict) else body}"
            )
            return False
        new_refresh = body.get("refresh_token", refresh_token)
        expires_in = int(body.get("expires_in", 86400))
        try:
            save_token("dropship", new_access, new_refresh, expires_in)
        except Exception as e:
            logger.warning(f"[AE-DS] could not persist refreshed token: {e}")
        self._access_token = new_access
        self._token_loaded = True
        logger.info("[AE-DS] access token refreshed (self-healed)")
        return True

    def is_available(self) -> bool:
        """Cheap check the caller can use to decide whether to invoke DS
        endpoints at all. True iff app key+secret AND a non-expired
        dropship token are present."""
        if not self._app_key or not self._app_secret:
            return False
        return self._load_token() is not None

    def _get_lock(self) -> asyncio.Lock:
        """Lazily create the request-serialization lock on first use."""
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    # ------------------------------------------------------------------
    # Signing + HTTP
    # ------------------------------------------------------------------
    def _sign(self, params: Dict[str, str]) -> str:
        """HMAC-SHA256 signature over sorted (key, value) concatenation.

        AE's spec: concatenate the sorted key+value pairs as a single
        string, HMAC-SHA256 it with the app secret, hex-uppercase. The
        `sign` param itself is excluded from the input.
        """
        sorted_items = sorted((k, v) for k, v in params.items() if k != "sign")
        payload = "".join(f"{k}{v}" for k, v in sorted_items)
        digest = hmac.new(
            self._app_secret.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return digest.upper()

    async def _pace(self) -> None:
        """Sleep just long enough to honour `_min_interval`. Must be
        called while holding `_lock` so concurrent callers queue."""
        now = time.time()
        elapsed = now - self._last_request_at
        if elapsed < self._min_interval:
            await asyncio.sleep(self._min_interval - elapsed)
        self._last_request_at = time.time()

    async def _request(
        self,
        method: str,
        extra_params: Dict[str, str],
        timeout: int = 15,
        _auth_retried: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """Make a signed DS API GET. Returns the raw parsed JSON response
        or None on transport/auth failure. Callers are responsible for
        navigating the response wrapper (each DS method has its own
        `aliexpress_ds_*_response.result` envelope)."""
        token = self._load_token()
        if not token:
            return None

        timestamp = str(int(time.time() * 1000))
        params = {
            "app_key": self._app_key,
            "method": method,
            "timestamp": timestamp,
            "format": "json",
            "v": "2.0",
            "sign_method": "sha256",
            "session": token,
            **{k: str(v) for k, v in extra_params.items() if v is not None},
        }
        params["sign"] = self._sign(params)

        async with self._get_lock():
            await self._pace()
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        AE_API_BASE, params=params, timeout=timeout
                    ) as response:
                        body = await response.json(content_type=None)
            except asyncio.TimeoutError:
                logger.warning(f"[AE-DS] {method} timed out after {timeout}s")
                return None
            except aiohttp.ClientError as exc:
                logger.warning(f"[AE-DS] {method} transport error: {exc}")
                return None
            except Exception as exc:
                logger.error(f"[AE-DS] {method} unexpected error: {exc}")
                return None

        if isinstance(body, dict) and "error_response" in body:
            err = body["error_response"]
            code = str(err.get("code", ""))
            msg = str(err.get("msg", ""))
            # Self-heal an expired/invalid token: refresh once and retry.
            token_dead = (
                "IllegalAccessToken" in code
                or ("token" in msg.lower() and ("expire" in msg.lower() or "invalid" in msg.lower()))
            )
            if token_dead and not _auth_retried:
                logger.warning(f"[AE-DS] {method} token invalid/expired — refreshing + retrying")
                if await self._refresh_token():
                    return await self._request(method, extra_params, timeout=timeout, _auth_retried=True)
            logger.warning(f"[AE-DS] {method} API error code={code} msg={msg!r}")
            return None

        return body

    # ------------------------------------------------------------------
    # DS endpoints
    # ------------------------------------------------------------------
    async def get_hot_products(
        self,
        feed_name: str = "DS_Global_topsellers",
        page_size: int = 20,
        page_no: int = 1,
        country: str = "US",
        currency: str = "USD",
        language: str = "EN",
        category_ids: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Pull a DS recommend feed (top-sellers / bestseller / etc.).

        Normalises every row to the same shape the discovery engine
        already consumes for affiliate products — so callers can swap
        sources without rewriting downstream readers."""
        if not self.is_available():
            return []

        body = await self._request(
            "aliexpress.ds.recommend.feed.get",
            {
                "feed_name": feed_name,
                "country": country,
                "target_currency": currency,
                "target_language": language,
                "page_size": min(int(page_size), 50),
                "page_no": int(page_no),
                **({"category_ids": category_ids} if category_ids else {}),
            },
        )
        if not body:
            return []

        # AE's response wrapper has changed shape twice. Try both.
        resp = body.get("aliexpress_ds_recommend_feed_get_response", {})
        result = resp.get("result") or resp.get("resp_result") or {}
        raw_products = result.get("products")
        if isinstance(raw_products, dict):
            raw_products = raw_products.get("product", [])
        if not isinstance(raw_products, list):
            return []

        out: List[Dict[str, Any]] = []
        for item in raw_products:
            if not isinstance(item, dict):
                continue
            normalised = self._normalise_feed_item(item, feed_name)
            if normalised:
                out.append(normalised)
        return out

    async def get_product_details(
        self,
        product_id: str,
        country: str = "US",
        currency: str = "USD",
        language: str = "EN",
    ) -> Optional[Dict[str, Any]]:
        """Pull `aliexpress.ds.product.get` for a single product. Returns
        a flat dict with the merchant price + commission fields the
        discovery engine cares about, or None on miss. Cached per
        product_id for `_detail_cache_ttl` seconds."""
        if not product_id or not self.is_available():
            return None

        cached = self._detail_cache.get(str(product_id))
        if cached and (time.time() - cached[0]) < self._detail_cache_ttl:
            return cached[1]

        body = await self._request(
            "aliexpress.ds.product.get",
            {
                "product_id": str(product_id),
                "ship_to_country": country,
                "target_currency": currency,
                "target_language": language,
            },
        )
        if not body:
            return None

        resp = body.get("aliexpress_ds_product_get_response", {})
        result = resp.get("result") or resp.get("resp_result") or {}
        if not isinstance(result, dict) or not result:
            return None

        detail = self._normalise_product_detail(result)
        if detail:
            self._detail_cache[str(product_id)] = (time.time(), detail)
        return detail

    # ------------------------------------------------------------------
    # Bulk enrichment
    # ------------------------------------------------------------------
    async def enrich_pricing(
        self,
        products: List[Dict[str, Any]],
        limit: int = 20,
    ) -> int:
        """Mutate `products` in-place, replacing the affiliate-derived
        cost estimate with the real DS merchant price when available.

        Only the first `limit` products are enriched, because the DS
        detail API is one HTTP call per product (~250ms each at our
        rate limit). The discovery engine sorts by OI score before
        calling us, so the top-K hit the API and the rest keep their
        heuristic estimate. Returns the number of products that were
        successfully enriched.
        """
        if not self.is_available():
            return 0

        enriched = 0
        for idx, product in enumerate(products[: max(0, int(limit))]):
            product_id = product.get("product_id")
            if not product_id:
                continue
            # Strip any "ae_" / "cj_" prefix some callers add
            raw_id = str(product_id).split("_")[-1] if "_" in str(product_id) else str(product_id)

            detail = await self.get_product_details(raw_id)
            if not detail:
                continue

            merchant_cost = detail.get("merchant_cost")
            if merchant_cost is None or merchant_cost <= 0:
                continue

            commission_pct = detail.get("commission_pct")

            # Overwrite the cost basis. The heuristic was too generous
            # (affiliate_price × 1.65); the DS merchant price is the
            # real number the dropshipper would pay AE.
            product["cost_price"] = round(float(merchant_cost), 2)
            product["supplier_cost"] = product["cost_price"]
            product["cost_basis"] = "ae_ds_merchant_price"
            product["price_source"] = "aliexpress_ds_api"
            product["price_fetched_at"] = datetime.now(timezone.utc).isoformat()

            # Commission: keep affiliate value as fallback, but prefer
            # the DS-derived per-product rate when AE returned one.
            if commission_pct is not None and commission_pct > 0:
                product["commission_rate"] = float(commission_pct)

            # Surface DS-specific fields the existing UI doesn't read yet
            # but downstream consumers will.
            product["ds_ship_from_country"] = detail.get("ship_from_country")
            product["ds_package_weight"] = detail.get("package_weight")
            product["ds_delivery_time_days"] = detail.get("delivery_time_days")
            product["ds_min_sku_price"] = detail.get("min_sku_price")
            product["ds_max_sku_price"] = detail.get("max_sku_price")

            # Cite the DS source in data_sources so the evidence panel
            # can show "merchant price from AE DS API" instead of "heuristic".
            data_sources = product.setdefault("data_sources", {})
            data_sources["aliexpress_ds"] = {
                "available": True,
                "merchant_cost": product["cost_price"],
                "commission_pct": product.get("commission_rate"),
                "ship_from": detail.get("ship_from_country"),
                "delivery_time_days": detail.get("delivery_time_days"),
                "package_weight": detail.get("package_weight"),
                "fetched_at": product["price_fetched_at"],
            }
            # Also overwrite the aliexpress.cost field so the existing UI
            # picks up the corrected number without code changes.
            ae_block = data_sources.setdefault("aliexpress", {})
            ae_block["cost"] = product["cost_price"]
            ae_block["cost_basis"] = "ae_ds_merchant_price"

            enriched += 1

        if enriched:
            logger.info(
                f"[AE-DS] Enriched {enriched}/{min(limit, len(products))} "
                f"products with real merchant prices"
            )
        return enriched

    # ------------------------------------------------------------------
    # Normalisation helpers
    # ------------------------------------------------------------------
    def _normalise_feed_item(
        self,
        item: Dict[str, Any],
        feed_name: str,
    ) -> Optional[Dict[str, Any]]:
        """DS feed responses use the same field names as the affiliate API
        for prices (target_sale_price etc.) but they're the merchant-side
        view. We reuse the affiliate shape so the discovery engine can
        merge DS feed products with affiliate products without a special
        case."""
        try:
            product_id = str(item.get("product_id") or "").strip()
            if not product_id:
                return None
            sale = self._parse_float(item.get("target_sale_price"))
            if sale <= 0:
                return None
            original = self._parse_float(item.get("target_original_price"))
            return {
                "product_id": product_id,
                "title": item.get("product_title", ""),
                "target_sale_price": sale,
                "target_original_price": original or sale,
                "image_url": item.get("product_main_image_url"),
                "promotion_link": item.get("promotion_link")
                    or item.get("product_detail_url"),
                "volume": self._parse_int(item.get("volume", 0)),
                "evaluate_rate": item.get("evaluate_rate"),
                "ship_from_country": item.get("ship_from_country"),
                "shipping_cost": item.get("shipping_cost"),
                "category_id": item.get("first_level_category_id"),
                "category_name": item.get("second_level_category_name")
                    or item.get("first_level_category_name"),
                # Provenance — tells the discovery engine this product
                # came from the DS API, not the affiliate API.
                "source_api": "aliexpress_ds",
                "ds_feed_name": feed_name,
            }
        except Exception as exc:
            logger.debug(f"[AE-DS] Failed to normalise feed item: {exc}")
            return None

    def _normalise_product_detail(
        self,
        result: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """`aliexpress.ds.product.get` returns a nested DTO graph. Flatten
        it into the handful of fields enrichment cares about: the
        merchant price (min sku_price), commission rate, package weight,
        delivery time, ship-from country.

        AE's response shapes vary, so we try several known paths."""
        try:
            base = result.get("ae_item_base_info_dto") or {}
            sku_root = (
                result.get("ae_item_sku_info_dtos")
                or result.get("ae_item_sku_info_d_t_o_s")
                or {}
            )
            skus = (
                sku_root.get("ae_item_sku_info_d_t_o")
                or sku_root.get("ae_item_sku_info_dto")
                or sku_root.get("ae_item_sku_info_dtos")
                or []
            )
            if isinstance(skus, dict):
                skus = [skus]
            if not isinstance(skus, list):
                skus = []

            # Collect all non-zero SKU prices. AE confusingly uses several
            # field names: sku_price is the merchant cost (what we pay);
            # offer_sale_price is the consumer-facing sale price.
            sku_prices: List[float] = []
            offer_prices: List[float] = []
            for sku in skus:
                if not isinstance(sku, dict):
                    continue
                p = self._parse_float(sku.get("sku_price"))
                if p > 0:
                    sku_prices.append(p)
                op = self._parse_float(sku.get("offer_sale_price"))
                if op > 0:
                    offer_prices.append(op)

            # If no SKU array, fall back to the base-info price fields
            if not sku_prices:
                p = self._parse_float(base.get("sale_price") or base.get("product_sale_price"))
                if p > 0:
                    sku_prices.append(p)
            if not sku_prices:
                return None

            merchant_cost = min(sku_prices)
            min_sku = min(sku_prices)
            max_sku = max(sku_prices)

            # Commission — AE sometimes returns it at the top of the
            # result, sometimes nested inside the base info.
            commission_raw = (
                result.get("commission_rate")
                or base.get("commission_rate")
                or result.get("commission")
            )
            commission_pct = None
            if commission_raw is not None:
                commission_pct = self._parse_float(str(commission_raw).replace("%", ""))

            # Logistics — used for shipping cost / delivery estimates
            logistics = (
                result.get("logistics_info_dto")
                or result.get("ae_item_logistics_info_dto")
                or {}
            )
            package = result.get("package_info_dto") or {}

            return {
                "product_id": str(base.get("product_id") or ""),
                "title": base.get("subject") or base.get("title"),
                "merchant_cost": merchant_cost,
                "min_sku_price": min_sku,
                "max_sku_price": max_sku,
                "consumer_offer_price": min(offer_prices) if offer_prices else None,
                "commission_pct": commission_pct,
                "ship_from_country": logistics.get("ship_from_country") or logistics.get("country"),
                "delivery_time_days": self._parse_int(
                    logistics.get("delivery_time") or logistics.get("estimated_delivery_time")
                ),
                "package_weight": self._parse_float(package.get("gross_weight")),
                "currency": base.get("currency_code") or "USD",
            }
        except Exception as exc:
            logger.debug(f"[AE-DS] Failed to normalise product detail: {exc}")
            return None

    # ------------------------------------------------------------------
    # Small parsing helpers — AE returns numbers as strings, sometimes
    # with currency symbols, sometimes empty. Be defensive.
    # ------------------------------------------------------------------
    @staticmethod
    def _parse_float(value: Any) -> float:
        if value is None:
            return 0.0
        if isinstance(value, (int, float)):
            return float(value)
        try:
            cleaned = str(value).strip().replace("$", "").replace(",", "")
            return float(cleaned) if cleaned else 0.0
        except (ValueError, TypeError):
            return 0.0

    @staticmethod
    def _parse_int(value: Any) -> int:
        if value is None:
            return 0
        if isinstance(value, int):
            return value
        try:
            return int(float(str(value).strip()))
        except (ValueError, TypeError):
            return 0


# ----------------------------------------------------------------------
# Singleton — one client per process. AE's auth token is global to the
# platform, so there's no per-tenant variance to model.
# ----------------------------------------------------------------------
_ds_client: Optional[AliExpressDSClient] = None


def get_ds_client() -> AliExpressDSClient:
    """Return the process-wide AE DS client, creating it on first use."""
    global _ds_client
    if _ds_client is None:
        _ds_client = AliExpressDSClient()
    return _ds_client
