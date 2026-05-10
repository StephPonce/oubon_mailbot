"""
Task #17: Scheduled 4-hour sentiment refresh on watched products.

Context
-------
Live, continually-updated social sentiment is the stated differentiator
for Ospra OS — a discovered product is a snapshot, but a DEPLOYED /
ACTIVE product is a live SKU in the user's store whose sentiment can
materially shift in hours. This module re-runs the same sentiment
pipeline that `ProductDiscoveryEngine` uses at discovery time, against
the products the user is actively selling.

Design
------
- "Watched" = Product rows with status in {QUEUED, DEPLOYED, ACTIVE}.
  These are the rows a seller actually cares about; DISCOVERED products
  that never got deployed don't need 4-hour refresh cycles (they'll be
  re-scored on the next discovery run).
- The refresher borrows `ProductDiscoveryEngine` without going through
  `__init__` (same trick as `scripts/test_score_variance.py`). It wires
  up only the sentiment sources it needs.
- Results are written back to Product.social_score (existing column,
  re-used as the sentiment freshness channel) + Product.last_updated.
  Full sentiment evidence is NOT persisted to a new table in this pass
  — doing so would require a migration. Instead, we log the evidence
  so it's preserved in run logs. Follow-up task #17b can add a dedicated
  sentiment_snapshots table.
- All updates are wrapped in a per-product try/except: a single
  failing product never stops the rest of the batch.
- Concurrency is bounded by an asyncio.Semaphore so we don't run 1000
  parallel Apify calls.

Schedule
--------
`start_sentiment_refresh_scheduler()` wires an APScheduler IntervalTrigger
every 4 hours. On startup we also run one refresh immediately so the
dashboard isn't cold-stale after a deploy.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Default refresh cadence (configurable via env)
DEFAULT_REFRESH_INTERVAL_HOURS = 4
# Max parallel refreshes to avoid hammering Apify/Grok/Reddit
DEFAULT_CONCURRENCY = 4
# Time budget per product (seconds) — sentiment enrichers are ~3-6s each
PER_PRODUCT_TIMEOUT_SECONDS = 25


# =========================================================================
# Core refresher
# =========================================================================

class SentimentRefresher:
    """
    Re-runs sentiment enrichment on watched (live) products.

    Usage:
        refresher = SentimentRefresher()
        await refresher.refresh_watched_products()

    Dependency injection:
        refresher = SentimentRefresher(
            engine=my_test_engine,           # override discovery engine
            watched_loader=fake_loader_fn,   # override DB query
            writer=fake_writer_fn,           # override DB write
        )
    """

    def __init__(
        self,
        engine=None,
        watched_loader=None,
        writer=None,
        concurrency: int = DEFAULT_CONCURRENCY,
    ):
        self._engine = engine
        self._watched_loader = watched_loader
        self._writer = writer
        self._semaphore = asyncio.Semaphore(concurrency)

    # ---- Public entry point --------------------------------------------

    async def refresh_watched_products(self) -> Dict[str, int]:
        """
        Refresh sentiment for every watched product.

        Returns a summary dict:
            {'attempted': N, 'refreshed': M, 'errors': E, 'skipped': S}
        """
        watched = self._load_watched_products()
        if not watched:
            logger.info("[SENTIMENT-REFRESH] No watched products to refresh.")
            return {'attempted': 0, 'refreshed': 0, 'errors': 0, 'skipped': 0}

        logger.info(
            f"[SENTIMENT-REFRESH] Starting refresh for {len(watched)} watched product(s). "
            f"Concurrency={self._semaphore._value}."
        )

        engine = self._get_engine()
        if engine is None:
            logger.warning("[SENTIMENT-REFRESH] No discovery engine available; aborting.")
            return {'attempted': len(watched), 'refreshed': 0, 'errors': 0, 'skipped': len(watched)}

        # Group by niche so we can batch the per-niche Amazon search.
        by_niche: Dict[str, List[Dict]] = {}
        for p in watched:
            niche = p.get('niche') or 'general'
            by_niche.setdefault(niche, []).append(p)

        refreshed = 0
        errors = 0
        skipped = 0

        # Each niche runs in its own task; within a niche we send the whole
        # product list to the enrichment pipeline (matches the discovery flow).
        tasks = [
            self._refresh_niche_group(engine, niche, products)
            for niche, products in by_niche.items()
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for group_result in results:
            if isinstance(group_result, Exception):
                logger.error(f"[SENTIMENT-REFRESH] Niche batch failed: {group_result}")
                errors += 1
                continue
            refreshed += group_result.get('refreshed', 0)
            errors += group_result.get('errors', 0)
            skipped += group_result.get('skipped', 0)

        summary = {
            'attempted': len(watched),
            'refreshed': refreshed,
            'errors': errors,
            'skipped': skipped,
            'ran_at': datetime.now(timezone.utc).isoformat(),
        }
        logger.info(
            f"[SENTIMENT-REFRESH] Complete: {refreshed}/{len(watched)} refreshed, "
            f"{errors} errors, {skipped} skipped."
        )
        return summary

    # ---- Per-niche refresh loop ----------------------------------------

    async def _refresh_niche_group(self, engine, niche: str, products: List[Dict]) -> Dict[str, int]:
        """Run the full sentiment pipeline against one niche's worth of products."""
        refreshed = 0
        errors = 0
        skipped = 0

        try:
            # Amazon is the primary signal (one search per niche). If the
            # connector is unavailable we fall through to Twitter/Reddit.
            if getattr(engine, 'amazon_reviews_available', False):
                async with self._semaphore:
                    products = await asyncio.wait_for(
                        engine._enrich_with_amazon_reviews(products, niche),
                        timeout=PER_PRODUCT_TIMEOUT_SECONDS * max(1, len(products) // 4 + 1),
                    )

            if getattr(engine, 'xai_available', False):
                async with self._semaphore:
                    products = await asyncio.wait_for(
                        engine._enrich_with_twitter_sentiment(products),
                        timeout=PER_PRODUCT_TIMEOUT_SECONDS,
                    )

            # Reddit enrichment removed per architecture pivot (May 2026).
            # reddit_available is now hard-False at engine init; this branch
            # never fires. Kept as a comment so the refresher flow stays
            # easy to grep for if Reddit is ever revived.

        except asyncio.TimeoutError:
            logger.warning(
                f"[SENTIMENT-REFRESH] Niche '{niche}' hit enrichment timeout "
                f"(some products may have partial data)."
            )
            errors += 1

        except Exception as e:
            logger.error(f"[SENTIMENT-REFRESH] Niche '{niche}' enrichment failed: {e}")
            errors += len(products)
            return {'refreshed': 0, 'errors': errors, 'skipped': 0}

        # Write fresh scores back
        for product in products:
            try:
                new_score = self._compute_sentiment_score(product)
                if new_score is None:
                    skipped += 1
                    continue
                self._write_sentiment_score(product, new_score)
                refreshed += 1
            except Exception as e:
                logger.error(
                    f"[SENTIMENT-REFRESH] Failed to persist product "
                    f"{product.get('id') or product.get('title', '?')}: {e}"
                )
                errors += 1

        return {'refreshed': refreshed, 'errors': errors, 'skipped': skipped}

    # ---- Helpers -------------------------------------------------------

    @staticmethod
    def _compute_sentiment_score(product: Dict) -> Optional[float]:
        """
        Pick the freshest sentiment score using the same tier priority as
        ProductDiscoveryEngine._calculate_scores:
          Amazon (primary) > Twitter > Reddit > CJ proxy (capped at 70).
        Returns None if every source came back empty (honest, so we don't
        pretend we have data).
        """
        # Amazon (Apify) — highest-trust signal
        amazon_buzz = product.get('amazon_buzz')
        amazon_rating = product.get('amazon_rating')
        if amazon_buzz and amazon_buzz > 0:
            # Map buzz_score (0-100) + rating (0-5) into a combined 0-100 score.
            # Matches the logic in product_discovery._calculate_scores.
            if amazon_rating:
                rating_component = (float(amazon_rating) / 5.0) * 100.0
                return (float(amazon_buzz) * 0.6) + (rating_component * 0.4)
            return float(amazon_buzz)

        # Twitter (Grok) — secondary
        twitter_sent = product.get('twitter_sentiment')
        if twitter_sent is not None:
            return float(twitter_sent)

        # Reddit — secondary
        reddit_sent = product.get('reddit_sentiment')
        if reddit_sent is not None:
            return float(reddit_sent)

        return None

    def _load_watched_products(self) -> List[Dict]:
        """Load watched products. Override via constructor for tests."""
        if self._watched_loader is not None:
            return self._watched_loader()
        return _default_watched_loader()

    def _write_sentiment_score(self, product: Dict, score: float) -> None:
        """Write the fresh sentiment score back to the Product row."""
        if self._writer is not None:
            self._writer(product, score)
            return
        _default_writer(product, score)

    def _get_engine(self):
        """Return a ProductDiscoveryEngine (lazy init to avoid import cost at startup)."""
        if self._engine is not None:
            return self._engine
        try:
            # Construct via normal __init__ so all sentiment sources initialize.
            from ospra_os.intelligence.product_discovery import ProductDiscoveryEngine
            self._engine = ProductDiscoveryEngine()
        except Exception as e:
            logger.error(f"[SENTIMENT-REFRESH] Failed to build ProductDiscoveryEngine: {e}")
            self._engine = None
        return self._engine


# =========================================================================
# Default DB integration (separated so tests can override cleanly)
# =========================================================================

def _default_watched_loader() -> List[Dict]:
    """
    Query Product rows in a 'watched' lifecycle state and return them as
    dicts shaped like discovery output (so the enrichers can consume
    them unchanged).
    """
    try:
        from ospra_os.database import SessionLocal, Product
        from ospra_os.database.base import ProductStatus
    except Exception as e:
        logger.warning(f"[SENTIMENT-REFRESH] DB imports unavailable: {e}")
        return []

    watched_statuses = {ProductStatus.QUEUED, ProductStatus.DEPLOYED, ProductStatus.ACTIVE}

    db = SessionLocal()
    try:
        rows = (
            db.query(Product)
              .filter(Product.status.in_(watched_statuses))
              .limit(500)  # sanity cap
              .all()
        )
        out: List[Dict] = []
        for p in rows:
            out.append({
                'id': p.id,
                'title': p.title or p.product_name,
                'niche': _niche_from_tags(p.ai_tags) or 'general',
                'price': p.selling_price or p.price or 0,
                'cost_price': p.supplier_cost or 0,
                'suggested_price': p.selling_price or p.price or 0,
                'source': p.source_platform,
                'data_sources': {},
            })
        return out
    finally:
        db.close()


def _default_writer(product: Dict, score: float) -> None:
    """Update Product.social_score + bump last_updated for the given product."""
    product_id = product.get('id')
    if not product_id:
        logger.debug("[SENTIMENT-REFRESH] Product missing id, not writing to DB.")
        return

    try:
        from ospra_os.database import SessionLocal, Product
    except Exception as e:
        logger.warning(f"[SENTIMENT-REFRESH] DB imports unavailable: {e}")
        return

    db = SessionLocal()
    try:
        row = db.query(Product).filter(Product.id == product_id).first()
        if row is None:
            return
        row.social_score = float(score)
        row.last_updated = datetime.now(timezone.utc)
        db.commit()
    except Exception as e:
        logger.error(f"[SENTIMENT-REFRESH] DB write failed for product {product_id}: {e}")
        db.rollback()
    finally:
        db.close()


def _niche_from_tags(tags) -> Optional[str]:
    """Extract a niche string from a product's AI tags list."""
    if not tags or not isinstance(tags, list):
        return None
    KNOWN = {'smart_home', 'kitchen', 'fitness', 'beauty', 'tech', 'home', 'outdoor'}
    for t in tags:
        if not isinstance(t, str):
            continue
        normalized = t.lower().replace('-', '_').replace(' ', '_')
        if normalized in KNOWN:
            return normalized
    return None


# =========================================================================
# Scheduler wiring (APScheduler)
# =========================================================================

_scheduler = None


def start_sentiment_refresh_scheduler(interval_hours: Optional[int] = None):
    """
    Start the 4-hour sentiment refresh job.

    Honours env flags:
      SENTIMENT_REFRESH_ENABLED  (default: 'true')
      SENTIMENT_REFRESH_HOURS    (default: 4)
      SENTIMENT_REFRESH_RUN_ON_START (default: 'true')
    """
    global _scheduler

    enabled = os.getenv('SENTIMENT_REFRESH_ENABLED', 'true').lower() == 'true'
    if not enabled:
        logger.info("[SENTIMENT-REFRESH] Disabled via SENTIMENT_REFRESH_ENABLED=false.")
        return None

    if interval_hours is None:
        interval_hours = int(os.getenv('SENTIMENT_REFRESH_HOURS', str(DEFAULT_REFRESH_INTERVAL_HOURS)))

    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from apscheduler.triggers.interval import IntervalTrigger
    except Exception as e:
        logger.warning(f"[SENTIMENT-REFRESH] APScheduler missing: {e}")
        return None

    refresher = SentimentRefresher()

    async def _job():
        try:
            await refresher.refresh_watched_products()
        except Exception as e:
            logger.error(f"[SENTIMENT-REFRESH] Scheduled run failed: {e}")

    if _scheduler is None:
        _scheduler = AsyncIOScheduler()

    _scheduler.add_job(
        _job,
        trigger=IntervalTrigger(hours=interval_hours),
        id='sentiment_refresh',
        name=f'Sentiment refresh (every {interval_hours}h)',
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    # Optionally run immediately so the dashboard isn't cold on boot.
    if os.getenv('SENTIMENT_REFRESH_RUN_ON_START', 'true').lower() == 'true':
        try:
            loop = asyncio.get_event_loop()
            loop.create_task(_job())
        except Exception as e:
            logger.warning(f"[SENTIMENT-REFRESH] Could not kick initial run: {e}")

    if not _scheduler.running:
        _scheduler.start()

    logger.info(
        f"[SENTIMENT-REFRESH] Scheduler started (every {interval_hours}h, "
        f"concurrency={DEFAULT_CONCURRENCY})."
    )
    return _scheduler


def stop_sentiment_refresh_scheduler():
    """Stop the scheduler cleanly (for shutdown hooks / tests)."""
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
    _scheduler = None
