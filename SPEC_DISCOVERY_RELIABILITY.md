# SPEC: Discovery Reliability — kill the "Discovery unavailable" failure class

**For:** CC (Claude Code CLI session) · **From:** Cowork session, 2026-07-15
**Approved by owner:** yes — including the structural job+poll piece.
**House rules apply:** verify-first against real data, one regression test per step, commit per step, plain-pip resolve check before push, report where this spec's assumptions were wrong.

---

## Why (verified facts, 2026-07-15)

1. **Prod catalog is 16 days stale.** `GET /api/discovery/catalog?niche=smart_home` on prod
   (`ospra-intelligence-api.onrender.com`, commit `8dcfdc2`) returns 87 products — every one
   discovered `2026-06-29`, `days_of_proof: 16`. The `ospra-catalog-warm` cron
   (`render.yaml:196`, schedule `0 1,13 * * *`) has not successfully written in ~2 weeks.
   ospra.io is selling June's "timing windows" as today's. For this product, stale IS down.

2. **Every prod catalog row carries**
   `qualitative_assessment.data_gaps: ["AI provider unconfigured — set XAI_API_KEY or ANTHROPIC_API_KEY"]`.
   `render.yaml` declares those keys for the cron service with `sync: false` — meaning they must
   be manually entered in the Render dashboard **per service**. The web service has them; the
   cron evidently does not. (Third wrong/missing-env incident: Apify token, xAI key, now this.)

3. **The cold path is a synchronous 45–95s HTTP request.** Measured: 44.3s and 48.0s in the
   June 29 warm rows; 93.6s on the July 14 manual probe. Server budget is 120s
   (`middleware/timeout_middleware.py` path override `("/api/discovery/quick", 120)`), and
   Render's proxy has its own request timeout in the ~100s zone (CONFIRM the current documented
   value; do not trust this number). Any kill along that chain surfaces in the browser as a
   status-0 network error → `ProductDiscovery.jsx:3516` "Discovery unavailable / Load failed."

4. **Refresh-spam stacks live discovery runs.** The client dedupes in-flight requests per page
   load only (`api.js` `_inflightDiscovery`); a page refresh clears it. Each refresh on an
   empty-catalog niche fires a fresh 45–95s discovery run server-side, burning paid API calls
   (AliExpress, Meta, Apify) concurrently. Cost guard needed, not just UX.

5. **Prod users see dev error copy.** `api.js:453` hint: "Check that uvicorn is running on the
   configured port." — shown verbatim on ospra.io.

**Key files:**
- Routes: `ospra_os/intelligence/unified_discovery_routes.py` — `/quick/{niche}` @308, `/catalog` @652
- Frontend: `frontend/src/components/ProductDiscovery.jsx` @2957–2993 (catalog-first, falls through to on-demand), `frontend/src/services/api.js` @367 (`discoverProducts`, no AbortController), @449–455 (error copy)
- Warm: `ospra_os/tasks/catalog_warm.py` → upserts `discovered_catalog` (`ospra_os/database/discovered_catalog.py`)
- Timeouts: `ospra_os/middleware/timeout_middleware.py`

---

## Step 0 — Diagnose the dead cron (evidence before code)

Read the `ospra-catalog-warm` run history/logs in Render (owner will open dashboard access if
needed). Ranked hypotheses — confirm, don't assume:
  a. **Apify credits capped ~Jun 29** → discovery inside the warm run fails/returns nothing.
  b. Missing env in the cron service (AI keys proven missing; others may be too).
  c. Warm run crashes on one niche and aborts the whole batch.

Whatever the cause: make `catalog_warm.py` **per-niche fault-isolated** — wrap each niche in
try/except, log and continue, exit non-zero only if ALL niches fail. One bad niche or one
capped API must never zero out the whole refresh again.
**Test:** fixture where niche 2 of 3 raises → niches 1 and 3 still upsert.

## Step 1 — Stop lying about freshness (small, non-structural)

- `/catalog` response: add `catalog_freshness` meta = newest write timestamp for the niche
  (derive from existing columns; if upserts don't touch a timestamp on re-seen products, add
  `last_seen_at` — that gap is itself a bug worth confirming).
- Frontend: render "Data from {date}" on the products page; if freshness > 48h, show a stale
  banner instead of presenting June as now.
**Test:** catalog response includes freshness; stale fixture triggers banner logic (unit-level
on the formatter is fine).

## Step 2 — Job + poll for on-demand discovery (structural, approved)

New table `discovery_jobs` (alembic migration 007 — mandatory-migration pipeline already
enforces this): `id, niche, count, status ∈ {queued, running, done, error}, error_text,
created_at, started_at, finished_at, result_count, requested_by`.

- `POST /api/discovery/jobs {niche, count}` → **one live job per niche globally**: if a
  queued/running job exists for that niche, return it (200, idempotent) instead of creating
  another. This is the refresh-spam cost guard.
- Runner: FastAPI `BackgroundTasks` in-process — do NOT add a Celery worker service; there is
  no worker in `render.yaml` and we are not adding infra. The job calls the SAME discovery
  entrypoint `/quick` uses and **upserts results into `discovered_catalog`** — the catalog
  stays the single source of truth; no second results store, no new page, no new tab.
