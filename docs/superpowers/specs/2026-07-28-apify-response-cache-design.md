# Apify response cache — design

**Date:** 2026-07-28
**Status:** approved, ready for implementation plan
**Author:** brainstormed with Claude (CLI session)

## Problem

Apify spend hit the $45/month hard cap on ~2026-07-20, three weeks into a cycle
ending 2026-08-07. Every actor start since then returns
`403 platform-feature-disabled: Monthly usage hard limit exceeded`. Consequences
observed in production logs:

- `trend_warm` warms 0 terms and exits 1 (red) — Apify is capped and the pytrends
  fallback is 429'd by Google from Render's datacenter IPs.
- Meta Ad Library and TikTok Shop signals are absent from every discovery run, so
  every product is graded `Confidence: low`.

Root cause of the burn rate: **no Apify response is persisted between runs.**
`catalog_warm` runs 5 niches × 5 Meta sub-queries × 2×/day ≈ 50 actor starts/day
(~1,500/month), but only ~25 *distinct* sub-queries exist. The same questions are
re-asked ~60 times a month. `google_trends_apify.py` has an in-process dict cache
with a 1-hour TTL, which is dead weight in a cron (the process exits with it);
`meta_ads_library.py` has no cache at all.

## Goals

1. Stop paying for identical Apify questions — cache responses across processes.
2. Survive an Apify outage with degraded rather than absent signal.
3. Make Apify cache behavior observable in the existing `[APIFY SPEND]` log line.

## Non-goals (explicitly out of scope)

- **Daily spend pacing / budget ceilings.** This design caps *waste*, not *spend*;
  a burst of genuinely novel queries can still exhaust the cap. Pacing is a
  separate change so each stays reviewable.
- Changing which actors run, sub-query counts, or discovery cadence.
- Replacing the term-level trend cache (`cached_google_trends`).

## Decisions taken during brainstorming

| Decision | Choice | Rationale |
|---|---|---|
| Cache layer | Generic, at `base_apify.run_actor` | Single choke point every actor call passes through; connectors need no changes; covers TikTok/Amazon if re-enabled |
| Meta TTL | 3 days | Advertiser activity rarely shifts meaningfully in 72h; cuts Meta from ~1,500 to ~250 runs/month |
| Quota-exhausted behavior | Serve stale, mark it | Keeps winner-proof signal through an outage; confidence scoring downgrades rather than blanks |
| Google Trends actor | **Bypass (TTL 0)** | `trend_warm` exists to fetch *fresh* trends; a response cache would feed it its own previous answer forever. Term-level caching already lives in `cached_google_trends`. |

## Design

### Components

```
ospra_os/database/apify_cache_models.py      # ApifyResponseCache model (mirrors trend_cache_models.py)
ospra_os/product_research/connectors/apify/response_cache.py   # key/get/put/ttl/prune
ospra_os/product_research/connectors/apify/base_apify.py       # run_actor integration (the only call-site change)
alembic/versions/20260728_1500_009_apify_response_cache.py     # schema
tests/test_apify_response_cache.py                             # unit tests
```

`response_cache.py` is the only module that knows about caching; `base_apify`
calls four functions and is otherwise untouched. Connectors are not modified
except for one line in `meta_ads_library.py` to propagate the stale marker.

### Cache key

SHA-256 hex of the canonical form of:

- `actor_id`
- `run_input` serialized as JSON with `sort_keys=True` (dict ordering must not
  produce two keys for one question)
- `max_items` (a 25-item call is not interchangeable with a 100-item call)

**Excluded from the key:** `timeout_secs`, `memory_mbytes` — provisioning knobs
that do not change the result and would fragment the cache.

### Schema — `apify_response_cache`

| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK | |
| `cache_key` | String(64), unique, indexed | SHA-256 hex |
| `actor_id` | String(128), indexed | per-actor TTL + spend reporting |
| `run_input_summary` | String(512) | truncated readable input; lets a human eyeball a row without decoding a hash |
| `items` | JSON | exactly what `run_actor` returned |
| `item_count` | Integer | denormalized, for cheap monitoring |
| `fetched_at` | DateTime, indexed | drives staleness |
| `hit_count` | Integer, default 0 | proves the cache earns its keep |
| `last_hit_at` | DateTime, nullable | |
| `created_at` | DateTime | |

### TTL policy

Config dict in `response_cache.py`, env-overridable:

| Actor | TTL | Env override |
|---|---|---|
| `curious_coder/facebook-ads-library-scraper` | 72h | `APIFY_CACHE_TTL_HOURS_META` |
| `apify/google-trends-scraper` (env `APIFY_GOOGLE_TRENDS_ACTOR`) | 0 = bypass | `APIFY_CACHE_TTL_HOURS_TRENDS` |
| default (all others) | 24h | `APIFY_CACHE_TTL_HOURS_DEFAULT` |
| empty result (`[]`), any actor | 6h | `APIFY_CACHE_TTL_HOURS_EMPTY` |

Empty results are cached so a genuinely dead keyword stops costing money, but at a
short TTL so a one-off actor hiccup does not blank it for days.

Kill switch: `APIFY_CACHE_ENABLED=false` disables reads and writes entirely.

