"""
TikTok Shop units-sold snapshots + velocity (Phase 1 step 3 — the demand spine).

TikTok Shop product rows (from the Apify actor) carry a CUMULATIVE sold_count.
This module persists one snapshot per product per day into the EXISTING
``product_timeseries`` store (same table, same ``product_identity_key``, same
one-row-per-day upsert the catalog_warm cron uses — no parallel store), and
computes ``units_sold_7d`` velocity as the least-squares slope of consecutive
snapshots (× 7), via ``velocity_saturation.units_velocity_from_series``.

Identity: a TikTok Shop product is keyed by its TikTok product id —
``product_identity_key({"product_id": <tiktok id>})`` — so its history never
forks on title/image churn, and any AE/CJ-sourced product that later matches
keeps its own separate key (the merge happens on the product dict, not here).

Column semantics note: ``ProductTimeseries.tiktok_units_sold`` stores the raw
CUMULATIVE count observed that day (slope of a cumulative counter = sales
rate). ``tiktok_velocity`` stores the derived units/week once ≥3 snapshots
exist. NULL = not measured; never fabricated zeros.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

VELOCITY_WINDOW_DAYS = 14


def snapshot_tiktok_products(products: List, niche: Optional[str] = None) -> Dict[str, int]:
    """Upsert today's units-sold snapshot for each TikTok Shop product.

    ``products``: TikTokShopProduct records (or dicts with the same fields).
    Best-effort: DB problems log and return zeros — discovery never crashes
    on snapshot persistence.
    """
    stats = {"inserted": 0, "updated": 0, "skipped": 0}
    if not products:
        return stats

    try:
        from ospra_os.database.connection import SessionLocal
        from ospra_os.database.product_timeseries import (
            ProductTimeseries, product_identity_key,
        )
    except Exception as e:
        logger.warning(f"[UNITS] timeseries store unavailable: {e}")
        return stats

    today = datetime.utcnow().date()
    session = SessionLocal()
    try:
        for p in products:
            get = (lambda k, _p=p: getattr(_p, k, None)) if not isinstance(p, dict) \
                else (lambda k, _p=p: _p.get(k))
            tiktok_id = get("tiktok_product_id")
            sold = get("sold_count")
            if not tiktok_id or sold is None:
                stats["skipped"] += 1
                continue

            key = product_identity_key({"product_id": str(tiktok_id)})

            row = (
                session.query(ProductTimeseries)
                .filter_by(product_key=key, snapshot_date=today)
                .first()
            )
            fields = {
                "niche": niche,
                "title": (get("title") or "")[:512] or None,
                "tiktok_units_sold": int(sold),
                "seen_in_discovery": True,
            }
            if row is None:
                row = ProductTimeseries(
                    product_key=key, snapshot_date=today,
                    created_at=datetime.utcnow(),
                    signal_count=1,
                    **fields,
                )
                session.add(row)
                stats["inserted"] += 1
            else:
                for k, v in fields.items():
                    if v is not None:
                        setattr(row, k, v)
                stats["updated"] += 1

            # Derive velocity AFTER upserting so today's own measurement is
            # part of the slope (autoflush makes the new row visible to the
            # in-session history query).
            velocity = load_units_velocity(str(tiktok_id), session=session)
            row.tiktok_velocity = velocity["units_weekly"] if velocity else None
        session.commit()
    except Exception as e:
        session.rollback()
        logger.warning(f"[UNITS] snapshot failed: {e}")
    finally:
        session.close()

    if stats["inserted"] or stats["updated"]:
        logger.info(
            "[UNITS] snapshots: %d inserted, %d updated, %d skipped",
            stats["inserted"], stats["updated"], stats["skipped"],
        )
    return stats


def _load_velocity_by_key(key: str, days: int, session=None) -> Optional[Dict]:
    """units_sold_7d velocity for a pre-computed product_timeseries key. None
    until ≥3 daily measurements exist (thin data must not move grades)."""
    try:
        from ospra_os.database.connection import SessionLocal
        from ospra_os.database.product_timeseries import ProductTimeseries
        from ospra_os.intelligence.velocity_saturation import units_velocity_from_series
    except Exception:
        return None

    cutoff = datetime.utcnow().date() - timedelta(days=days)
    owns_session = session is None
    if owns_session:
        session = SessionLocal()
    try:
        rows = (
            session.query(ProductTimeseries)
            .filter(
                ProductTimeseries.product_key == key,
                ProductTimeseries.snapshot_date >= cutoff,
                ProductTimeseries.tiktok_units_sold.isnot(None),
            )
            .order_by(ProductTimeseries.snapshot_date.asc())
            .all()
        )
    except Exception as e:
        logger.debug(f"[UNITS] velocity load failed: {e}")
        return None
    finally:
        if owns_session:
            session.close()

    if not rows:
        return None
    day0 = rows[0].snapshot_date
    return units_velocity_from_series(
        [r.tiktok_units_sold for r in rows],
        day_offsets=[(r.snapshot_date - day0).days for r in rows],
    )


def load_units_velocity(
    tiktok_product_id: str,
    days: int = VELOCITY_WINDOW_DAYS,
    session=None,
) -> Optional[Dict]:
    """units_sold_7d velocity for one TikTok Shop product id."""
    from ospra_os.database.product_timeseries import product_identity_key
    key = product_identity_key({"product_id": str(tiktok_product_id)})
    return _load_velocity_by_key(key, days, session=session)


def load_units_velocity_for_product(product: dict, days: int = VELOCITY_WINDOW_DAYS,
                                    session=None) -> Optional[Dict]:
    """units_sold_7d velocity for a discovered-product dict, keyed by the SAME
    shared product_identity_key the snapshots used (so a product carrying its
    TikTok product id as ``product_id`` finds its own history). This is the
    hook the scoring pass calls to turn real units velocity into grade lift."""
    from ospra_os.database.product_timeseries import product_identity_key
    return _load_velocity_by_key(product_identity_key(product), days, session=session)


def units_velocity_boost(velocity: Optional[Dict], boost_max: float = 0.25) -> float:
    """Turn a units-velocity reading into a multiplicative grade boost in
    [1.0, 1+boost_max].

    Rising real units-sold lifts the grade; flat/declining does NOT lower it
    (non-positive velocity → 1.0), matching the module's no-fabricated-penalty
    posture. Strength is the weekly sales GROWTH relative to the current level
    (units_weekly / max(last_sold_count, floor)), clamped to [0, 1] so a
    doubling-per-week product hits the full boost and a 10%/week product gets
    a proportional slice.
    """
    if not velocity:
        return 1.0
    weekly = velocity.get("units_weekly") or 0.0
    if weekly <= 0:
        return 1.0
    base = max(int(velocity.get("last_sold_count") or 0), 50)  # floor avoids div-by-small
    rel = min(weekly / base, 1.0)
    return round(1.0 + boost_max * rel, 4)