- `GET /api/discovery/jobs/{id}` → status. Orphan recovery: if `running` and
  `started_at > 10min` ago (deploy restart killed it), report `error` — the GET handler does
  this lazily; no reaper process.
- Keep `/quick/{niche}` alive for scripts/back-compat. The UI stops using it on the cold path.
**Tests (fail-if-reverted):** (1) same-niche POST while running returns the existing job, does
NOT start a second run; (2) orphaned running job reports error via GET; (3) job completion
upserts into `discovered_catalog` (fixture discovery fn).

## Step 3 — Frontend wiring

`ProductDiscovery.jsx` cold path (@2984–2993): replace the 90s `await discoverProducts` with
POST job → progress state ("Running live discovery — usually 60–90s") → poll `GET /jobs/{id}`
every 3s (cap ~3min) → on `done`, re-fetch `/catalog` and render. On `error`, honest message +
retry button that POSTs a new job. Add AbortController (25s) to the `/catalog` fetch itself.

## Step 4 — Error copy

`api.js:453`: branch on `import.meta.env.PROD` — prod copy: "Discovery is taking longer than
expected or the connection dropped. Retry in a moment." Keep the uvicorn hint for dev only.

---

## Do NOT
- Do not create a new discovery pipeline, page, tab, or results store (Section G disease —
  extend `unified_discovery_routes.py` + `ProductDiscovery.jsx` only).
- Do not add a Celery/worker service or Redis dependency for this.
- Do not touch `email_automation/`, tenancy, or the moat modules.
- Do not remove or bypass `TimeoutMiddleware`; the job pattern makes its budget irrelevant on
  the cold path.

## Owner items (Steph, not CC — blocking Step 0 diagnosis if skipped)
1. Render dashboard → `ospra-catalog-warm` → Events/Logs since June 29 (screenshot or paste to CC).
2. Render dashboard → `ospra-catalog-warm` → Environment → add `XAI_API_KEY` (and/or
   `ANTHROPIC_API_KEY`) with the same values as the web service.
3. Confirm which Apify account/plan prod's `APIFY_API_TOKEN` belongs to (MCP shows FREE tier;
   notes say $45 STARTER capped to Aug 7 — reconcile before budgeting).

## Report back
Per house style: what each step found, where this spec was wrong (especially the cron
root-cause ranking and the Render proxy timeout figure), test counts, and the prod
verification: products page loads on a cold niche without the failure banner, and the
catalog freshness date on ospra.io is current.

---
---

# ADDENDUM — 2026-07-15 (owner pulled cron logs; root cause SOLVED)

Step 0's diagnosis is done — skip the log spelunking. Tonight's `catalog_warm` run
(23:05 UTC) discovered **0 products across all 5 niches** and exited status 2. The logs
show THREE independent dead credential systems in the **cron service env**, plus the
Apify cap:

1. **Apify: hard-capped.** `403 {"type": "platform-feature-disabled", "message":
   "Monthly usage hard limit exceeded"}` on every `curious_coder/facebook-ads-library-scraper`
   start. The breaker tripped correctly after 2 failures. Kills all meta_ads winners.
   Owner confirmed: credits exhausted.
2. **CJ Dropshipping: 401 on every call**, `token refresh unavailable/failed`. The
   `CJ_ACCESS_TOKEN` in the cron env is dead AND the refresh path can't re-auth
   (check whether `CJ_EMAIL`/`CJ_API_KEY` are actually set in the cron service).
3. **AliExpress: two failures.** (a) `ALIEXPRESS_TRACKING_ID not set` in the cron env —
   the affiliate API (**the source that built the entire June 29 catalog**,
   `price_source: aliexpress_affiliate_api`) returns 0 without it. (b) DS API
   `IllegalAccessToken`, `no refresh_token stored — re-authorize at
   /api/aliexpress/auth/start to seed one`; cron runs on a stale env token.
4. Minor: `JWT_SECRET_KEY` unset in cron (insecure-default RuntimeWarning).

**What worked (validated by this failure):** per-source graceful degradation, the Apify
breaker, and the absence-snapshot guard ("source outage, not product disappearance" —
no fake timeseries rows), and the non-zero exit. The engine refused to fabricate. The
catalog is stale because the warm's inputs starved on June 29, not because anything is
wrong with discovery logic.

**Consequences for the steps above:**
- Step 0's code change (per-niche fault isolation) is still wanted, but the primary fix
  is env repair (owner checklist below). Once AliExpress affiliate creds work in the
  cron, the catalog refreshes WITHOUT Apify — google_trends (pytrends fallback) is
  alive, meta winners simply absent → lower coverage, honestly reported. Fresh beats full.
- Original owner-item #2 (add XAI key) is superseded: the June 29 `data_gaps` note
  predates the key add — treat as a fossil unless the next GREEN warm run reproduces it.
- Steps 1–4 (freshness meta, jobs+poll, frontend wiring, error copy) unchanged.