### Data flow in `run_actor`

1. **Breaker check (existing).** `apify_actor_tripped(actor_id)` currently returns
   `[]`. It must now attempt a **stale-allowed** cache read first — this is
   precisely the outage case the stale path exists for.
2. **Fresh read.** Look up the key; if present and within TTL, increment
   `hit_count`/`last_hit_at`, log `[APIFY CACHE] hit`, return items. No HTTP.
3. **Live call.** Existing code path, unchanged.
4. **Write on success.** Upsert the response (see size guard below).
5. **Stale fallback on failure.** On quota/403/exception, re-read the key
   *ignoring age*. If anything exists, stamp and return it; else return `[]` as
   today.

### Stale marking

When serving an expired entry, each returned item is stamped (on a copy, never
mutating the cached list) with:

```python
item["_ospra_cache"] = {"stale": True, "fetched_at": "<iso8601>"}
```

Propagation, one step at a time:

- `meta_ads_library.search_active_ads` sets `stale: True` on its result dict when
  any item carries the marker.
- `product_discovery._fetch_meta_ads_trends` records it as
  `_meta_winners_cache['stale']`, and the scoring pass stamps
  `product['meta_niche_stale']` alongside the existing
  `meta_niche_advertiser_count`. (There is no `data_sources['meta_ads']` key in
  this codebase — the advertiser signal travels via `_meta_winners_cache`.)
- `_compute_saturation` (`product_discovery.py:317`) already derives confidence
  from how much signal weight it could fill: `meta_advertiser_density` contributes
  weight `0.25`. A **stale** Meta signal contributes at **half weight (0.125)** —
  the saturation score still uses it, and `confidence` lands between "fresh
  signal" and "no signal". This is the concrete meaning of "reduced, not absent":
  "40 advertisers as of Tuesday" instead of "no data".

### Error handling

Governing principle, same as `catalog_warm`'s credential check: **the cache must
never cause the outage it exists to prevent.** Every failure below logs a warning
and falls through to the live call:

- DB unreachable / table missing / corrupt JSON row → treat as a miss
- Write failure → return live items anyway
- Concurrency: two parallel sub-queries with the same key may both miss and both
  run. Accepted (rare, costs one duplicate run). Writes are upserts so the race
  cannot raise a unique-constraint error.
- Size guard: responses serializing above `APIFY_CACHE_MAX_BYTES` (default
  2,000,000) are not cached, so a pathological payload cannot bloat Postgres.
- Retention: rows older than `APIFY_CACHE_PRUNE_DAYS` (default 30) are deleted at
  the start of each `catalog_warm` run.

### Observability

`get_apify_budget_report()` gains `cache_hits`, `cache_misses`, `stale_served`, so
the existing `[APIFY SPEND]` line in `catalog_warm` shows the savings directly.

### Migration

Alembic migration 009 creates the table. The crons additionally `create_all` it in
their existing bootstrap so a cron can run before the web service has deployed
(same pattern as `discovered_catalog` / `product_timeseries`).

## Testing

`tests/test_apify_response_cache.py`, with HTTP mocked:

1. Hit inside TTL → zero HTTP calls, items returned from cache.
2. Miss past TTL → exactly one HTTP call, row refreshed.
3. `run_input` dicts with reordered keys → one cache row, not two.
4. Differing `max_items` → two rows, not one.
5. Quota 403 with an expired entry → stale items returned, `_ospra_cache` marker
   present, `stale_served` counted.
6. Tripped breaker with an expired entry → stale items returned (not `[]`).
7. DB failure on read → live call still happens, no exception escapes.
8. Empty result cached with the short TTL.
9. Response over the size guard is not written.
10. Google Trends actor never reads or writes the cache.
11. Meta connector propagates `stale: True` to its result dict.
12. `_compute_saturation` gives a stale Meta signal half weight (0.125), so its
    `confidence` sits strictly between the fresh-signal and no-signal cases.

Full suite (`uv run pytest`) must stay green; pre-existing unrelated failures
noted in CLAUDE.md remain acceptable.

## Verification in production

After deploy, one `catalog_warm` run should show:

- `[APIFY CACHE] hit` lines for repeated sub-queries
- `actor_starts` in the `[APIFY SPEND]` line falling from ~25/run toward ~0–5
- `cache_hits=` non-zero in the same line
- Products still carrying the Meta signal (`meta_niche_advertiser_count` > 0)

## Expected outcome

- Meta Ad Library: ~1,500 → ~250 actor runs/month (≈83% reduction).
- An Apify outage degrades grading (stale-marked signal) instead of blanking it.
- Budget headroom returns for TikTok Shop and Google Trends within the same $45.

## Risks

| Risk | Mitigation |
|---|---|
| A bad-but-200 actor response gets cached and served for 3 days | Short empty-TTL; `APIFY_CACHE_ENABLED=false` kill switch; rows are prunable by `actor_id` |
| Stale marker silently dropped by connector parsing | Test 11 asserts propagation |
| Postgres growth | Size guard + 30-day prune + `item_count` monitoring |
| Someone later "fixes" the trends bypass | TTL 0 is commented with the reason in config |
