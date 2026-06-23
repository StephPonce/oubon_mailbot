"""
Catalog warm — scheduled discovery → persistent catalog (#56).

Runs the REAL discovery engine across many niches on a schedule and upserts the
graded results into `discovered_catalog` (the durable, cross-process store the
API reads). This is what turns discovery from "one niche, on demand, in-memory"
into "dozens of graded products with a track record" on the dashboard.

Run manually or as a Render cron:
    python -m ospra_os.tasks.catalog_warm

Env knobs:
    DISCOVERY_CATALOG_NICHES   comma list (default: the 10 built-in niches)
    DISCOVERY_CATALOG_COUNT    products to request per niche (default 20)

Self-bootstrapping: creates the table if missing, so the cron can run before
any web deploy has provisioned it (same pattern as trend_warm).
"""

import asyncio
import hashlib
import logging
import os
import sys
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("catalog_warm")

DEFAULT_NICHES = [
    "smart_home", "kitchen", "fitness", "beauty", "tech",
    "home_decor", "pet", "outdoor", "office", "gaming",
]
COUNT_PER_NICHE = int(os.getenv("DISCOVERY_CATALOG_COUNT", "20"))


def _niches() -> list:
    raw = os.getenv("DISCOVERY_CATALOG_NICHES", "").strip()
    if raw:
        return [n.strip() for n in raw.split(",") if n.strip()]
    return DEFAULT_NICHES


def _session():
    from ospra_os.database.connection import SessionLocal
    return SessionLocal()


def _bootstrap_table() -> None:
    from ospra_os.database.base import Base
    from ospra_os.database.connection import engine
    from ospra_os.database.discovered_catalog import DiscoveredProduct
    from ospra_os.database.product_timeseries import ProductTimeseries

    Base.metadata.create_all(
        bind=engine,
        tables=[DiscoveredProduct.__table__, ProductTimeseries.__table__],
    )


def _int_or_none(v):
    try:
        return int(v) if v is not None and v != "" else None
    except (TypeError, ValueError):
        return None


def _float_or_none(v):
    try:
        return float(v) if v is not None and v != "" else None
    except (TypeError, ValueError):
        return None


def _extract_timeseries_signals(product: dict) -> dict:
    """Pull the raw daily signals (the moat columns) off the product dict.

    Every signal is None when absent — never a fabricated zero — so the
    confidence gate can mark thin days as low-confidence, not bad products.
    """
    ds = product.get("data_sources") or {}
    ae = ds.get("aliexpress") or {}
    tiktok_shop = ds.get("tiktok_shop") or {}

    meta_adv = _int_or_none(product.get("meta_niche_advertiser_count"))
    ae_orders = _int_or_none(
        product.get("sales_count") or ae.get("orders") or product.get("lastest_volume")
    )
    gt = product.get("google_trend_score")
    if gt is None:
        gt = (ds.get("google_trends") or {}).get("interest")
    google_trends = _float_or_none(gt)
    tt_units = _int_or_none(
        product.get("tiktok_units_sold") or tiktok_shop.get("units_sold_7d")
    )
    tt_velocity = _float_or_none(
        product.get("tiktok_velocity") or tiktok_shop.get("velocity")
    )

    signals = {
        "meta_advertiser_count": meta_adv,
        "aliexpress_orders": ae_orders,
        "google_trends_interest": google_trends,
        "tiktok_units_sold": tt_units,
        "tiktok_velocity": tt_velocity,
    }
    signals["signal_count"] = sum(1 for v in signals.values() if v is not None)
    return signals


def snapshot_timeseries(session, product: dict, niche: str) -> str:
    """Upsert today's per-product time-series row. Returns 'inserted' or 'updated'.

    One row per (product_key, snapshot_date): a same-day re-run UPDATEs, a new
    day INSERTs — building the trajectory history that powers velocity grading.
    """
    from ospra_os.database.product_timeseries import ProductTimeseries

    key = _product_key(product)
    today = datetime.utcnow().date()
    cat = _extract(product, niche)  # reuse grade/score/saturation extraction
    sig = _extract_timeseries_signals(product)

    fields = {
        "niche": niche,
        "title": cat["title"],
        "grade": cat["grade"],
        "score": cat["score"],
        "saturation_score": cat["saturation_score"],
        "opportunity_score": cat["opportunity_score"],
        "velocity_phase": cat["velocity_phase"],
        "sentiment_score": cat["sentiment_score"],
        **sig,
    }

    row = (
        session.query(ProductTimeseries)
        .filter_by(product_key=key, snapshot_date=today)
        .first()
    )
    if row is None:
        session.add(ProductTimeseries(
            product_key=key, snapshot_date=today,
            created_at=datetime.utcnow(), **fields,
        ))
        return "inserted"
    for k, v in fields.items():
        setattr(row, k, v)
    return "updated"


def _product_key(product: dict) -> str:
    title = (product.get("title") or product.get("product_name") or "").strip().lower()
    image = (product.get("image_url") or product.get("main_image") or "").strip()
    return hashlib.sha256(f"{title}|{image}".encode()).hexdigest()[:32]


