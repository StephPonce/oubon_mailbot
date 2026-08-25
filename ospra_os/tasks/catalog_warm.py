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
    from sqlalchemy import text

    from ospra_os.database.apify_cache_models import ApifyResponseCache
    from ospra_os.database.qualitative_cache_models import QualitativeReadCache
    from ospra_os.database.base import Base
    from ospra_os.database.connection import engine
    from ospra_os.database.discovered_catalog import DiscoveredProduct
    from ospra_os.database.product_timeseries import ProductTimeseries

    Base.metadata.create_all(
        bind=engine,
        tables=[
            DiscoveredProduct.__table__,
            ProductTimeseries.__table__,
            ApifyResponseCache.__table__,
            QualitativeReadCache.__table__,
        ],
    )
    # create_all never ALTERs an existing table (the June init_database lesson),
    # so backfill columns added after the table first shipped. Idempotent.
    try:
        with engine.begin() as conn:
            if engine.dialect.name == "postgresql":
                conn.execute(text(
                    "ALTER TABLE product_timeseries ADD COLUMN IF NOT EXISTS "
                    "seen_in_discovery BOOLEAN NOT NULL DEFAULT TRUE"
                ))
            else:  # sqlite (dev/tests) — no IF NOT EXISTS for ADD COLUMN
                cols = [r[1] for r in conn.exec_driver_sql(
                    "PRAGMA table_info(product_timeseries)").fetchall()]
                if "seen_in_discovery" not in cols:
                    conn.exec_driver_sql(
                        "ALTER TABLE product_timeseries ADD COLUMN "
                        "seen_in_discovery BOOLEAN NOT NULL DEFAULT 1"
                    )
    except Exception as e:
        logger.warning(f"seen_in_discovery column backfill skipped: {e}")


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
        # A real discovery hit: flips a same-day absence row back to seen.
        "seen_in_discovery": True,
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
    """Delegates to the shared identity key (re-audit M7) — supplier-ID-first,
    title|image hash only as fallback. Single source of truth lives next to the
    timeseries model so writer (here) and reader (product_discovery) can never
    drift apart again."""
    from ospra_os.database.product_timeseries import product_identity_key
    return product_identity_key(product)


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


async def warm_niche(niche: str, count: int = None, include_absences: bool = True) -> dict:
    """Run discovery for one niche and persist the results.

    ``count`` overrides COUNT_PER_NICHE — the discovery-jobs runner passes
    the caller's (tier-clamped) request size; the cron uses the env default.
    ``include_absences=False`` skips the absence-snapshot pass: a small
    user-triggered job (tier-clamped as low as 10) is NOT a full niche
    sweep — marking everything outside its pool "absent today" would poison
    the moat timeseries with false 'gone' signals. Only the cron's full
    sweep may assert absence.
    """
    from ospra_os.intelligence.product_discovery import discover_products

    if count is None:
        count = COUNT_PER_NICHE
    logger.info(f"[{niche}] discovering (count={count})...")
    try:
        # include_captions=False: the cron has no reader for Shopify captions —
        # generating them 2x/day x N niches was pure LLM spend (re-audit M11).
        products = await discover_products(
            niche=niche, count=count, include_captions=False
        )
    except Exception as e:  # one bad niche must not abort the whole run
        logger.error(f"[{niche}] discovery failed: {e}")
        return {"niche": niche, "discovered": 0, "new": 0, "seen": 0, "error": str(e)}

    new = seen = 0
    session = _session()
    seen_keys: set = set()
    try:
        snapshots = 0
        for p in products or []:
            # Re-audit M5: COMMIT PER PRODUCT. The old single-commit-per-niche
            # meant one malformed product rolled back every earlier uncommitted
            # row while the counters kept counting them — silent data loss with
            # inflated success logs. Counters now only increment AFTER commit.
            try:
                # Discovered today regardless of persistence outcome — a
                # failed COMMIT below must not mislabel the product as
                # "absent from discovery" in the absence pass.
                seen_keys.add(_product_key(p))
                result = upsert_product(session, p, niche)
                snapshot_timeseries(session, p, niche)
                session.commit()
                new += result == "new"
                seen += result == "seen"
                snapshots += 1
            except Exception as e:
                logger.warning(f"[{niche}] skip one product: {e}")
                session.rollback()

        # Re-audit M2 (survivorship bias): products in the catalog that did NOT
        # resurface today still get an "absence" snapshot (signals NULL,
        # seen_in_discovery=False), so decliners' trajectories keep recording
        # instead of truncating exactly when they'd teach the most. Bounded to
        # products seen in the last ABSENCE_WINDOW_DAYS so retired zombies
        # don't snapshot forever.
        #
        # Adversarial-review fix: ONLY when discovery itself produced output.
        # A zero-product run means the SOURCES are dead (the M6 alert case),
        # not that every product vanished — writing absence rows on outage
        # days would poison the presence data with false "gone" signals.
        absences = 0
        if products and include_absences:
            try:
                absences = _snapshot_absent_products(session, niche, seen_keys)
            except Exception as e:
                logger.warning(f"[{niche}] absence snapshots failed: {e}")
                session.rollback()
        else:
            logger.info(
                f"[{niche}] discovery returned 0 products — skipping absence "
                f"snapshots (source outage, not product disappearance)"
            )
    finally:
        session.close()

    logger.info(
        f"[{niche}] discovered={len(products or [])} new={new} refreshed={seen} "
        f"snapshots={snapshots} absence_rows={absences}"
    )
    return {
        "niche": niche, "discovered": len(products or []),
        "new": new, "seen": seen, "snapshots": snapshots, "absences": absences,
    }


