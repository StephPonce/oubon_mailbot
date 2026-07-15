"""
Store-carry detector + early-adopter signal (Moat Phase 3).

Phase 1 measures REAL demand (units-sold velocity); Phase 2 filters truth
(organic vs seeded). Phase 3 answers "is it too late?": a product selling
hard on TikTok that FEW stores already carry is the pre-saturation window —
the signal worth paying for. High velocity + high store-carry means the
window has closed.

Store-carry is measured against PUBLIC Shopify catalogs: every Shopify store
serves ``{store}/products.json`` unauthenticated (verified live 2026-07-15
against oubonshop.com and colourpop.com — fields: products[].{id, title,
handle, body_html, vendor, product_type, tags, images[].src,
variants[].price}). No Apify involved, so this signal builds and verifies
under the Apify cap.

Candidate stores come from URLs discovery already collects — Meta Ad Library
sample_landing_urls and the product's own source/landing URLs. Non-Shopify
domains 404 or return HTML; both degrade gracefully to "store unknown".

Matching reuses the discovery engine's title discipline (normalized
SequenceMatcher + token Jaccard — NOTE: product_discovery has no
image-similarity helper despite folklore; its cross-supplier matcher is
price/keyword/title/category, so title-axis matching is what exists to
reuse). A store counts as carrying the product when the best per-catalog
match clears MATCH_THRESHOLD.

The count is cached per product per day in the EXISTING product_timeseries
row (``store_carry_count``, migration 006) so carry TRENDS over time —
watching store-carry fill in day over day is the saturation-timing moat.

Phase 3 step 3: the same store catalogs are where driving TikTok video URLs
live (body_html frequently embeds them). ``extract_tiktok_video_urls`` pulls
them so Phase 2's comments actor finally has product→video mapping; the live
comment scrape itself stays behind its connector's LIVE_VERIFIED gate until
Apify credits return.
"""

from __future__ import annotations

import logging
import os
import re
from datetime import datetime
from difflib import SequenceMatcher
from typing import Callable, Dict, List, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# A store "carries" the product when best-match similarity clears this.
MATCH_THRESHOLD = float(os.getenv("STORE_CARRY_MATCH_THRESHOLD", "0.60"))

# Single page of products.json — Shopify caps limit at 250 per page. One page
# is a deliberate cost/coverage tradeoff for v1 (logged when it may truncate).
CATALOG_PAGE_LIMIT = 250

FETCH_TIMEOUT_SECONDS = 12

# Marketplace / platform domains that can never be a competing Shopify
# storefront — skipping them saves dead requests (they'd degrade gracefully
# anyway, but each one costs FETCH_TIMEOUT_SECONDS in the worst case).
_NON_STORE_DOMAINS = (
    "aliexpress.", "amazon.", "cjdropshipping.", "tiktok.", "etsy.",
    "pinterest.", "facebook.", "instagram.", "google.", "youtube.",
    "reddit.", "twitter.", "x.com", "bit.ly", "walmart.", "ebay.",
    "temu.", "shein.", "alibaba.",
)