## NEW Step 5 — Signal display contract (the "frontend doesn't match backend" bug)

Owner decision (D15, recorded in `memory/decisions.md`): **X/Twitter is retired as a
sentiment source** — X rarely carries product talk. Backend already reflects this:
`DISCOVERY_DISABLE_X` unset ⇒ disabled (`product_discovery.py:976-983`, tonight's log:
`x_twitter: [DISABLED] off by default`). The frontend does NOT reflect it:
`ProductDiscovery.jsx` still maps `twitter_evidence` (@225) and renders the Twitter leg
of `SocialEvidencePanel` (@699-790), so users see a dead X metric.

Contract: the products UI renders ONLY signals the backend actually queried for that
row — drive it from `data_coverage.by_source` (`"real"`/`"empty"` ⇒ render;
`"n/a"` ⇒ collapse into a single "not queried: …" line, never a zeroed metric card).
X-specific UI renders only when a row actually carries X data (old rows, back-compat).
Do the same for any other permanently-disabled source. No new components — modify
`SocialEvidencePanel` and the score-breakdown display in place.
**Test (fail-if-reverted):** a product whose `by_source.twitter == "n/a"` renders no
Twitter metric; one with real twitter_evidence still does.

## Owner checklist (CORRECTED 2026-07-15 late — owner screenshots showed ALIEXPRESS_TRACKING_ID exists on NEITHER service; earlier "copy from web" sourcing was wrong)
1. `CJ_API_KEY` — from the CJ dashboard (API settings). Add to cron; check web too.
   This is the var whose absence disarms the 401 self-healer (`client.py`
   `_refresh_access_token` returns False without `cj_email and cj_api_key`). CJ tokens
   expire ~15 days BY DESIGN; with this var set, expiry self-heals and stops mattering.
   The stale `CJ_ACCESS_TOKEN` can stay — refresh replaces it in-memory + on-disk cache.
2. `ALIEXPRESS_TRACKING_ID` — from the AliExpress AFFILIATE PORTAL (often literally
   `default`). Create on BOTH services; it exists on neither.
3. `JWT_SECRET_KEY` — copy from web if present there; otherwise generate once, set on both.
4. Visit `/api/aliexpress/auth/start` once (seeds the DB refresh token; ds_client
   prefers DB token thereafter — AE OAuth expiry self-heals for both services).
5. Apify Console → Billing/Limits: the 403 is a **hard limit**. Raise it (overage
   billing resumes actors immediately) or wait for the Aug 7 reset / upgrade. Until
   then the system runs Apify-less: no meta winners, no TikTok velocity, no comment
   linkage — AE + trends + grading still function.
6. Then trigger the cron manually and confirm `catalog_warm complete: N discovered`, N > 0.

## NEW Step 6 — Credential health: expiry must be LOUD (root-cause prevention)

Why: prod tokens died on schedule (CJ ~15-day TTL; AE OAuth `expires_in`) and nobody
knew for ~2 weeks because nothing monitors credential state. Both self-healers exist
but were disarmed (CJ: `CJ_API_KEY` missing → `client.py:184` returns False; AE: env
token has no refresh_token → `ds_client.py:130-135`, OAuth flow never completed, DB
table empty).

Build: a `credential_health()` check invoked (a) at catalog_warm start, (b) exposed in
`/health` payload. Reports per credential: present? healer ARMED? (CJ: email+api_key
set; AE: DB refresh_token row exists), and days-to-expiry where knowable
(`aliexpress_tokens.expires_at`). Cron logs a single ALERT line and exits non-zero if
a load-bearing healer is disarmed — fail at 14 days-to-death, not 14 days after.
Extend the existing sources-status printout; do not build a new monitoring subsystem.
**Test (fail-if-reverted):** disarmed CJ healer (no api_key) → health reports
`cj: {present: true, healer_armed: false}`; armed → `healer_armed: true`. AE with no
DB row → `refresh_seeded: false`.

Policy line for CLAUDE.md (CC add it): **env-pasted tokens are bootstrap-only; every
credential must have an armed refresh path or a loud expiry alert. A static secret is
a scheduled outage.**

## OPEN CONTRADICTION for CC to resolve (do this in Step 0)
June 29's catalog rows are `price_source: aliexpress_affiliate_api` with generated
affiliate links — yet `ALIEXPRESS_TRACKING_ID` is set on NEITHER Render service, and
the code passes `os.getenv('ALIEXPRESS_TRACKING_ID', '')` as mandatory at three call
sites (`integrations/aliexpress/client.py:52,163,212`;
`product_research/connectors/suppliers/aliexpress.py:310,544`;
`api/aliexpress_product_routes.py:338`). Either AE tolerates an empty tracking_id on
`affiliate.product.query` (and the "mandatory → 0 products" warning overstates), or the
working value comes from a path not yet found (DB token store? second client?). The
raw-response logging added in `aac9464` (2026-06-27) prints AE's actual answer — the
first warm run after the env fixes settles this empirically. Report which it was; if
tracking_id turns out NOT to be the AE blocker, say so plainly and identify what was.
