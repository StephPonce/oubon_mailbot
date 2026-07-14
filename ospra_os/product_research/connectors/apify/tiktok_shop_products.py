"""
TikTok Shop PRODUCT scraper (Apify) — Phase 1 of the TikTok-first demand spine.

Replaces the video-actor default (clockworks) as the TikTok Shop signal source:
this returns PRODUCT-level rows (productId, soldCount, price, rating,
reviewCount, shop) which are the raw material for units-sold velocity — the
"find winners before competitors" demand signal.

Actor selection (2026-07-14, store-metadata evidence — see Phase-1 report):
  PRIMARY  trakk/tiktok-shop-search-scraper
           ~$0.0016/product + $0.00005 start (BRONZE tier)
           → 100-product daily snapshot ≈ $0.16/day (~$4.90/mo)
           Documented output: productId, title, productUrl, currentPrice,
           originalPrice, currency, soldCount, soldText, rating, reviewCount.
           Documented input: country_code, keyword|keywords, maxItems,
           maxPages, sortBy(best_sellers|relevance|...), minSoldCount, ...
  FALLBACK pro100chok/tiktok-shop-scraper-usage ($0.002/item flat; richer
           sold fields: salesVolume, soldLast30Days, globalSold)
  PREMIUM  pratikdani/tiktok-shop-search-scraper ($0.012/result — 7.5x cost;
           documents week_sold_count directly)

LIVE VERIFICATION STATUS
------------------------
``LIVE_VERIFIED = False``: the Apify account is over its monthly usage cap
($45.12/$45.00 until 2026-08-07), so NO live run has confirmed the real
output shape yet. Per the Phase-1 methodology (field names are the #1 thing
that's wrong), this module therefore:
  * canonicalizes through explicit alias tables built from the actors'
    DOCUMENTED fields (observed on their store pages, not invented), and
  * FAILS CLOSED: if fewer than MIN_VALID_RATIO of items yield a product id
    + a parseable sold count, it returns an ``unverified_shape`` envelope
    with a key-sample for debugging — it never fabricates products.
Run ``scripts/verify_tiktok_shop_actor.py`` for ONE capped live run the
moment credits exist; flip LIVE_VERIFIED to True only after eyeballing the
dumped JSON and fixing any alias drift.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# See module docstring — flip ONLY after a real run's JSON has been inspected.
LIVE_VERIFIED = False

DEFAULT_ACTOR = "trakk/tiktok-shop-search-scraper"
FALLBACK_ACTOR = "pro100chok/tiktok-shop-scraper-usage"

# Below this fraction of parseable items the batch is treated as an unknown
# shape (actor changed its output / wrong actor configured) and NOT used.
MIN_VALID_RATIO = 0.3

# Documented-field alias tables (store-page evidence, 2026-07-14).
# Order matters: first present key wins.
_ID_KEYS = ("productId", "product_id", "id", "pid", "itemId", "item_id")
_TITLE_KEYS = ("title", "name", "productName", "product_name")
_SOLD_KEYS = (
    "soldCount", "sold_count", "sold", "salesVolume", "sales_volume",
    "unitsSold", "units_sold", "globalSold", "global_sold",
)
_SOLD_TEXT_KEYS = ("soldText", "sold_text", "sold_count_str", "soldCountStr")
_PRICE_KEYS = ("currentPrice", "current_price", "price", "salePrice", "sale_price", "final_price")
_RATING_KEYS = ("rating", "productRating", "product_rating", "stars", "star")
_REVIEWS_KEYS = ("reviewCount", "review_count", "reviews", "reviewsCount", "reviews_count")
_SHOP_KEYS = ("shopName", "shop_name", "seller", "sellerName", "seller_name", "storeName", "store_name", "shop")
_URL_KEYS = ("productUrl", "product_url", "url", "link", "productLink")

_SOLD_TEXT_RE = re.compile(r"([\d.,]+)\s*([kKmM]?)")


@dataclass
class TikTokShopProduct:
    """Canonical product-level record the demand spine consumes."""
    tiktok_product_id: str
    title: str
    sold_count: int                      # CUMULATIVE units sold as observed today
    price: Optional[float] = None
    rating: Optional[float] = None
    review_count: Optional[int] = None
    shop_name: Optional[str] = None
    url: Optional[str] = None
    raw_keys: List[str] = field(default_factory=list)  # observability

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tiktok_product_id": self.tiktok_product_id,
            "title": self.title,
            "sold_count": self.sold_count,
            "price": self.price,
            "rating": self.rating,
            "review_count": self.review_count,
            "shop_name": self.shop_name,
            "url": self.url,
        }


def _first(item: Dict, keys) -> Any:
    for k in keys:
        if k in item and item[k] not in (None, ""):
            return item[k]
    return None


def _parse_sold(item: Dict) -> Optional[int]:
    """Parse a cumulative sold count. Numeric fields first; '12.3k'-style
    strings second. Returns None (NOT 0) when nothing parseable exists —
    absence must stay distinguishable from 'zero sold'."""
    val = _first(item, _SOLD_KEYS)
    if val is not None:
        try:
            n = int(float(val))
            return n if n >= 0 else None
        except (TypeError, ValueError):
            pass
        # fall through to text parse of the same value
        val_text = str(val)
    else:
        val_text = None

    text = val_text or _first(item, _SOLD_TEXT_KEYS)
    if not text:
        return None
    m = _SOLD_TEXT_RE.search(str(text))
    if not m:
        return None
    try:
        num = float(m.group(1).replace(",", ""))
    except ValueError:
        return None
    suffix = m.group(2).lower()
    if suffix == "k":
        num *= 1_000
    elif suffix == "m":
        num *= 1_000_000
    return int(num)


def _parse_price(item: Dict) -> Optional[float]:
    val = _first(item, _PRICE_KEYS)
    if val is None:
        return None
    if isinstance(val, dict):  # some actors nest {value, currency}
        val = val.get("value") or val.get("amount")
    try:
        return float(str(val).replace("$", "").replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def _parse_num(item: Dict, keys, cast=float):
    val = _first(item, keys)
    if val is None:
        return None
    try:
        return cast(str(val).replace(",", ""))
    except (TypeError, ValueError):
        return None


def parse_items(items: List[Dict]) -> Dict[str, Any]:
    """Canonicalize raw actor items. STRICT: an item counts as valid only if
    it yields a product id, a title, and a parseable sold count. When fewer
    than MIN_VALID_RATIO of items are valid, the whole batch is rejected as
    an unknown shape (see module docstring)."""
    if not items:
        return {"status": "empty", "products": [], "invalid_count": 0}

    products: List[TikTokShopProduct] = []
    invalid = 0
    for item in items:
        if not isinstance(item, dict):
            invalid += 1
            continue
        pid = _first(item, _ID_KEYS)
        title = _first(item, _TITLE_KEYS)
        sold = _parse_sold(item)
        if pid is None or not title or sold is None:
            invalid += 1
            continue
        products.append(TikTokShopProduct(
            tiktok_product_id=str(pid),
            title=str(title).strip(),
            sold_count=sold,
            price=_parse_price(item),
            rating=_parse_num(item, _RATING_KEYS, float),
            review_count=_parse_num(item, _REVIEWS_KEYS, lambda v: int(float(v))),
            shop_name=(_first(item, _SHOP_KEYS) or None),
            url=(_first(item, _URL_KEYS) or None),
            raw_keys=sorted(item.keys()),
        ))

    valid_ratio = len(products) / len(items)
    if valid_ratio < MIN_VALID_RATIO:
        sample_keys = sorted(items[0].keys()) if isinstance(items[0], dict) else []
        logger.error(
            "[TIKTOK-SHOP] Unrecognized actor output shape: %d/%d items parseable. "
            "First-item keys: %s — actor output drifted from the documented fields; "
            "run scripts/verify_tiktok_shop_actor.py and update the alias tables.",
            len(products), len(items), sample_keys,
        )
        return {
            "status": "unverified_shape",
            "products": [],
            "invalid_count": invalid,
            "sample_keys": sample_keys,
        }

    return {"status": "ok", "products": products, "invalid_count": invalid}


class TikTokShopProductsScraper:
    """Fetch product-level TikTok Shop rows via a paid Apify actor.

    Cost hygiene: every call is capped by ``max_items`` (default from
    TIKTOK_SHOP_MAX_ITEMS, itself defaulting LOW). At trakk BRONZE pricing
    (~$0.0016/item) the default 100-item snapshot costs ≈ $0.16.
    """

    def __init__(self, apify_client=None):
        # Late import so this module stays importable without the client deps.
        if apify_client is None:
            from ospra_os.product_research.connectors.apify.base_apify import ApifyClient
            apify_client = ApifyClient()
        self.client = apify_client
        self.actor_id = os.getenv("APIFY_TIKTOK_SHOP_ACTOR", DEFAULT_ACTOR)
        self.max_items_default = int(os.getenv("TIKTOK_SHOP_MAX_ITEMS", "100"))
        self.country_code = os.getenv("TIKTOK_SHOP_COUNTRY", "US")

    def build_input(self, keywords: List[str], max_items: int) -> Dict[str, Any]:
        """Actor input per trakk's documented schema (country_code / keywords /
        maxItems / maxPages / sortBy). Kept as its own method so the
        verification harness and tests pin exactly what we send."""
        return {
            "country_code": self.country_code,
            "keywords": keywords,
            "maxItems": max_items,
            "maxPages": max(1, min(10, max_items // 20 or 1)),
            "sortBy": "best_sellers",
        }

    async def fetch_products(
        self,
        keywords: List[str],
        max_items: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Run the actor and canonicalize. Returns
        {status, products: [TikTokShopProduct], actor_id, cost_estimate_usd}."""
        max_items = max_items or self.max_items_default
        run_input = self.build_input(keywords, max_items)

        items = await self.client.run_actor(
            actor_id=self.actor_id,
            run_input=run_input,
            timeout_secs=int(os.getenv("TIKTOK_SHOP_TIMEOUT_SECS", "240")),
            memory_mbytes=int(os.getenv("TIKTOK_SHOP_MEMORY_MB", "512")),
            max_items=max_items,
        )

        parsed = parse_items(items)
        parsed["actor_id"] = self.actor_id
        # Listed BRONZE-tier estimate; refine against real run charges.
        parsed["cost_estimate_usd"] = round(0.00005 + 0.0016 * len(items), 4)
        if parsed["status"] == "ok":
            logger.info(
                "[TIKTOK-SHOP] %s returned %d products (%d unparseable) ~$%.4f",
                self.actor_id, len(parsed["products"]), parsed["invalid_count"],
                parsed["cost_estimate_usd"],
            )
        return parsed