ABSENCE_WINDOW_DAYS = int(os.getenv("DISCOVERY_ABSENCE_WINDOW_DAYS", "30"))


def _snapshot_absent_products(session, niche: str, seen_keys: set) -> int:
    """Write seen_in_discovery=False snapshots for recently-active catalog
    products that didn't appear in today's discovery output (re-audit M2)."""
    from datetime import timedelta

    from ospra_os.database.discovered_catalog import DiscoveredProduct
    from ospra_os.database.product_timeseries import ProductTimeseries

    today = datetime.utcnow().date()
    active_cutoff = datetime.utcnow() - timedelta(days=ABSENCE_WINDOW_DAYS)
    rows = (
        session.query(DiscoveredProduct)
        .filter(
            DiscoveredProduct.niche == niche,
            DiscoveredProduct.last_seen_at >= active_cutoff,
        )
        .all()
    )
    written = 0
    for cat in rows:
        if cat.product_key in seen_keys:
            continue
        try:
            existing = (
                session.query(ProductTimeseries)
                .filter_by(product_key=cat.product_key, snapshot_date=today)
                .first()
            )
            if existing is not None:
                continue  # already has a real row today — don't overwrite
            session.add(ProductTimeseries(
                product_key=cat.product_key,
                snapshot_date=today,
                niche=niche,
                title=cat.title,
                # Signals + grade stay NULL: nothing was measured today.
                # Absence itself is the datum.
                signal_count=0,
                seen_in_discovery=False,
                created_at=datetime.utcnow(),
            ))
            session.commit()
            written += 1
        except Exception as e:
            logger.warning(f"[{niche}] absence row failed for {cat.product_key[:8]}: {e}")
            session.rollback()
    return written


