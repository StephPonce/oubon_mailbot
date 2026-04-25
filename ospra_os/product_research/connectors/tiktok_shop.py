"""
TikTok Shop Partner API connector (first-party, official API).

Different from the Apify-based scraper at
`ospra_os.product_research.connectors.apify.tiktok_shop` (which uses third-party
actors to scrape public TikTok content) and from the content-side
`ospra_os.integrations.tiktok_client.TikTokClient` (which uses the TikTok Open
Platform for user videos). This connector calls the TikTok Shop Open Platform
at `open-api.tiktokglobalshop.com` and returns real `units_sold_7d` + view
velocity for ranked product candidates.

Auth model
----------
The TikTok Shop Partner API uses a 4-credential model:

  TIKTOK_SHOP_APP_KEY       — stable, identifies the partner app.
  TIKTOK_SHOP_APP_SECRET    — stable, used to HMAC-SHA256 sign each request.
  TIKTOK_SHOP_ACCESS_TOKEN  — per-seller, rotates via OAuth refresh (lifespan
                              typically 24h).
  TIKTOK_SHOP_CIPHER        — per-shop identifier returned by the OAuth
                              callback; required for every product/order call.

Signing recipe (per TikTok Shop API docs, v2023-09 signing spec):
  1. Extract all query-string params except `sign` and `access_token`.
  2. Sort the remaining params alphabetically by key.
  3. Concatenate into "{k1}{v1}{k2}{v2}..." — no separators.
  4. Prepend the request path (with leading slash).
  5. For POST/PUT, append the raw JSON body.
  6. Wrap the string with the app_secret on both sides: secret + str + secret.
  7. HMAC-SHA256 with the app_secret as the key; lowercase hex digest → sign.

Ranking signal
--------------
The task (#36) calls out `units_sold_7d + social velocity`. The seller-side
product list exposes `sale_count_7d` and `view_count_7d`; we normalize both
into `trend_score` (0–100) and surface the raw values in the ProductCandidate's
tags for downstream use by `opportunity_scorer`.

Graceful degradation
--------------------
Every request path short-circuits when credentials are missing: `is_available()`
returns False and `search()`/`get_trending()` return []. The multi-source
discovery layer already handles empty connector results without failing the
overall run, so an unconfigured TikTok Shop account is a no-op, not an error.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import httpx

from .base import BaseConnector, ProductCandidate

logger = logging.getLogger(__name__)


# TikTok Shop Partner API regions (for host selection if we ever shard)
REGION_HOSTS = {
    "US": "https://open-api.tiktokglobalshop.com",
    "UK": "https://open-api.tiktokglobalshop.com",
    # SEA regions share the same global host; region is passed as a query param
    "ID": "https://open-api.tiktokglobalshop.com",
    "MY": "https://open-api.tiktokglobalshop.com",
    "PH": "https://open-api.tiktokglobalshop.com",
    "SG": "https://open-api.tiktokglobalshop.com",
    "TH": "https://open-api.tiktokglobalshop.com",
    "VN": "https://open-api.tiktokglobalshop.com",
}

# API version segment (TikTok Shop uses date-stamped versions).
API_VERSION = "202309"

# Default HTTP timeouts — scoped so a hung TikTok side never blocks discovery.
DEFAULT_CONNECT_TIMEOUT = 5.0
DEFAULT_READ_TIMEOUT = 25.0
DEFAULT_TOTAL_TIMEOUT = 30.0


class TikTokShopConnector(BaseConnector):
    """
    First-party TikTok Shop Partner API connector.

    Usage:
        connector = TikTokShopConnector()
        if connector.is_available():
            candidates = await connector.search("smart home gadget")
            # or
            trending = await connector.get_trending(category="Beauty", limit=20)
    """

    def __init__(
        self,
        app_key: Optional[str] = None,
        app_secret: Optional[str] = None,
        access_token: Optional[str] = None,
        shop_cipher: Optional[str] = None,
        region: Optional[str] = None,
        api_host: Optional[str] = None,
        http_client: Optional[httpx.AsyncClient] = None,
    ):
        self.app_key = app_key or os.getenv("TIKTOK_SHOP_APP_KEY")
        self.app_secret = app_secret or os.getenv("TIKTOK_SHOP_APP_SECRET")
        self.access_token = access_token or os.getenv("TIKTOK_SHOP_ACCESS_TOKEN")
        self.shop_cipher = shop_cipher or os.getenv("TIKTOK_SHOP_CIPHER")
        self.region = (region or os.getenv("TIKTOK_SHOP_REGION") or "US").upper()
        self.api_host = (
            api_host
            or os.getenv("TIKTOK_SHOP_API_HOST")
            or REGION_HOSTS.get(self.region, REGION_HOSTS["US"])
        )
        # Injectable for tests; falls back to a module-scoped default at call time.
        self._http_client = http_client

        super().__init__(api_key=self.app_key)

    # ------------------------------------------------------------------ identity
    @property
    def name(self) -> str:
        return "TikTok Shop"

    @property
    def source_id(self) -> str:
        return "tiktok_shop"

    def is_available(self) -> bool:
        """Connector is usable only when all four Partner API credentials are present."""
        return bool(
            self.app_key
            and self.app_secret
            and self.access_token
            and self.shop_cipher
        )

    # --------------------------------------------------------------- signing
    @staticmethod
    def _canonicalize(path: str, params: Dict[str, Any], body: Optional[str]) -> str:
        """
        Build the canonical string-to-sign per TikTok Shop v2023-09 spec.

        Params with keys `sign` and `access_token` are excluded from the signing
        material. Body (if any) is appended verbatim after the sorted param
        concatenation.
        """
        filtered = {
            k: v for k, v in params.items() if k not in ("sign", "access_token")
        }
        sorted_items = sorted(filtered.items(), key=lambda kv: kv[0])
        concat = "".join(f"{k}{v}" for k, v in sorted_items)
        signing_str = f"{path}{concat}"
        if body:
            signing_str = f"{signing_str}{body}"
        return signing_str

    def _sign(self, path: str, params: Dict[str, Any], body: Optional[str] = None) -> str:
        """HMAC-SHA256(app_secret + canonical + app_secret, key=app_secret)."""
        if not self.app_secret:
            raise RuntimeError("TikTok Shop app_secret not configured")
        canonical = self._canonicalize(path, params, body)
        wrapped = f"{self.app_secret}{canonical}{self.app_secret}"
        digest = hmac.new(
            self.app_secret.encode("utf-8"),
            wrapped.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return digest  # lowercase hex

    def _build_request(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        body: Optional[Dict[str, Any]] = None,
    ) -> tuple[str, Dict[str, str], Optional[str]]:
        """Assemble the full URL, signed query string, and JSON body."""
        all_params: Dict[str, Any] = {
            "app_key": self.app_key,
            "timestamp": str(int(time.time())),
            "shop_cipher": self.shop_cipher,
            "version": API_VERSION,
        }
        if params:
            all_params.update({k: str(v) for k, v in params.items() if v is not None})

        body_str: Optional[str] = None
        if body is not None:
            body_str = json.dumps(body, separators=(",", ":"), sort_keys=True)

        all_params["sign"] = self._sign(path, all_params, body_str)
        all_params["access_token"] = self.access_token

        url = f"{self.api_host}{path}?{urlencode(all_params)}"
        headers = {"Content-Type": "application/json"}
        return url, headers, body_str

    # --------------------------------------------------------------- transport
    async def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        body: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if not self.is_available():
            logger.warning("[tiktok_shop] credentials missing; returning empty payload")
            return {"code": 0, "data": {}, "message": "credentials missing"}

        url, headers, body_str = self._build_request(path, params, body)
        timeout = httpx.Timeout(
            connect=DEFAULT_CONNECT_TIMEOUT,
            read=DEFAULT_READ_TIMEOUT,
            write=DEFAULT_READ_TIMEOUT,
            pool=DEFAULT_TOTAL_TIMEOUT,
        )

        async def _do(client: httpx.AsyncClient) -> Dict[str, Any]:
            response = await client.request(
                method=method,
                url=url,
                headers=headers,
                content=body_str.encode("utf-8") if body_str else None,
                timeout=timeout,
            )
            response.raise_for_status()
            payload = response.json()
            # TikTok Shop wraps every response as {code, message, data, request_id}.
            # code=0 is success; anything else is an API-level error.
            if payload.get("code", 0) != 0:
                logger.warning(
                    "[tiktok_shop] API error code=%s message=%s path=%s",
                    payload.get("code"),
                    payload.get("message"),
                    path,
                )
            return payload

        if self._http_client is not None:
            return await _do(self._http_client)

        async with httpx.AsyncClient() as client:
            return await _do(client)

    # ------------------------------------------------------------------ public
    async def search(self, query: str, **kwargs) -> List[ProductCandidate]:
        """
        Search the seller's shop catalog by keyword.

        Uses `/product/{VERSION}/products/search` with keyword filter and
        page-size capped by `limit`. Results are ranked by recent sales velocity.

        Kwargs:
            limit: max results (default 20, max 100).
            category_id: TikTok Shop category ID filter (optional).
            min_price / max_price: price filters in shop currency (optional).
        """
        limit = int(kwargs.get("limit", 20))
        limit = max(1, min(limit, 100))
        payload = {
            "status": "ACTIVATE",
            "keyword": query,
            "seller_skus": [],
            "create_time_ge": None,
            "create_time_le": None,
            "update_time_ge": None,
            "update_time_le": None,
            "category_version": "v2",
        }
        if kwargs.get("category_id"):
            payload["category_ids"] = [str(kwargs["category_id"])]
        if kwargs.get("min_price") is not None:
            payload["price_min"] = float(kwargs["min_price"])
        if kwargs.get("max_price") is not None:
            payload["price_max"] = float(kwargs["max_price"])

        response = await self._request(
            method="POST",
            path=f"/product/{API_VERSION}/products/search",
            params={"page_size": str(limit), "page_token": ""},
            body=payload,
        )
        products = (response.get("data") or {}).get("products") or []
        return [c for c in (self._to_candidate(p, query) for p in products) if c is not None]

    async def get_trending(
        self,
        category: Optional[str] = None,
        limit: int = 10,
    ) -> List[ProductCandidate]:
        """
        Pull the trend feed — hottest SKUs in the seller's region, ranked by
        `units_sold_7d`.

        TikTok Shop exposes this as `/product/{VERSION}/trend/feed`. If the
        category is provided, results are filtered to that category_id.
        """
        limit = max(1, min(int(limit), 100))
        params: Dict[str, Any] = {"region": self.region, "page_size": str(limit)}
        if category:
            params["category_id"] = str(category)

        response = await self._request(
            method="GET",
            path=f"/product/{API_VERSION}/trend/feed",
            params=params,
        )
        items = (response.get("data") or {}).get("items") or []
        return [c for c in (self._to_candidate(i, category) for i in items) if c is not None]

    # --------------------------------------------------------------- parsers
    @staticmethod
    def _normalize_velocity(units_7d: int, views_7d: int) -> float:
        """
        Blend units_sold_7d and view_count_7d into a 0–100 trend score.

        Units sold dominate (0.7 weight) because real purchases are a stronger
        signal than impressions. Views contribute the remaining 0.3 as a
        tie-breaker between catalog listings with sparse sales. Both axes are
        log-compressed so a single viral outlier doesn't collapse the scale.
        """
        import math

        # log1p(units_7d=1000) ≈ 6.9; target mid-range around 200 units/wk.
        units_norm = min(1.0, math.log1p(max(units_7d, 0)) / math.log1p(1000))
        views_norm = min(1.0, math.log1p(max(views_7d, 0)) / math.log1p(500_000))
        blended = (0.7 * units_norm) + (0.3 * views_norm)
        return round(blended * 100, 1)

    def _to_candidate(
        self, raw: Dict[str, Any], query_or_category: Optional[str]
    ) -> Optional[ProductCandidate]:
        """Map a raw TikTok Shop product payload into a ProductCandidate."""
        try:
            name = raw.get("title") or raw.get("name") or raw.get("product_name")
            if not name:
                return None
            product_id = raw.get("product_id") or raw.get("id")
            price_obj = raw.get("price") or {}
            # TikTok Shop returns `price.original_price` as a string in shop currency.
            price = None
            currency = "USD"
            if isinstance(price_obj, dict):
                raw_price = price_obj.get("original_price") or price_obj.get("sale_price")
                currency = price_obj.get("currency") or "USD"
                if raw_price is not None:
                    try:
                        price = float(raw_price)
                    except (TypeError, ValueError):
                        price = None
            elif isinstance(price_obj, (int, float, str)):
                try:
                    price = float(price_obj)
                except (TypeError, ValueError):
                    price = None

            # Image
            images = raw.get("main_images") or raw.get("images") or []
            image_url = None
            if images:
                first = images[0]
                if isinstance(first, dict):
                    image_url = first.get("url") or first.get("uri")
                elif isinstance(first, str):
                    image_url = first

            # Velocity signals
            units_7d = int(raw.get("sale_count_7d") or raw.get("units_sold_7d") or 0)
            views_7d = int(raw.get("view_count_7d") or raw.get("views_7d") or 0)
            trend_score = self._normalize_velocity(units_7d, views_7d)

            # Rating
            rating = raw.get("avg_rating") or raw.get("rating") or 0
            try:
                supplier_rating = float(rating)
            except (TypeError, ValueError):
                supplier_rating = None

            # Product URL (TikTok Shop public-facing permalink)
            product_url = raw.get("product_url") or raw.get("permalink")
            if not product_url and product_id:
                product_url = (
                    f"https://shop.tiktok.com/view/product/{product_id}"
                )

            tags = [
                f"units_sold_7d:{units_7d}",
                f"views_7d:{views_7d}",
            ]
            if query_or_category:
                tags.append(f"source_query:{query_or_category}")

            return ProductCandidate(
                name=str(name)[:200],
                source=self.source_id,
                price=price,
                currency=currency,
                url=product_url,
                image_url=image_url,
                trend_score=trend_score,
                search_volume=views_7d,
                social_mentions=None,
                social_engagement=units_7d,
                supplier_name="TikTok Shop Seller",
                supplier_rating=supplier_rating,
                category=str(query_or_category) if query_or_category else None,
                tags=tags,
            )
        except Exception as e:
            logger.warning("[tiktok_shop] parse error: %s", e)
            return None
