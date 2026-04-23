"""
Task #17: Unit test for SentimentRefresher.

Scenario: 4 products in 2 niches (smart_home × 3, fitness × 1).
- Mock Amazon enrichment returns buzz=70 for product 1, None for the rest.
- Mock Twitter enrichment returns sentiment=60 for product 3.
- Mock Reddit enrichment returns sentiment=55 for product 4.
- Product 2 has NO signal from any source → must be skipped, not written.

Assertions:
  1. The refresher picks the highest-tier signal available per product
     (Amazon > Twitter > Reddit) — matches _calculate_scores tier priority.
  2. Products with zero signal are counted as 'skipped', not 'refreshed'
     (no fake baseline scores).
  3. The writer is invoked exactly once per refreshed product.
  4. Per-niche batching groups products by niche before enrichment.
  5. A thrown exception from one niche does not kill the others.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from ospra_os.intelligence.sentiment_refresher import SentimentRefresher


# =========================================================================
# Fake discovery engine — exposes only the sentinel-flag attributes and
# the three _enrich_with_* methods we care about. No __init__ required.
# =========================================================================

class FakeEngine:
    def __init__(self):
        self.amazon_reviews_available = True
        self.xai_available = True
        self.reddit_available = True
        self.calls = {'amazon': 0, 'twitter': 0, 'reddit': 0}
        self.raise_on_niche = None

    async def _enrich_with_amazon_reviews(self, products, niche):
        self.calls['amazon'] += 1
        if self.raise_on_niche == niche:
            raise RuntimeError(f"Simulated Amazon crash on niche={niche}")
        # Product 1 ("Smart LED Strip") gets a real Amazon signal
        for p in products:
            if p.get('title') == 'Smart LED Strip':
                p['amazon_buzz'] = 70.0
                p['amazon_rating'] = 4.5
        return products

    async def _enrich_with_twitter_sentiment(self, products):
        self.calls['twitter'] += 1
        for p in products:
            if p.get('title') == 'Smart Plug':
                p['twitter_sentiment'] = 60.0
        return products

    async def _enrich_with_reddit_sentiment(self, products, niche):
        self.calls['reddit'] += 1
        for p in products:
            if p.get('title') == 'Resistance Band':
                p['reddit_sentiment'] = 55.0
        return products


# =========================================================================
# Tests
# =========================================================================

async def run_tests():
    # -- SETUP: 4 watched products in 2 niches ----------------------------
    watched = [
        {'id': 1, 'title': 'Smart LED Strip', 'niche': 'smart_home', 'price': 19.99},
        {'id': 2, 'title': 'Smart Home Hub',  'niche': 'smart_home', 'price': 49.00},
        {'id': 3, 'title': 'Smart Plug',      'niche': 'smart_home', 'price': 12.50},
        {'id': 4, 'title': 'Resistance Band', 'niche': 'fitness',    'price': 18.00},
    ]

    writes = []  # list of (product_id, score)

    def fake_writer(product, score):
        writes.append((product.get('id'), round(score, 2)))

    engine = FakeEngine()
    refresher = SentimentRefresher(
        engine=engine,
        watched_loader=lambda: [dict(p) for p in watched],  # fresh copies
        writer=fake_writer,
    )

    # -- RUN --------------------------------------------------------------
    summary = await refresher.refresh_watched_products()

    print("\n[SUMMARY]", summary)
    print("[WRITES] ", writes)

    # -- ASSERTIONS -------------------------------------------------------

    # 1) Amazon called once per niche (2 niches). Twitter & Reddit likewise.
    assert engine.calls['amazon'] == 2, f"Expected 2 Amazon calls, got {engine.calls['amazon']}"
    assert engine.calls['twitter'] == 2, f"Expected 2 Twitter calls, got {engine.calls['twitter']}"
    assert engine.calls['reddit'] == 2, f"Expected 2 Reddit calls, got {engine.calls['reddit']}"

    # 2) Product 1 (Amazon buzz=70, rating=4.5) → 70*0.6 + (4.5/5)*100*0.4 = 42 + 36 = 78
    # 3) Product 3 (Twitter=60, no Amazon) → 60
    # 4) Product 4 (Reddit=55, no Amazon, no Twitter) → 55
    # 5) Product 2 (no signal) → skipped, no write
    write_map = dict(writes)
    assert 1 in write_map, f"Product 1 should have been written, got writes={writes}"
    assert 3 in write_map, f"Product 3 should have been written, got writes={writes}"
    assert 4 in write_map, f"Product 4 should have been written, got writes={writes}"
    assert 2 not in write_map, (
        f"Product 2 has no signal and must be skipped (not written). Got: {writes}"
    )

    # 6) Amazon score for product 1 uses the buzz+rating blend
    p1_score = write_map[1]
    assert 77.0 <= p1_score <= 79.0, f"P1 expected ~78 (buzz+rating blend). Got {p1_score}"

    # 7) Twitter score for product 3 is the raw twitter_sentiment
    p3_score = write_map[3]
    assert p3_score == 60.0, f"P3 expected 60 (twitter tier). Got {p3_score}"

    # 8) Reddit score for product 4 is raw reddit_sentiment
    p4_score = write_map[4]
    assert p4_score == 55.0, f"P4 expected 55 (reddit tier). Got {p4_score}"

    # 9) Summary counters
    assert summary['refreshed'] == 3, f"Expected 3 refreshed, got {summary['refreshed']}"
    assert summary['skipped'] == 1, f"Expected 1 skipped, got {summary['skipped']}"
    assert summary['attempted'] == 4, f"Expected 4 attempted, got {summary['attempted']}"

    print("\n[PASS] Refreshed 3/4 products correctly. Product 2 skipped (no signal, no fake score).")

    # -- RESILIENCE: a crashing niche must not kill siblings --------------
    engine2 = FakeEngine()
    engine2.raise_on_niche = 'fitness'  # fitness niche will throw
    writes2 = []
    refresher2 = SentimentRefresher(
        engine=engine2,
        watched_loader=lambda: [dict(p) for p in watched],
        writer=lambda p, s: writes2.append((p['id'], round(s, 2))),
    )
    summary2 = await refresher2.refresh_watched_products()
    print("\n[RESILIENCE SUMMARY]", summary2)
    print("[RESILIENCE WRITES] ", writes2)

    # Smart home niche should still write products 1 & 3 even though fitness crashed
    ids_written2 = {w[0] for w in writes2}
    assert 1 in ids_written2, f"Smart-home P1 must still be written when fitness crashes. Got {writes2}"
    assert 3 in ids_written2, f"Smart-home P3 must still be written when fitness crashes. Got {writes2}"
    assert 4 not in ids_written2, f"Fitness P4 must NOT be written on crash. Got {writes2}"
    assert summary2['errors'] >= 1, "Crashing niche must increment error count"

    print("\n[PASS] Crash resilience verified: one niche failure didn't block the others.")

    return 0


if __name__ == "__main__":
    rc = asyncio.run(run_tests())
    sys.exit(rc)
