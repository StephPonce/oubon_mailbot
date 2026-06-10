---
name: discovery-open-diagnostics
description: Google Trends 0-results + meta_ads winners not surfacing — both RESOLVED 2026-06-04 (commit d6233b5); one latent note on the slow Apify trends actor
metadata:
  type: project
---

Found 2026-06-03, **both RESOLVED 2026-06-04 (commit d6233b5)**:

1. **Google Trends returned 0 results — RESOLVED.** Root cause was NOT degenerate keywords (the original hunch) but three connector bugs: (a) the normalization edit set `timeframe='today 12-m'`, which the `apify/google-trends-scraper` actor 400-rejects (valid: today 1-m/3-m/5-y/all); (b) that actor takes ~12 min/run (a SUCCEEDED run measured 739s) vs the connector's 120s timeout, so every run was abandoned; (c) schema drift — the actor now returns `interestOverTime_timelineData` with nested `value:[N]` (+ flattened `relatedQueries_*`), but the parser read flat `interestOverTime`/`value`. Fix: **pytrends is now the primary inline trend source** (in-process, seconds, valid for `today 12-m`); the slow Apify actor is demoted to a fallback that only runs when pytrends is unconfigured. `_extract_keywords` now emits real phrases. Connector parser handles both schemas.

2. **meta_ads winners now survive into ranked output — RESOLVED.** Earlier 0 survived; after (a) the grok-4.3 X-sentiment migration started feeding `twitter_sentiment` and (b) per-winner Google Trends got wired into per-product scores, **12/12 meta_ads winners pass min_score** and ~7/10 of the ranked output is `winner_source=meta_ads`. Trend is wired via `TrendAnalyzer.get_trend_interest` (batches winner phrases) → `discover_products` stamps each product's `data_sources['google_trends']` by winner; google_trends went 0/10 → 10/10 populated with distinct per-winner values. `[winner_source]` + `[trend-wire]` log lines instrument this.

**Latent note:** if the Apify `apify/google-trends-scraper` is ever reinstated, it must move to a background Celery pre-warm + cache (1-hr TTL) — it cannot run inline at ~12 min/request. See [[xai-agent-tools-migration]] if that memory exists.