def _extract(product: dict, niche: str) -> dict:
    """Pull the columns we index/filter on out of the full product dict."""
    saturation = product.get("saturation_score")
    opportunity = None
    if isinstance(saturation, (int, float)):
        # saturation may be 0-1 or 0-100; normalize to 0-100 for storage.
        sat100 = saturation * 100 if saturation <= 1 else saturation
        opportunity = round(max(0.0, 100.0 - sat100), 1)
        saturation = round(sat100, 1)
    return {
        "niche": niche,
        "title": (product.get("title") or product.get("product_name") or "")[:512],
        "image_url": product.get("image_url") or product.get("main_image"),
        "supplier": product.get("source") or product.get("supplier"),
        "grade": (product.get("grade") or product.get("tier") or product.get("recommendation") or "")[:16] or None,
        "score": product.get("final_score") or product.get("oi_score") or product.get("score"),
        "saturation_score": saturation,
        "opportunity_score": opportunity,
        "velocity_phase": product.get("velocity_phase") or product.get("lifecycle_phase"),
        "sentiment_score": product.get("sentiment_score"),
        "payload": product,
    }


def upsert_product(session, product: dict, niche: str) -> str:
    """Insert a new catalog row or refresh an existing one (preserving
    first_seen_at). Returns 'new' or 'seen'."""
    from ospra_os.database.discovered_catalog import DiscoveredProduct

    key = _product_key(product)
    fields = _extract(product, niche)
    now = datetime.utcnow()

    row = session.query(DiscoveredProduct).filter_by(product_key=key).first()
    if row is None:
        row = DiscoveredProduct(
            product_key=key, first_seen_at=now, last_seen_at=now, times_seen=1,
            created_at=now, **fields,
        )
        session.add(row)
        return "new"

    # Re-surfaced: bump proof signals, refresh the volatile fields, KEEP first_seen_at.
    row.last_seen_at = now
    row.times_seen = (row.times_seen or 0) + 1
    for k, v in fields.items():
        setattr(row, k, v)
    return "seen"


async def warm_niche(niche: str) -> dict:
    """Run discovery for one niche and persist the results."""
    from ospra_os.intelligence.product_discovery import discover_products

    logger.info(f"[{niche}] discovering (count={COUNT_PER_NICHE})...")
    try:
        products = await discover_products(niche=niche, count=COUNT_PER_NICHE)
    except Exception as e:  # one bad niche must not abort the whole run
        logger.error(f"[{niche}] discovery failed: {e}")
        return {"niche": niche, "discovered": 0, "new": 0, "seen": 0, "error": str(e)}

    new = seen = 0
    session = _session()
    try:
        snapshots = 0
        for p in products or []:
            try:
                result = upsert_product(session, p, niche)
                new += result == "new"
                seen += result == "seen"
                # #56 Phase 1 (the moat): also write today's time-series row.
                snapshot_timeseries(session, p, niche)
                snapshots += 1
            except Exception as e:
                logger.warning(f"[{niche}] skip one product: {e}")
                session.rollback()
        session.commit()
    finally:
        session.close()

    logger.info(
        f"[{niche}] discovered={len(products or [])} new={new} refreshed={seen} "
        f"snapshots={snapshots}"
    )
    return {
        "niche": niche, "discovered": len(products or []),
        "new": new, "seen": seen, "snapshots": snapshots,
    }


async def run() -> dict:
    _bootstrap_table()
    # Reset the per-run Apify circuit breaker / spend counters (cost brief).
    try:
        from ospra_os.product_research.connectors.apify.base_apify import reset_apify_budget
        reset_apify_budget()
    except Exception:
        pass
    niches = _niches()
    logger.info(f"Catalog warm starting for {len(niches)} niches: {niches}")
    results = []
    for niche in niches:  # serial: discovery is API-heavy; avoid hammering suppliers
        results.append(await warm_niche(niche))
    total_new = sum(r.get("new", 0) for r in results)
    total_seen = sum(r.get("seen", 0) for r in results)
    total_disc = sum(r.get("discovered", 0) for r in results)
    total_snap = sum(r.get("snapshots", 0) for r in results)
    logger.info(
        f"Catalog warm complete: {total_disc} discovered across {len(niches)} niches "
        f"({total_new} new, {total_seen} refreshed, {total_snap} daily snapshots)."
    )
    # Per-run Apify spend report (actor-starts drive metered cost). In steady
    # state this should show ONLY Meta Ad Library actor-starts (~1/niche).
    apify_report = {}
    try:
        from ospra_os.product_research.connectors.apify.base_apify import get_apify_budget_report
        apify_report = get_apify_budget_report()
        logger.info(
            f"[APIFY SPEND] actor_starts={apify_report.get('actor_starts', 0)} "
            f"tripped={apify_report.get('tripped_actors', [])} "
            f"quota_failures={apify_report.get('quota_failures', {})}"
        )
    except Exception:
        pass
    return {
        "niches": len(niches), "discovered": total_disc, "new": total_new,
        "seen": total_seen, "snapshots": total_snap,
        "apify": apify_report, "by_niche": results,
    }


def main() -> None:
    try:
        asyncio.run(run())
    except Exception as e:
        logger.error(f"Catalog warm aborted: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