_TIKTOK_VIDEO_RE = re.compile(
    r"https?://(?:www\.|m\.)?tiktok\.com/@[\w.\-]+/video/\d+"
    r"|https?://(?:vm|vt)\.tiktok\.com/[\w]+",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Step 1a — candidate store URLs from what discovery already collects
# ---------------------------------------------------------------------------

def _base_url(url: str) -> Optional[str]:
    """https://shop.example.com/products/foo?x=1 → https://shop.example.com"""
    try:
        parsed = urlparse(url if "://" in url else f"https://{url}")
        if not parsed.netloc or "." not in parsed.netloc:
            return None
        return f"https://{parsed.netloc.lower()}"
    except Exception:
        return None


def candidate_store_urls(product: dict, extra_urls: Optional[List[str]] = None) -> List[str]:
    """Distinct candidate storefront base URLs for this product.

    Sources (all already collected by discovery — nothing new is scraped to
    build this list): Meta Ad Library winner landing URLs on the product's
    winner_provenance, any advertiser sample_landing_urls attached during
    winner matching, and the product's own landing/store URLs. Marketplace
    domains are excluded (never Shopify storefronts).
    """
    urls: List[str] = list(extra_urls or [])

    wp = product.get("winner_provenance") or {}
    for key in ("sample_url", "landing_url"):
        if wp.get(key):
            urls.append(wp[key])
    if isinstance(wp.get("sample_landing_urls"), list):
        urls.extend(u for u in wp["sample_landing_urls"] if u)

    for key in ("sample_landing_urls", "landing_urls"):
        val = product.get(key)
        if isinstance(val, list):
            urls.extend(u for u in val if u)

    for key in ("store_url", "landing_page", "product_url", "source_url"):
        if product.get(key):
            urls.append(product[key])

    out: List[str] = []
    seen = set()
    for url in urls:
        base = _base_url(str(url))
        if not base or base in seen:
            continue
        host = urlparse(base).netloc
        if any(bad in host for bad in _NON_STORE_DOMAINS):
            continue
        seen.add(base)
        out.append(base)
    return out


# ---------------------------------------------------------------------------
# Step 1b — public catalog fetch (no Apify, no auth)
# ---------------------------------------------------------------------------

# One-run catalog cache. Many products in a discovery pass share candidate
# stores (the same Meta winners feed them), and hammering one host with
# back-to-back identical fetches gets rate-limited (observed live: second
# fetch of the same catalog within a second intermittently failed). Failures
# are cached too — a store that just 403'd will 403 for the rest of the run.
_catalog_cache: Dict[str, Optional[List[Dict]]] = {}
_CATALOG_CACHE_MAX = 256


def clear_catalog_cache() -> None:
    _catalog_cache.clear()


def fetch_store_catalog(store_url: str, timeout: int = FETCH_TIMEOUT_SECONDS) -> Optional[List[Dict]]:
    """Fetch ``{store}/products.json`` — the public Shopify catalog endpoint.

    Returns a list of {"title", "handle", "body_html", "image", "price"}
    dicts, or None when the store isn't a Shopify storefront / blocks the
    request / serves non-JSON (verified failure modes: example.com → 404
    HTML; gymshark.com → CloudFront 403 HTML). None means "unknown", and
    callers must treat it as unknown — never as "doesn't carry".
    """
    cache_key = store_url.rstrip("/").lower()
    if cache_key in _catalog_cache:
        return _catalog_cache[cache_key]

    try:
        import requests
    except ImportError:  # pragma: no cover
        return None

    def _remember(result):
        if len(_catalog_cache) >= _CATALOG_CACHE_MAX:
            _catalog_cache.clear()
        _catalog_cache[cache_key] = result
        return result

    url = f"{store_url.rstrip('/')}/products.json?limit={CATALOG_PAGE_LIMIT}"
    try:
        resp = requests.get(
            url,
            timeout=timeout,
            headers={"User-Agent": "Mozilla/5.0 (compatible; OspraDiscovery/1.0)"},
            allow_redirects=True,
        )
        if resp.status_code != 200:
            logger.debug("[CARRY] %s → HTTP %s", url, resp.status_code)
            return _remember(None)
        data = resp.json()
    except Exception as e:
        logger.debug("[CARRY] %s unreachable/non-JSON: %s", url, e)
        return _remember(None)

    products = data.get("products") if isinstance(data, dict) else None
    if not isinstance(products, list):
        return _remember(None)
    if len(products) >= CATALOG_PAGE_LIMIT:
        logger.info(
            "[CARRY] %s catalog has ≥%d products (single page fetched; "
            "carry match may miss items beyond page 1)",
            store_url, CATALOG_PAGE_LIMIT,
        )

    out = []
    for p in products:
        if not isinstance(p, dict) or not p.get("title"):
            continue
        images = p.get("images") or []
        variants = p.get("variants") or []
        out.append({
            "title": p["title"],
            "handle": p.get("handle"),
            "body_html": p.get("body_html") or "",
            "image": (images[0].get("src") if images and isinstance(images[0], dict) else None),
            "price": (variants[0].get("price") if variants and isinstance(variants[0], dict) else None),
        })
    return _remember(out)


# ---------------------------------------------------------------------------
# Step 1c — fuzzy match against a catalog (title axis, discovery discipline)
# ---------------------------------------------------------------------------

def _normalize_title(title: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", (title or "").lower()).strip()


def _title_similarity(a: str, b: str) -> float:
    """max(char-level SequenceMatcher, token Jaccard) on normalized titles.

    Same two axes the discovery engine's cross-supplier matcher weights
    (title_score + keyword_score); taking the max keeps short-vs-verbose
    dropship titles ("LED Light Pad" vs "A3 LED Light Pad – 3-Level
    Dimmable Drawing Board") from false-negativing on char ratio alone.
    """
    na, nb = _normalize_title(a), _normalize_title(b)
    if not na or not nb:
        return 0.0
    char = SequenceMatcher(None, na, nb).ratio()
    ta, tb = set(na.split()), set(nb.split())
    jacc = len(ta & tb) / len(ta | tb) if ta | tb else 0.0
    return max(char, jacc)


def best_catalog_match(product_title: str, catalog: List[Dict]) -> Dict:
    """Best {similarity, title, handle, body_html} in one store's catalog."""
    best = {"similarity": 0.0, "title": None, "handle": None, "body_html": ""}
    for item in catalog:
        sim = _title_similarity(product_title, item.get("title") or "")
        if sim > best["similarity"]:
            best = {
                "similarity": sim,
                "title": item.get("title"),
                "handle": item.get("handle"),
                "body_html": item.get("body_html") or "",
            }
    return best


# ---------------------------------------------------------------------------
# Step 3 — product→video linkage from the pages we already fetch
# ---------------------------------------------------------------------------

def extract_tiktok_video_urls(html: str) -> List[str]:
    """TikTok video URLs embedded in store HTML (product body_html or a
    landing page). This is the product→video mapping Phase 2's comments
    actor needs; the actual comment scrape stays behind the connector's
    LIVE_VERIFIED gate until Apify credits return."""
    if not html:
        return []
    seen, out = set(), []
    for m in _TIKTOK_VIDEO_RE.findall(html):
        if m not in seen:
            seen.add(m)
            out.append(m)
    return out


# ---------------------------------------------------------------------------
# Step 1d — the carry measurement itself
# ---------------------------------------------------------------------------

def product_store_carry(
    product: dict,
    store_urls: Optional[List[str]] = None,
    fetch: Optional[Callable[[str], Optional[List[Dict]]]] = None,
    threshold: float = None,
) -> Dict:
    """How many distinct candidate stores already sell this product.

    Returns {
      store_carry_count: int | None,   # None = NO store could be checked → unknown
      stores_checked: int,             # catalogs actually fetched + parsed
      stores_unreachable: int,         # candidates that had no readable catalog
      carried_by: [ {store, similarity, matched_title} ],
      tiktok_video_urls: [...],        # step 3 linkage, from matched body_html
    }

    ``store_carry_count`` is None (unknown, NEVER "low") when zero catalogs
    could be read — a product whose candidate URLs are all non-Shopify must
    not masquerade as un-carried.
    """
    threshold = MATCH_THRESHOLD if threshold is None else threshold
    # Resolved at call time (not def time) so tests and callers can swap the
    # module-level fetch_store_catalog.
    fetch = fetch if fetch is not None else fetch_store_catalog
    title = product.get("title") or product.get("product_name") or ""
    urls = store_urls if store_urls is not None else candidate_store_urls(product)

    checked = 0
    unreachable = 0
    carried_by: List[Dict] = []
    video_urls: List[str] = []

    for store in urls:
        catalog = fetch(store)
        if catalog is None:
            unreachable += 1
            continue
        checked += 1
        best = best_catalog_match(title, catalog)
        if best["similarity"] >= threshold:
            carried_by.append({
                "store": store,
                "similarity": round(best["similarity"], 3),
                "matched_title": best["title"],
            })
            for vurl in extract_tiktok_video_urls(best["body_html"]):
                if vurl not in video_urls:
                    video_urls.append(vurl)

    return {
        "store_carry_count": len(carried_by) if checked > 0 else None,
        "stores_checked": checked,
        "stores_unreachable": unreachable,
        "carried_by": carried_by,
        "tiktok_video_urls": video_urls,
    }


# ---------------------------------------------------------------------------
# Step 1e — cache in product_timeseries so carry trends over time
# ---------------------------------------------------------------------------

def persist_store_carry(product: dict, carry_count: Optional[int], session=None) -> bool:
    """Upsert today's ``store_carry_count`` on the product's timeseries row.

    Same key + same one-row-per-day upsert as units_velocity snapshots.
    None (unknown) is NOT written — NULL already means "not measured", and
    overwriting a real measurement with unknown would erase signal.
    Best-effort: failures log and return False; discovery never crashes on
    cache persistence.
    """
    if carry_count is None:
        return False
    try:
        from ospra_os.database.connection import SessionLocal
        from ospra_os.database.product_timeseries import (
            ProductTimeseries, product_identity_key,
        )
    except Exception as e:
        logger.debug("[CARRY] timeseries store unavailable: %s", e)
        return False

    key = product_identity_key(product)
    today = datetime.utcnow().date()
    owns_session = session is None
    if owns_session:
        session = SessionLocal()
    try:
        row = (
            session.query(ProductTimeseries)
            .filter_by(product_key=key, snapshot_date=today)
            .first()
        )
        if row is None:
            row = ProductTimeseries(
                product_key=key,
                snapshot_date=today,
                title=(product.get("title") or "")[:512] or None,
                niche=product.get("niche"),
                signal_count=1,
                created_at=datetime.utcnow(),
            )
            session.add(row)
        row.store_carry_count = int(carry_count)
        if owns_session:
            session.commit()
        return True
    except Exception as e:
        if owns_session:
            session.rollback()
        logger.debug("[CARRY] persist failed: %s", e)
        return False
    finally:
        if owns_session:
            session.close()


def load_store_carry_for_product(product: dict, session=None) -> Optional[int]:
    """Most recent cached store_carry_count for this product (None = unknown)."""
    try:
        from ospra_os.database.connection import SessionLocal
        from ospra_os.database.product_timeseries import (
            ProductTimeseries, product_identity_key,
        )
    except Exception:
        return None

    key = product_identity_key(product)
    owns_session = session is None
    if owns_session:
        session = SessionLocal()
    try:
        row = (
            session.query(ProductTimeseries)
            .filter(
                ProductTimeseries.product_key == key,
                ProductTimeseries.store_carry_count.isnot(None),
            )
            .order_by(ProductTimeseries.snapshot_date.desc())
            .first()
        )
        return row.store_carry_count if row else None
    except Exception:
        return None
    finally:
        if owns_session:
            session.close()


# ---------------------------------------------------------------------------
# Step 2 — the early-adopter signal (velocity × carry)
# ---------------------------------------------------------------------------

# Carry thresholds: ≤ LOW distinct stores = pre-saturation window;
# ≥ HIGH = the market already moved in.
CARRY_LOW = int(os.getenv("EARLY_ADOPTER_CARRY_LOW", "2"))
CARRY_HIGH = int(os.getenv("EARLY_ADOPTER_CARRY_HIGH", "6"))


def early_adopter_signal(
    units_weekly: Optional[float],
    store_carry_count: Optional[int],
    cap: float = 0.15,
) -> Dict:
    """Combine Phase 1 velocity with store-carry into flag + bounded multiplier.

    Returns {"flag": ..., "multiplier": ...} where multiplier ∈ [1-cap, 1+cap]:

    - RISING velocity + LOW carry  → "early_adopter", boost up to 1+cap.
      Boost scales with how empty the field is (carry 0 → full cap).
    - RISING velocity + HIGH carry → "saturated", demote down to 1-cap.
      Bounded demote, mirroring the units-velocity discipline: it reorders
      within a tier, it does not fabricate a failure.
    - carry unknown (None)         → "unknown", multiplier 1.0 — NEVER assume
      low. Same for velocity unknown/flat: no timing signal, no adjustment.
    """
    if store_carry_count is None or units_weekly is None or units_weekly <= 0:
        return {"flag": "unknown" if store_carry_count is None else "neutral",
                "multiplier": 1.0}

    if store_carry_count <= CARRY_LOW:
        # carry 0 → full boost; carry == CARRY_LOW → half boost.
        openness = 1.0 - (store_carry_count / (CARRY_LOW * 2)) if CARRY_LOW else 1.0
        return {"flag": "early_adopter", "multiplier": 1.0 + cap * openness}

    if store_carry_count >= CARRY_HIGH:
        # Saturation deepens past the threshold; full demote by 2×HIGH.
        depth = min((store_carry_count - CARRY_HIGH) / CARRY_HIGH + 0.5, 1.0)
        return {"flag": "saturated", "multiplier": 1.0 - cap * depth}

    return {"flag": "neutral", "multiplier": 1.0}
