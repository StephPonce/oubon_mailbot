"""
Task #19: Regression test for AliExpress buyer-rating signal.

Background
----------
The AliExpress affiliate API response ALREADY contains two buyer-derived
fields for every product we discover:

  * ``evaluate_rate``  — positive-feedback % across all buyers (0-100)
  * ``lastest_volume`` — recent sales count (acts as sample-size proxy)

Before Task #19 we were using ``lastest_volume`` as ``sales_count`` but
throwing away ``evaluate_rate`` entirely. That's a buyer-derived signal
we already pay for that was being discarded — and it's strictly stronger
than the CJ "supplier-quality proxy" we were falling back on for
AE-only products with no Amazon coverage.

What this test locks down
-------------------------
1. ``_build_aliexpress_evidence`` extracts ``evaluate_rate`` and
   ``lastest_volume`` into the shape the scorer expects, handling the
   messy string forms ("95%", "95.0", None, '') the API actually returns.
2. An AE-only product with a strong rating gets a non-zero sentiment
   score sourced from ``aliexpress_api`` (not CJ proxy, not 'none').
3. AE sentiment is CAPPED at 78 — it can't impersonate the Amazon tier.
4. When Amazon is present, Amazon wins (AE does not overwrite).
5. AE ranks ABOVE CJ supplier proxy — an AE-rated product outranks an
   identical CJ-only product on sentiment.
6. No evaluate_rate (empty string / None) → no AE sentiment signal
   (fails open to whatever lower tier applies, with no fake score).
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from ospra_os.intelligence.product_discovery import ProductDiscoveryEngine


# =====================================================================
# Helpers
# =====================================================================

def _bare_engine() -> ProductDiscoveryEngine:
    """Instantiate the engine without __init__ so we skip external deps."""
    return ProductDiscoveryEngine.__new__(ProductDiscoveryEngine)


def _build_ae_product(
    title: str,
    niche: str,
    evaluate_rate,
    lastest_volume: int,
    cost_price: float = 5.0,
    suggested_price: float = 19.99,
    extras: dict | None = None,
) -> dict:
    """Construct a fully-normalized AE product dict, mirroring what
    ``_fetch_aliexpress`` produces after Task #19."""
    engine = _bare_engine()
    raw_item = {
        'product_id': '1005006' + title.replace(' ', '')[:6],
        'product_title': title,
        'evaluate_rate': evaluate_rate,
        'lastest_volume': lastest_volume,
        'promotion_link': f'https://aliexpress.com/item/{title[:10]}.html',
        'commission_rate': '8.0%',
        'target_sale_price': str(cost_price),
        'target_original_price': str(cost_price * 1.5),
        'target_sale_price_currency': 'USD',
    }
    ae_evidence = engine._build_aliexpress_evidence(raw_item)

    product = {
        'title': title,
        'niche': niche,
        'cost_price': cost_price,
        'suggested_price': suggested_price,
        'source': 'aliexpress',
        'available_on': ['aliexpress'],
        'sales_count': lastest_volume,
        'commission_rate': 8.0,
        'aliexpress_rating': ae_evidence.get('rating_stars'),
        'aliexpress_buzz': ae_evidence.get('buzz_score'),
        'data_sources': {
            'aliexpress': {
                'available': True,
                'orders': lastest_volume,
                'commission': '8.0%',
                'url': raw_item['promotion_link'],
                'rating_pct': ae_evidence.get('rating_pct'),
                'rating_stars': ae_evidence.get('rating_stars'),
                'buzz_score': ae_evidence.get('buzz_score'),
                'found_real_rating': ae_evidence.get('found_real_rating'),
            },
            'aliexpress_signals': ae_evidence,
        },
    }
    if extras:
        product.update(extras)
    return product


# =====================================================================
# Tests
# =====================================================================

def test_evidence_builder_shapes():
    engine = _bare_engine()

    # Happy path with percent sign
    ev1 = engine._build_aliexpress_evidence({
        'evaluate_rate': '95.0%',
        'lastest_volume': 1500,
        'promotion_link': 'https://aliexpress.com/item/x.html',
    })
    assert ev1['found_real_rating'] is True
    assert ev1['rating_pct'] == 95.0
    assert ev1['rating_stars'] == 4.75
    assert ev1['buzz_score'] is not None and 0 < ev1['buzz_score'] <= 85
    assert ev1['supplier_url'].startswith('https://aliexpress.com/')
    assert ev1['source_type'] == 'aliexpress_affiliate_api'

    # No rating → honest empty state (not a fake baseline)
    ev2 = engine._build_aliexpress_evidence({
        'evaluate_rate': '',
        'lastest_volume': 500,
    })
    assert ev2['found_real_rating'] is False
    assert ev2['rating_pct'] is None
    assert ev2['rating_stars'] is None
    assert ev2['buzz_score'] is None

    # Malformed rating → fails open, doesn't crash
    ev3 = engine._build_aliexpress_evidence({
        'evaluate_rate': 'not-a-number',
        'lastest_volume': 100,
    })
    assert ev3['found_real_rating'] is False

    # Cap: even perfect rating + huge volume can't exceed 85
    ev4 = engine._build_aliexpress_evidence({
        'evaluate_rate': 100,
        'lastest_volume': 999999,
    })
    assert ev4['buzz_score'] <= 85.0, (
        f"AE buzz must cap at 85 (< Amazon ceiling). Got {ev4['buzz_score']}"
    )

    print("[A PASS] evidence builder handles all input shapes correctly.")


