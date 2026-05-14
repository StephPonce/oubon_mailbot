# Task #13 — Anti-Saturation Phase 2 Handoff

**Status**: Open. Pre-work landed across Tasks #10/#11/#12 and Options A/B/C.
**Estimated effort**: 60-90 minutes of focused work in a fresh session.
**Risk**: Touches scoring + UI + cross-reference. Test coverage exists.

---

## The Problem

Discovery now fetches data from 11+ independent signal sources, but only
9 of them actually influence the OI score. The remaining **5 sources are
"orphan caches"** — their fetch methods populate instance attributes,
but `_calculate_scores` never reads those attributes, so the rich
structured data is discarded.

This means: when a smart bulb is being advertised by 5 dropshippers on
Meta AND jumped 1,000 ranks on Amazon Movers AND is trending on Etsy,
Ospra doesn't currently boost its score for that convergence. It just
shows up in the AE/CJ results because some of the source keywords led
the supplier search there.

The fix has three parts:

1. **Cross-reference discovered products against winner-source caches**
   (match by title/keyword, attach the evidence to the product)
2. **Add a `convergence_score`** counting how many independent
   winner-proof sources flagged the product
3. **Surface the new evidence in the Score Breakdown UI** with a
   "Winner Evidence" row showing which sources flagged the product

---

## The Five Orphan Caches

All populated in `ospra_os/intelligence/product_discovery.py`. None
are read by `_calculate_scores` (around line 3233).

| Cache attribute | Populated by | Shape | Source |
|---|---|---|---|
| `self._meta_winners_cache` | `_fetch_meta_ads_trends` (~line 1968) | `{niche, winners:[{page_name, max_days_active, variant_count, sample_landing_urls}], advertisers:[...], ad_count}` | Meta Ad Library |
| `self._amazon_movers_cache` | `_fetch_amazon_movers_rss` (~line 2083) | `{niche, category, items:[{title, asin, rank_delta, price, ...}]}` | Amazon Movers RSS |
| `self._amazon_new_releases_cache` | `_fetch_amazon_new_releases_rss` (~line 2144) | Same shape as movers (new_releases feed) | Amazon New Releases RSS |
| `self._etsy_trending_cache` | `_fetch_etsy_trending` (~line 2197) | `{niche, category, items:[{title, url, favorites, price, ...}]}` | Etsy Trending |
| `self._tiktok_engagement_cache` | `_fetch_tiktok_trends` (~line 1786) | **Already used** — read by `_merge_tiktok_engagement_into_products` | TikTok Apify |

The first 4 are dead. The last one (`_tiktok_engagement_cache`) is the
template for what we want to do — it's read by
`_merge_tiktok_engagement_into_products` (~line 1635) which fuzzy-
matches product titles and writes engagement metrics back onto each
product. **Mirror that pattern for the 4 orphan caches.**

---

## Proposed Implementation

### Step 1 — Mirror the TikTok engagement merge for each orphan cache

Add 4 new merge methods on `ProductDiscoveryEngine`:

```python
def _merge_meta_winners_into_products(self, products):
    """For each product, check if its title matches an advertiser's
    landing-page-derived product keywords in _meta_winners_cache.
    If yes, attach winner evidence to the product."""

def _merge_amazon_movers_into_products(self, products):
    """For each product, fuzzy-match title against
    _amazon_movers_cache items. If match, attach the rank_delta as
    evidence."""

def _merge_amazon_new_releases_into_products(self, products):
    """Same pattern as movers — match by title, attach the 'this is a
    new launch' flag."""

def _merge_etsy_trending_into_products(self, products):
    """Same pattern — match by title, attach Etsy favorites count
    as evidence."""
```

Each method writes to `product["winner_evidence"][source_name]` — a
new top-level key shaped like:

```python
product["winner_evidence"] = {
    "meta_ads": {"matched": True, "page_name": "Smart Home Co",
                 "days_active": 21, "variant_count": 4},
    "amazon_movers": {"matched": True, "rank_delta": 850, "asin": "..."},
    "amazon_new_releases": {"matched": False},
    "etsy_trending": {"matched": False},
}
```

Title matching: reuse the existing `_normalize_title` + token overlap
helpers in product_discovery.py. Don't introduce a new similarity lib.

### Step 2 — Compute `convergence_score`

Inside `_calculate_scores`, after the existing score computation:

```python
evidence = product.get("winner_evidence") or {}
matched_sources = sum(1 for v in evidence.values() if v.get("matched"))
# 0 = no signal, 1 = noise, 2 = signal, 3+ = strong winner
convergence_score = min(100, matched_sources * 30)
product["convergence_score"] = convergence_score
product["winner_source_count"] = matched_sources
```

### Step 3 — Reweight OI score to include convergence

In `_calculate_scores`, find where `oi_score` is computed (the weighted
average). Currently it's roughly:

```python
oi_score = (
    demand_score * 0.25 +
    trend_score * 0.20 +
    sentiment_score * 0.20 +
    viral_score * 0.15 +
    profit_score * 0.20
)
```

Reweight to include convergence. Suggested split:

