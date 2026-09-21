# OPEN ISSUES

Findings that are verified but not yet fixed. Each entry states what is wrong,
how it was verified, and what it costs if left alone. Fixed items move to
`docs/HANDOFF_2026-08.md`.

---

## Anthropic API call-site review — 2026-09-21

Reviewed all **20 `messages.create()` call sites across 12 files**. Enumerated
with `grep -rn "Anthropic(\|messages\.create"`, then each file checked for
timeout config, retry config, `max_tokens`, and error handling.

SDK facts this review is measured against (verified against the installed
`anthropic==0.72.0`, not assumed):

```
default timeout     = Timeout(connect=5.0, read=600, write=600, pool=600)
default max_retries = 2
```

### ~~A1 — No timeout on 19 of 20 Anthropic calls~~ · **FIXED 2026-09-21** (`fad82ec`)

All 12 client constructions now pass `timeout=ANTHROPIC_TIMEOUT_SECONDS`
(default 60s). briefing_engine's sync-client-on-the-event-loop calls go through
`asyncio.to_thread`, and the briefing routes serve a cached copy + background
generation instead of generating inline. Three source-scan guard tests.
Original finding kept below for the record.

Only `ospra_os/ml/ai_client.py` sets a timeout. Every other call site inherits
the SDK default of a **600-second read timeout**, and because the SDK also
retries twice by default, one unresponsive call can occupy a worker for
**roughly 30 minutes** before raising.

| File | Calls | Path |
|---|---|---|
| `ospra_os/ai/providers/claude.py` | 6 | shared provider |
| `ospra_os/intelligence/briefing_engine.py` | 2 | **request path** (`intelligence_core_routes.py:94`) |
| `ospra_os/intelligence/competitive_learning.py` | 2 | background |
| `ospra_os/intelligence/trend_analyzer.py` | 2 | background |
| `ospra_os/ai/multi_provider_client.py` | 1 | shared |
| `ospra_os/integrations/meta/ad_generator.py` | 1 | ad copy |
| `ospra_os/integrations/shopify/deployment.py` | 1 | deploy path |
| `ospra_os/intelligence/ai_pricing_generator.py` | 1 | pricing |
| `ospra_os/intelligence/daily_brief.py` | 1 | scheduled |
| `ospra_os/services/product_content_generator.py` | 1 | content |

`briefing_engine` is the sharpest case: it is reached from an HTTP handler, so
a stalled Anthropic call holds a request open for up to 10 minutes.

**Fix:** set an explicit `timeout=` at client construction (a single value on
the `Anthropic(...)` client covers every call made through it). Pick per
workload — short for request paths, longer for batch.

*Note on retries: the SDK's default `max_retries=2` already applies everywhere,
so retry coverage is NOT missing. Timeout is the actual gap. Adding explicit
retry logic on top would compound, not help.*

### A2 — Nine distinct Claude model strings, hardcoded across 12 files · **MEDIUM**

```
22x claude-sonnet-4-5-20250929      2x claude-3-haiku-20240307
11x claude-sonnet (prefix/partial)  2x claude-3-5-sonnet-20241022
 6x claude-sonnet-4 (partial)       2x claude-3-5-haiku-20241022
 3x claude-haiku (partial)          1x claude-opus-4-20250514
 2x claude-opus (partial)
```

Three of these pin models from 2024 (`claude-3-haiku-20240307`,
`claude-3-5-sonnet-20241022`, `claude-3-5-haiku-20241022`). There is a
`ospra_os/ai/model_router.py` and `ospra_os/ai/providers/claude.py` that exist
to centralise this, but 10 of the 12 files construct their own
`Anthropic(...)` client and name a model inline, bypassing it.

**Why it matters for F1 specifically:** `ledger.MODEL_VERSION` stamps one model
string onto every snapshot. If different code paths grade with different
models, that stamp is a fiction, and calibration pools incomparable grades —
the exact failure the version columns exist to prevent.

**Fix:** route the remaining call sites through `ai/providers/claude.py` and
name models in one place.

### A3 — `except Exception` around AI calls in 11 of 12 files · **MEDIUM**

46 occurrences across these files (9 in `ai/providers/claude.py` alone). This
is CLAUDE.md trap #2: a renamed method, a changed response shape, or an
exhausted key becomes a log line while the feature reports success. Not fixed
here because narrowing them needs per-site judgement about intended fallback
behaviour — several are legitimate provider-fallback handlers.

**Fix:** narrow to the SDK's own exception types (`anthropic.APIError`,
`APITimeoutError`, `RateLimitError`) and let genuinely unexpected exceptions
propagate.

---

## Shipped since this file was created

- **F2 fit gate** (`91a0da5`) — G1-G8 coherence filter, evaluate-only
  (FIT_GATE_FILTER off), rejections snapshotted by F1 before any filtering.
- **F7 grading v2 factors** (`79c1132`) — recorded into every snapshot's
  factor_breakdown; weights behind GRADING_V2_ENABLED (off) per the spec's
  no-change-without-calibration rule.

## Pre-existing, carried forward

### ~~B1 — `ad_spend` is never written to `ProductPerformance`~~ · **FIXED 2026-09-21** (`5e0966a`)

`check_ad_performance` is now implemented: pulls live Meta spend per active
campaign, attributes it onto today's `ProductPerformance` row, and flags
ROAS < 2.0 with a `suggested_action` — it never pauses/scales/spends (a test
asserts this). The sales sync no longer seeds `"ad_spend": 0.0`; ownership is
split (sync owns sales/COGS/fees and preserves the row's ad_spend, the ad task
owns ad_spend), pinned by an ownership-guard test. Remaining scope: only Meta
has a metrics adapter — TikTok/Google campaigns return None (unreachable) and
keep their stored figures; wire adapters when those platforms carry real
campaigns.

### B2 — Migrations 009 and 012 are unguarded against the create_all race · **MEDIUM**

`tasks/catalog_warm.py` bootstraps tables with `Base.metadata.create_all` and
the Render cron runs independently of the API's
`preDeployCommand: alembic upgrade head`. 013 and 014 were made idempotent for
this reason; 009 and 012 have the same exposure and have simply been lucky on
timing. An unguarded `CREATE TABLE` losing the race fails the deploy.

### B3 — Two models share `__tablename__ = "product_performance"` · **MEDIUM**

`database/performance_models.py:39` (daily rollup, `product_id` is an Integer
FK) and `learning/summary_models.py:131` (lifetime rollup, `product_id` is
`String(100)`) declare the same table name with incompatible schemas. Whichever
imports last wins the SQLAlchemy registry. F1's aggregation reads the
`performance_models` one.

---

## Blocked — needs owner action

### C1 — `grade_snapshots` row counts cannot be read from this machine

The `.env` `DATABASE_URL` points at a Neon host that is **not production**: it
reports `alembic_version = 003` and has no `discovered_catalog`,
`product_timeseries`, or ledger tables. Production is at `014`.

To answer "total rows / distinct products / first + last timestamp", one of:
- the production `DATABASE_URL` (Render → `ospra-db` → External Connection String), or
- run this and paste the output:

```sql
SELECT count(*)                AS total_rows,
       count(DISTINCT product_key) AS distinct_products,
       min(ts)                 AS first_snapshot,
       max(ts)                 AS last_snapshot
FROM grade_snapshots;
```

The first timestamp is the validation-clock start for the file-03 launch gate.