def test_ae_lifts_sentiment_for_ae_only_product():
    engine = _bare_engine()
    product = _build_ae_product(
        title='Smart LED Strip',
        niche='smart_home',
        evaluate_rate='94.5%',
        lastest_volume=1200,
    )

    scored = engine._calculate_scores([product])
    p = scored[0]

    assert p['sentiment_available'] is True, \
        "AE-rated product must produce a real sentiment signal"
    assert p['sentiment_source'] == 'aliexpress_api', (
        f"Expected sentiment_source='aliexpress_api', got {p['sentiment_source']!r}"
    )
    assert 55 < p['sentiment_score'] <= 78, (
        f"AE sentiment should lift above neutral(55) but be capped at 78. "
        f"Got {p['sentiment_score']}"
    )
    assert 'aliexpress_ratings' in p.get('sources_validated', []), \
        "AE ratings must appear in sources_validated when the signal is real"
    print(f"[B PASS] AE-only product gets sentiment={p['sentiment_score']} "
          f"via source={p['sentiment_source']}.")


def test_amazon_wins_when_both_present():
    engine = _bare_engine()
    product = _build_ae_product(
        title='Smart Plug WiFi',
        niche='smart_home',
        evaluate_rate='90.0%',
        lastest_volume=800,
    )
    # Inject Amazon signal (would come from the reviews enricher)
    product['data_sources']['amazon_reviews'] = {
        'available': True,
        'buzz_score': 88.0,
        'aggregate_rating': 4.6,
        'total_reviews': 2400,
    }
    product['amazon_buzz'] = 88.0

    scored = engine._calculate_scores([product])
    p = scored[0]

    assert p['sentiment_source'] == 'amazon_reviews', (
        f"Amazon must dominate when present. Got {p['sentiment_source']!r}"
    )
    assert p['sentiment_score'] >= 85, (
        f"With amazon buzz=88, sentiment should be >= 85. Got {p['sentiment_score']}"
    )
    print(f"[C PASS] Amazon wins over AE (sentiment={p['sentiment_score']} "
          f"via {p['sentiment_source']}).")


def test_ae_outranks_cj_proxy():
    engine = _bare_engine()

    # Product with AE evaluate_rate signal, no Amazon, no CJ
    ae_only = _build_ae_product(
        title='AE Rated Gadget',
        niche='smart_home',
        evaluate_rate='96.0%',
        lastest_volume=1800,
    )

    # Equivalent CJ-only product — no AE rating, falls back to CJ proxy.
    # We construct it by hand because it's not an AE product.
    cj_only = {
        'title': 'CJ Only Gadget',
        'niche': 'smart_home',
        'cost_price': 4.0,
        'suggested_price': 19.99,
        'source': 'cj_dropshipping',
        'available_on': ['cj_dropshipping'],
        'us_warehouse': True,
        'image_count': 8,
        'all_images': ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'],
        'data_sources': {
            'cj_dropshipping': {'available': True, 'warehouse': 'US'},
        },
    }

    scored = engine._calculate_scores([ae_only, cj_only])
    ae_scored = next(p for p in scored if p['title'] == 'AE Rated Gadget')
    cj_scored = next(p for p in scored if p['title'] == 'CJ Only Gadget')

    assert ae_scored['sentiment_score'] is not None
    assert cj_scored['sentiment_score'] is not None
    assert ae_scored['sentiment_score'] > cj_scored['sentiment_score'], (
        f"AE buyer-rated product should outrank CJ-proxy-only on sentiment. "
        f"AE={ae_scored['sentiment_score']} vs CJ={cj_scored['sentiment_score']}"
    )
    assert ae_scored['sentiment_source'] == 'aliexpress_api'
    assert cj_scored['sentiment_source'] == 'cj_supplier_proxy'
    print(f"[D PASS] AE tier ({ae_scored['sentiment_score']}) outranks "
          f"CJ proxy ({cj_scored['sentiment_score']}).")


def test_missing_rating_fails_open_not_fake():
    engine = _bare_engine()
    # AE returned the product but evaluate_rate came back empty — common
    # for brand-new SKUs. Must NOT produce a sentiment score out of thin air.
    product = _build_ae_product(
        title='Brand New SKU',
        niche='smart_home',
        evaluate_rate='',          # no rating
        lastest_volume=0,
    )

    scored = engine._calculate_scores([product])
    p = scored[0]
    assert p['sentiment_available'] is False, (
        "No AE rating + no other signals must produce sentiment_available=False, "
        f"not a fake baseline. Got sentiment_score={p['sentiment_score']} "
        f"sentiment_source={p['sentiment_source']!r}"
    )
    assert p['sentiment_score'] is None
    print("[E PASS] Empty evaluate_rate → sentiment_available=False (no fake score).")


def test_breakdown_exposes_ae_signal():
    engine = _bare_engine()
    product = _build_ae_product(
        title='Breakdown Check',
        niche='smart_home',
        evaluate_rate='92.0%',
        lastest_volume=900,
    )
    scored = engine._calculate_scores([product])
    bd = scored[0]['score_breakdown']
    assert bd.get('aliexpress_buzz') is not None, (
        f"score_breakdown must expose aliexpress_buzz. Got {bd}"
    )
    assert bd.get('aliexpress_rating') is not None
    print(f"[F PASS] score_breakdown exposes AE signals: "
          f"buzz={bd['aliexpress_buzz']}, rating={bd['aliexpress_rating']}.")


def run_all():
    test_evidence_builder_shapes()
    test_ae_lifts_sentiment_for_ae_only_product()
    test_amazon_wins_when_both_present()
    test_ae_outranks_cj_proxy()
    test_missing_rating_fails_open_not_fake()
    test_breakdown_exposes_ae_signal()
    print("\n[PASS] AliExpress buyer-rating signal wired end-to-end.")
    return 0


if __name__ == "__main__":
    sys.exit(run_all())