async def run() -> dict:
    _bootstrap_table()
    # Credential health FIRST (spec Step 6): a disarmed self-healer is a
    # scheduled outage — say so at the top of every run, at 14 days TO death
    # instead of 14 days after. The warm still runs (the check must never
    # cause the outage it prevents); main() turns alerts into a red exit.
    credential_alerts: list = []
    try:
        from ospra_os.core.credential_health import credential_health
        health = credential_health()
        credential_alerts = health.get("alerts", [])
        for alert in credential_alerts:
            logger.error(f"[ALERT][CREDENTIAL] {alert}")
        logger.info(
            "[CRED-HEALTH] cj(present=%s armed=%s) ae_ds(token=%s refresh_seeded=%s "
            "days_to_expiry=%s) ae_affiliate(configured=%s tracking_id=%s)",
            health["cj"]["present"], health["cj"]["healer_armed"],
            health["aliexpress_ds"]["token_source"],
            health["aliexpress_ds"]["refresh_seeded"],
            health["aliexpress_ds"]["days_to_expiry"],
            health["aliexpress_affiliate"]["configured"],
            health["aliexpress_affiliate"]["tracking_id_set"],
        )
    except Exception as e:
        logger.warning(f"[CRED-HEALTH] check failed (non-fatal): {e}")
    # Reset the per-run Apify circuit breaker / spend counters (cost brief).
    try:
        from ospra_os.product_research.connectors.apify.base_apify import reset_apify_budget
        reset_apify_budget()
    except Exception:
        pass
    # Retention: keep the response cache from growing without bound. Cheap
    # DELETE, and never fatal — a failed prune must not stop the warm.
    try:
        from ospra_os.product_research.connectors.apify.response_cache import prune
        pruned = prune()
        if pruned:
            logger.info(f"[APIFY CACHE] pruned {pruned} expired rows")
    except Exception as e:
        logger.warning(f"[APIFY CACHE] prune skipped: {e}")
    try:
        from ospra_os.intelligence.qualitative_cache import prune as _qprune
        qpruned = _qprune()
        if qpruned:
            logger.info(f"[QUAL CACHE] pruned {qpruned} expired rows")
    except Exception as e:
        logger.warning(f"[QUAL CACHE] prune skipped: {e}")
    niches = _niches()
    logger.info(f"Catalog warm starting for {len(niches)} niches: {niches}")
    results = []
    for niche in niches:  # serial: discovery is API-heavy; avoid hammering suppliers
        # Per-niche fault isolation at the RUN level. warm_niche already
        # try/excepts the discovery call, but anything that raised outside
        # that inner try (session setup, import-time failures, the absence
        # pass re-raising) aborted the WHOLE batch — one bad niche zeroed
        # out the refresh for every other niche (July 2026 stale-catalog
        # incident). One niche's crash must cost exactly one niche.
        try:
            results.append(await warm_niche(niche))
        except Exception as e:
            logger.error(f"[{niche}] niche run crashed (isolated, continuing): {e}")
            results.append({
                "niche": niche, "discovered": 0, "new": 0, "seen": 0,
                "snapshots": 0, "absences": 0, "error": str(e),
            })
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
            f"cache_hits={apify_report.get('cache_hits', 0)} "
            f"stale_served={apify_report.get('stale_served', 0)} "
            f"tripped={apify_report.get('tripped_actors', [])} "
            f"quota_failures={apify_report.get('quota_failures', {})}"
        )
    except Exception:
        pass
    # Re-audit M6: a run that discovers NOTHING across every niche means the
    # data layer is dead (expired tokens, quota, outage) and the moat clock is
    # NOT ticking. That must be loud — not a green checkmark in Render.
    if total_disc == 0 and niches:
        logger.error(
            "[ALERT] Catalog warm discovered 0 products across ALL niches — "
            "every supplier source is likely dead (check CJ/AliExpress/Apify "
            "tokens). No snapshots were written; the timeseries clock is "
            "stopped. This run will exit non-zero so Render shows it red."
        )
    return {
        "niches": len(niches), "discovered": total_disc, "new": total_new,
        "seen": total_seen, "snapshots": total_snap,
        "apify": apify_report, "by_niche": results,
        "credential_alerts": credential_alerts,
    }


def main() -> None:
    try:
        result = asyncio.run(run())
    except Exception as e:
        logger.error(f"Catalog warm aborted: {e}")
        sys.exit(1)
    # M6: empty run = failed run. Exit 2 distinguishes "sources dead" from
    # "crashed" (1) so the Render cron history tells the story at a glance.
    # Also red when products were discovered but ZERO snapshots persisted
    # (DB dead while APIs healthy) — the moat clock is equally stopped.
    if result.get("niches", 0) > 0 and (
        result.get("discovered", 0) == 0
        or (result.get("discovered", 0) > 0 and result.get("snapshots", 0) == 0)
    ):
        sys.exit(2)
    # Spec Step 6: a load-bearing self-healer is disarmed → the NEXT token
    # expiry is a scheduled outage. Red the run even though today's warm
    # succeeded — fail at 14 days TO death, not 14 days after. Exit 3 so the
    # cron history distinguishes "credential debt" from "sources dead" (2).
    if result.get("credential_alerts"):
        logger.error(
            "[ALERT] Warm completed but %d credential alert(s) are pending "
            "(see [ALERT][CREDENTIAL] lines above). Exiting non-zero so this "
            "shows red in Render.",
            len(result["credential_alerts"]),
        )
        sys.exit(3)


if __name__ == "__main__":
    main()