```python
oi_score = (
    demand_score * 0.20 +
    trend_score * 0.15 +
    sentiment_score * 0.15 +
    viral_score * 0.10 +
    profit_score * 0.20 +
    convergence_score * 0.20  # NEW — money-backed signals
)
```

The convergence weight steals from trend/sentiment/viral (the
softer signals). Profit and demand stay strong.

Saturation multiplier still applies on top, but the
high-convergence products will mostly NOT be saturated (they're
proven AND early-stage by definition — that's the winning combo).

### Step 4 — Surface in the Score Breakdown UI

File: `frontend/src/components/ProductDiscovery.jsx`, around the
"Score Breakdown" panel inside `ProductDetailPanel` (search for
`Score Breakdown` in the file).

Add a new row labeled **"Winner Evidence"** showing:

```
Winner Evidence: 3/4 sources confirm
  ✓ Meta Ads — "Smart Home Co" running 21d × 4 variants
  ✓ Amazon Movers — jumped from #1,280 to #45 today (Δ 1,235)
  ✓ Etsy — 142 favorites in last 24h
  ✗ Amazon New Releases — not a new launch
```

The data is on `product.winner_evidence` from the backend. Render
each entry with a green check if `matched: true`, gray X otherwise.

For the OI score circle / total: surface `convergence_score` as its
own grade band so users see "this product was flagged by 3 of 4
winner-proof sources" at a glance.

### Step 5 — Cross-reference merge

Currently `_cross_reference_suppliers` (~line 2589) only merges AE+CJ
supplier products. Consider extending it to also match against the
4 cached source lists — but be careful: those sources are NOT
suppliers (you can't dropship from Etsy or buy from a Meta ad). The
goal is *boosting matching products*, not adding new product records.

The cleanest approach: keep `_cross_reference_suppliers` as-is and do
the merge in 4 new methods AFTER step 5 scoring. That way the cross-ref
step stays narrowly about suppliers, and the winner-evidence merge is a
clean separate phase.

---

## Files That Will Change

**Backend** (`ospra_os/intelligence/product_discovery.py`):
- Add 4 new `_merge_*_into_products` methods near the existing
  `_merge_tiktok_engagement_into_products` (line ~1635)
- Call them in `discover_products` right after the existing TikTok
  merge (around line 967), before `_calculate_scores`
- Modify `_calculate_scores` to compute `convergence_score` and
  reweight `oi_score`

**Frontend** (`frontend/src/components/ProductDiscovery.jsx`):
- Add "Winner Evidence" row to Score Breakdown panel in
  `ProductDetailPanel`
- Optionally add a "Winner Sources" badge on `ProductCard` for
  products with `winner_source_count >= 2`

**Tests** (`tests/`):
- Add a `test_winner_evidence_merge.py` covering the 4 merge methods
  with synthetic caches and synthetic products
- Update any existing `test_calculate_scores.py` for the new weights

---

## What Already Works (Don't Break It)

These 9 sources are fully wired and influence scoring TODAY. Don't
regress them while adding the new logic:

- AliExpress Affiliate API → cost, profit_score, cross-ref
- AliExpress DS API → real merchant cost (Task #24)
- CJ Dropshipping → supplier presence, cross-ref
- Google Trends → trend_score (+ rising-related as of today)
- TikTok Apify → viral_score via engagement merge
- TikTok Shop Partner API → trend_score (when configured)
- Amazon Bestsellers → trend_score via category presence
- Twitter/X → sentiment_score
- Amazon Reviews → sentiment_score qualitative

If `convergence_score` is too aggressive in weighting, the existing
sources lose influence and well-tested products could drop. Validate
with a real discovery run before merging.

---

## Suggested Validation Plan

1. After implementing, run `python -m pytest tests/test_full_discovery_pipeline.py tests/test_parallel_discovery.py tests/test_saturation_scorer.py` — should all still pass.
2. Run a discovery cycle on `smart_home` niche and inspect the top 5 products' `winner_evidence` dicts. Confirm at least 1 product has matches across 2+ sources.
3. Compare OI rankings before/after the change. The convergence-flagged products should rise; pure-AE-velocity products should drop. If a product with 0 winner evidence is still #1, something is off.
4. Open the Products page in the browser. Open the top product's detail panel. Verify the new "Winner Evidence" row renders correctly.

---

## Notes for Future Sessions

- **Don't refactor `_calculate_scores`** wholesale while doing this — it's 900 lines and a refactor compounds risk. Add the convergence component as a new term, leave the rest alone.
- **The TikTok engagement merge pattern is the gold standard** (lines ~1635-1683). Mirror it precisely for the 4 new merges.
- **Title matching is the hard part.** Reuse `_normalize_title` and the existing token-overlap logic. Don't introduce fuzzywuzzy / rapidfuzz unless really needed — token Jaccard is good enough.
- **If you hit context limits**, ship Steps 1+2 first (backend merge + convergence_score). UI surface (Step 4) can be a follow-up commit.
- **The user (founder, non-coder)** appreciates plain-English explanations of what's about to change BEFORE you make the change. They'll catch design issues you'll miss.
