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

    Base.metadata.create_all(bind=engine, tables=[DiscoveredProduct.__table__])


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
        for p in products or []:
            try:
                result = upsert_product(session, p, niche)
                new += result == "new"
                seen += result == "seen"
            except Exception as e:
                logger.warning(f"[{niche}] skip one product: {e}")
                session.rollback()
        session.commit()
    finally:
        session.close()

    logger.info(f"[{niche}] discovered={len(products or [])} new={new} refreshed={seen}")
    return {"niche": niche, "discovered": len(products or []), "new": new, "seen": seen}


async def run() -> dict:
    _bootstrap_table()
    niches = _niches()
    logger.info(f"Catalog warm starting for {len(niches)} niches: {niches}")
    results = []
    for niche in niches:  # serial: discovery is API-heavy; avoid hammering suppliers
        results.append(await warm_niche(niche))
    total_new = sum(r.get("new", 0) for r in results)
    total_seen = sum(r.get("seen", 0) for r in results)
    total_disc = sum(r.get("discovered", 0) for r in results)
    logger.info(
        f"Catalog warm complete: {total_disc} discovered across {len(niches)} niches "
        f"({total_new} new, {total_seen} refreshed)."
    )
    return {"niches": len(niches), "discovered": total_disc, "new": total_new, "seen": total_seen, "by_niche": results}


def main() -> None:
    try:
        asyncio.run(run())
    except Exception as e:
        logger.error(f"Catalog warm aborted: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
