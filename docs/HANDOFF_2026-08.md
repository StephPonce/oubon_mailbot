# Handoff — August 2026 audit sweep

Written at the end of a long session so nothing is lost. Everything below is
either **DONE** (shipped + deployed + verified) or **OPEN** with enough detail to
execute without re-investigating.

**Governing lesson of the whole sweep:** this codebase fails *silently*. Broad
`except Exception` handlers turn renames, wrong shapes, and missing modules into
log lines, so features report success while doing nothing. ~13 features were
found silently disabled. **Verify end-to-end against production, not at the unit
level** — twice this session the unit tests passed while production did the
wrong thing.

---

## 1. SECURITY

### DONE

| ID | Fix | Commit |
|---|---|---|
| — | Deleted `POST /api/learning/simulate-sale`. Unauthenticated; wrote `event_type="sale"` (the ORGANIC tuple), so anyone could inject fake sales the G4 learning aggregations counted as real revenue. Re-opened the door migration 008 closed. | `be6e002` |
| C5 | Gmail `/messages`, `/stats`, `/status` now require auth. Probed live: returned **500 not 401** — request passed auth (there was none) and failed only because the token file is absent from the container. | `0797f3e` |
| C2 | Shopify OAuth now stores credentials via `Store.set_credentials()`. Both branches assigned `.credentials` directly, writing `access_token` + `webhook_secret` **in plaintext**. **⚠️ EXISTING ROWS STILL NEED A BACKFILL.** | `0797f3e` |
| C4 | Shopify OAuth callback: HMAC now mandatory (was `if hmac:` — omit the param, skip the check); shop **label** validated with `.isalnum()` (an `endswith(".myshopify.com")` check is NOT sufficient — `attacker.com?z=.myshopify.com` passes it and receives `client_secret`); state now bound to shop. | `0797f3e` |
| C1 | Auth on routes that delete products and spend money. | `9945060` |
| C1 (complete) | **ZERO unauthenticated state-changing routes.** 92 → 0 across four batches. Protected 367 → 518. | `65ca7cc`, `c886039`, `0e468b7`, `710c5f0` |
| — | **Ratchet test**: `tests/test_route_auth_ratchet.py` fails the build if a new ungated write route appears, and also if the baseline lists a route that is already fixed (so the count cannot rot). Baseline now EMPTY. | `69b1b27` |

**Auditor accuracy — two false-positive classes were found by verifying before
acting, and both mattered.** (1) Factory gates like `Depends(require_admin)` and
`require_tier("soar")` produce inner functions with unpredictable names; the
auditor now also treats a declared HTTP security scheme as proof of auth.
(2) `Depends(get_tenant)` IS auth — `tenancy/dependencies.py` converts a missing
tenant into a proper 401. The originally-reported 92 included ~39 already-safe
routes. **Always spot-check the tool before acting on its output.**

**This codebase gates routes FOUR different ways** — `get_current_user`, factory
gates (`require_admin`/`require_tier`), security schemes, and tenant
dependencies. Any audit assuming one convention lies in both directions.

**Deliberately public (allowlisted in `scripts/audit_route_auth.py`, not debt):**
provider-called webhooks (LemonSqueezy HMAC, Google Pub/Sub, WooCommerce OAuth
callback), `/auth/token` + `/auth/register` compat aliases (these need RATE
LIMITING, not auth — see O8), and `/api/abtesting/events/*` (storefront visitors
are anonymous by definition; gating them would break the measurement).

**C1 detail — read this before touching auth again.** Two layers existed and
**fixing `main.py` alone did nothing**: `ospra_os/integrations/shopify/routes.py`
is registered at `main.py:1854`, *before* the legacy `@app` duplicates are
defined, so it **shadows** them. After patching `main.py`, probing
`DELETE /api/shopify/products/123` still executed the handler and printed
"Deleting product 123". The router now has a router-level dependency.

**Verification technique that made this findable:** `GET` against a POST-only
route returns **405 if the route exists and no auth gate ran before routing**;
**401** if protected. Use this — it verifies auth without triggering paid work.

### OPEN — ranked

**O1. ~~Cross-tenant customer PII~~ — DONE (`ebeec4f`).** Migration 010 adds
`email_metrics.user_id`; the writer stamps it; `/emails/recent` filters to the
caller. Pre-010 rows are UNOWNED and served to nobody. 3 tests.
*Still open in this family:* `FulfillmentRecord`, `DiscoveryJob`,
`ProductEnhancedImages` and `ProductHistoryDB` have the same missing-owner
defect — same fix shape (column + migration + filter).

<details><summary>original finding</summary>

**O1. Cross-tenant customer PII, unauthenticated.** `ospra_os/email_automation/analytics_routes.py:57`
`GET /api/emails/recent` — no auth, no tenant filter, returns `customer_email` +
`subject`. **Live: 200.** Also `/api/dashboard/emails` (`:19`) and
`/api/emails/stats/weekly` (200, 1401 bytes of real data). Same file/router.
Also `ospra_os/services/notification_routes.py:40` `/api/notifications/recent`
(200, all tenants' `customer_email`/`customer_name`) and `:115`
`POST /api/notifications/send` — an **anonymous outbound-mail relay to any
address** (spam/phishing on your sender reputation).
*Structural root cause:* `EmailMetric` (`ospra_os/analytics/email_analytics.py:13-38`)
has **no `user_id`/`tenant_id`/`store_id` column at all** — it cannot be scoped
without a migration. Same defect in `FulfillmentRecord`
(`database/fulfillment_models.py:18`, holds `shipping_address`), `DiscoveryJob`,
`ProductEnhancedImages`, and `ProductHistoryDB` (`database/product_history.py:16-20`
— shared SQLite whose `orders` table holds `customer_email`, `customer_name`,
`tracking_number` with no owner column).
*Fix:* gate both routers behind auth **today**; then migrations adding `user_id`
+ backfill, then filter.
</details>

**O2. `/api/learning/*` — router-level auth DONE (`65ca7cc`).** Handlers still
take `user_id` from the URL, so an authenticated tenant can still read another
tenant's weights — derive it from the token to finish this.

<details><summary>original finding</summary>

**O2. `/api/learning/*` — zero auth, user_id from the URL.**
`ospra_os/learning/learning_routes.py` contains **no `Depends()` anywhere**.
- `GET /personal/{user_id}` (`:97`) — any tenant's model weights, best niches, price ranges
- `GET /events` (`:698`) — live **200**, all tenants' learning events
- `POST /custom-weights` (`:335`), `/personal/learn` (`:120`), `/feedback` (`:142`), `/record-ad-metrics` (`:370`) — **anonymous writes into any user's AI scoring model**
*Fix:* router-level `dependencies=[Depends(get_current_user)]`; derive `user_id`
from the token and **delete every `user_id` path/query/body parameter**.
</details>

**O3. ~~AliExpress OAuth token planting~~ — DONE (`63c4049`).** Both callbacks now
verify the HMAC state (600s TTL). Did NOT repoint `redirect_uri`: it must match
the AliExpress console registration, and a mismatch breaks the flow outright.
10 tests incl. replay rejection.

<details><summary>original finding</summary>

**O3. AliExpress OAuth token planting.** `ospra_os/api/aliexpress_oauth.py:122`
and `ospra_os/api/aliexpress_affiliate_oauth.py:95` both accept `state` and
**never read it**; both write the deployment-wide platform token. An attacker
feeds their own `code` and every tenant's sourcing runs through their account.
*The hardened implementation already exists* at `ospra_os/aliexpress/routes.py:287`
(HMAC state minted `:205`, verified unconditionally `:324`, TTL 600s) but is
unreachable because `routes.py:151-166` points `redirect_uri` at the unprotected
callback. *Fix:* repoint `redirect_uri`, or port `_verify_oauth_state` into both.
</details>

**O4. Email-OAuth cross-tenant attach.** `ospra_os/email_automation/oauth/routes.py:263`
— state is an unsigned `f"{user_id}:{state}"` (`:130`), split at `:284`.
`?state=7:anything` attaches the attacker's mailbox to user 7. Explicit TODO at
`:128`. *Fix:* use the existing DB-backed `put_state`/`pop_state` in
`ospra_os/security/oauth_state.py` (sound, atomic, replay-safe — already used
correctly by the WooCommerce callback, which is the reference implementation:
`ospra_os/api/woocommerce_routes.py:266`).

**O5. ~~TWO functions named `get_current_user`~~ — DONE (`5eb2d2d`).** The package
now re-exports the STRICT one; the permissive one is `get_current_user_optional`.
This exposed and fixed a real hole: `POST /api/discovery/jobs` was anonymous.

<details><summary>original finding</summary>

**O5. TWO functions named `get_current_user`.** `auth/jwt_auth.py:438` raises
401; `auth/dependencies.py:72` **returns `None` and never rejects**.
`ospra_os/auth/__init__.py:72` re-exports the **permissive** one. Anything doing
`from ospra_os.auth import get_current_user` looks protected and is not — this is
why `POST /api/discovery/jobs` and `GET /api/discovery/quick/{niche}` are
effectively public (`unified_discovery_routes.py:40`).
*Fix:* rename the optional one to `get_current_user_optional`; re-export the strict one.
</details>

**O6. Two env vars, two HIGH findings.**
- `ENVIRONMENT=production` — measured live: `x-ratelimit-limit: 500/minute` is the
  DEBUG value (`security/rate_limiting.py:242`), so limits run ~17× looser than
  intended. Two production detectors disagree: `rate_limiting.py:223-226` checks
  only `ENVIRONMENT`, while `core/env_validator.py:244-256` also accepts `RENDER`.
  Make rate limiting call the shared `is_production()`.
- `REDIS_URL` — confirmed unset (`/health/celery` → connection refused). JWT
  logout doesn't revoke across instances; the rate limiter is per-process, so
  real throughput is `limit × instances × workers`.
- Also: `CREDENTIALS_ENCRYPTION_KEY` is **undeclared in `render.yaml`** entirely,
  and `JWT_SECRET_KEY` is only on the web service while both crons set
  `ENVIRONMENT=production` → `auth/jwt_auth.py:55` raises at import → those
  workers may crash-loop.

**O7. Tier enforcement fails open and guards a nonexistent route.**
`middleware/tier_enforcement.py:125-128` allows anonymous through;
`PROTECTED_ENDPOINTS` lists `/api/products/discover`, a string that **appears
nowhere else in the repo**. Also `RequireTenantMiddleware`
(`tenancy/middleware.py:138-168`) is defined, exported, and **never registered**.

**O8. Auth endpoints outside the rate limiter.** `custom_rate_limiter.py:258-266`
skips all `/api/auth/`. `GET /api/auth/check-email` (`auth_routes.py:408-420`) is
an unthrottled account-enumeration oracle (live 200). Worse,
`api/frontend_compat_routes.py:68,97` expose `POST /auth/token` and `/auth/register`
aliases that **omit** the `check_sensitive_rate_limit` calls the real handlers make.

**O9. Remaining discovery cost-amplification, unauthenticated:**
`POST /api/discovery/cache/warm` (`:1658`), **`DELETE /api/discovery/cache/clear`
(`:1725`** — the force multiplier: clear cache, every later request is a cold
paid fan-out), `POST /api/discovery/refresh-cj-categories` (`:1592`), and 7
`/test-*` probes each burning a live paid supplier call. Also
`GET /api/discovery/catalog` → 200, **547 KB of your product-intelligence catalog**
to anyone with curl (documented as intentional; it is your core IP).

**O10. Medium:** `ospra.io` has almost no security headers (only `nosniff`;
missing HSTS/CSP/X-Frame-Options → clickjacking; the API by contrast is
excellent). `"unlimited"` in `rate_limiting.py:276,281` will crash `_parse_limit`
(`:48`) → every Stratosphere user gets a 500 on `/api/discovery/*`; use
`"1000000/hour"`. Dashboard-v2 is cross-tenant among *logged-in* users
(`dashboard/routes.py:598,541,122` over the ownerless shared SQLite). Open
redirect `api/subscription_routes.py:683` (`//evil.com` passes `startswith("/")`).
`/health` discloses `days_to_expiry` for the AliExpress token — tells an attacker
exactly when to strike.

**Low:** `webhooks/dlq.py:175-179` `importlib` on a DB-sourced value (RCE the
moment a request can write that column); `services/image_storage.py:190-193`
unsanitized `product_id` in a path join (one `Path(product_id).name` closes it);
`tiktok/routes.py:262-284` unbounded in-memory upload;
`advertising/google/google_ads.py:233,265` f-string into GAQL (not
request-reachable).

### VERIFIED CLEAN — do not regress
No SQL injection (322 call sites checked, all parameterized). No
`os.system`/`Popen`/`shell=True`/`eval`/`exec`/`pickle`; `yaml` never imported.
No secrets in git; `.env` gitignored. Fernet encryption is real and **fails
closed** in production. CORS genuinely restrictive (verified live against
spoofed origins). API security headers strong. `/docs`, `/redoc`,
`/openapi.json` all 404 in production. Webhook HMAC correct across 31 routes and
fails closed when no secret is set. No source maps in production.

### NOT YET AUDITED
A literal line-by-line pass of every file was **not** completed. Thinner
coverage: `ospra_os/api/[j-z]*` low-traffic route files; authenticated
cross-tenant behaviour (needs two real accounts — requires writes); Postgres-layer
RLS; CVE confirmation against installed versions (heavy dependency drift exists:
`anthropic` 0.72→0.121, `openai` 1.99→2.53, `fastapi` 0.128→0.141,
`cryptography` 46→50). Note the project carries **both** `python-jose` and
`PyJWT`, used inconsistently (`middleware/tier_enforcement.py:19` and
`auth/jwt_handler.py:28` use jose) — consolidate on PyJWT.

---

## 2. MOCK / FABRICATED DATA — COMPLETE (all 20 sites + 3 the audit missed)

Every production fabrication site is removed. Commits: `be6e002` (simulate-sale),
`f1d6426` (demo products, dead components), `ae3252a` (frontend cards),
`6407829` (spend caps, revenue charts, domain status, inventory), `6d76226`
(AI prompt inputs), `c17f41b` (last dead functions), `1710eb6` (random pricing).

**A systematic sweep beat the audit list.** Grepping `random.uniform|randint|
choice` across `ospra_os/` found 3 sites the list missed — including
`ai_pricing_generator._rule_based_pricing`, whose random price is written to a
LIVE Shopify listing. Sweep by pattern, don't trust an inventory.

Two method failures worth not repeating: cutting a function by "next def at the
same indent" broke the tree twice — once overrunning the end of a class (took
`get_engine`/`discover_products` with it), once stopping inside a multi-line
signature. Use explicit start/end line numbers. And `git stash` to compare
against HEAD collided with the parked "Gemini damage" stash; use
`git show HEAD:<path>` instead (already in project memory).

Deliberately kept: `static/tiktok_demo.html` (labelled a demo, obvious
placeholder image), `ai_product_analyzer.test_analyzer()` fixtures (demo
harness), `tests/` doubles, and documented heuristics like
`market_share_estimator`'s stated assumptions.

### Historical detail (original inventory)


**No test references ANY of these** — the whole purge is test-safe.

**Removed:** `simulate-sale` (see security above).

**Highest priority remaining:**
1. **`frontend/src/components/ProductDiscovery.jsx` `normalizeProduct`** — every
   product card, always. `:105` score `|| 50`; `:151-152` profit margin `: 50`
   then `×1.5` ⇒ **every product shows "Profit Margin 90"** on a full green bar
   with `estimated: false` hardcoded at `:1812`; `:66-74` `suggestedPrice = cost × 2.5`;
   `:190` invents `source: 'aliexpress'`; `:189` invents a "trending" tag.
   **The backend already stopped doing this deliberately** (`product_discovery.py:6552`);
   the frontend reintroduces it. Fix: propagate `null` — the honest "No data"
   striped bar already exists at `:1800`/`:1813`.
2. **`AutopilotControl.jsx:243,251,259,267`** — on API failure shows invented
   spend caps (85 / 10 / $100 / $50) as if they were the user's live limits, with
   no error banner. Most dangerous class: a user could act on it.
3. **`whitelabel/service.py:288-311`** — reports `cname_verified/txt_verified/ssl
   active` **without checking**, and commits it.
4. **`ospra_os/inventory/routes.py:28-55`** — the whole router is 5 hardcoded
   products + `random.uniform` sales history; 10 endpoints, incl.
   `POST /alerts/send-test` (emails fabricated alerts) and `/history/snapshot`
   (**persists** the fabrication). Real path exists in the same file:
   `shopify_sync.sync_all_products()` (`:559-660`).
5. **`analytics/analytics_engine.py`** — `:416-431` random revenue chart;
   `:112` hardcoded +25% growth; `:243` flat +10%; `/export` writes it to CSV.
6. **`marketing-site/index.html:585-631`** — three invented testimonials with
   names and quoted results, plus a pulsing "Live" badge on fake activity
   (`:136-215`). FTC endorsement exposure, not just hygiene.
7. Fabrication reaching the AI layer: `ai_product_analyzer.py:454` invents a
   4.0-star rating, `:475-476` a $35 AOV / 2% conversion for unknown stores;
   `api/product_analysis_routes.py:582-585` writes score defaults of 50 into the
   Claude prompt as measurements (and `:102-105` into the cache key, so unknown
   products collide). Prompt already does this right for `sales_count`/`rating`
   (`'Unknown'` at `:586-587`) — extend that.
8. **`ai_pricing_generator.py:185-187`** — `random.uniform` price **written to
   live Shopify listings**. T59 already nulled `rating`/`orders` here for exactly
   this reason; finish the job for `cost`/`price`.
9. `smart_recommendations.py:266-287` returns literally `"Product {i} in {niche}"`.
10. `_get_demo_products` (`product_discovery.py:7451-7550`) — env-gated OFF and
    well-defended; still delete it, along with `tiktok_client.py:398` random
    price and `_get_fallback_videos` (`:230-266`, dead).

**Convention to copy:** the absence-row pattern in `tasks/catalog_warm.py:293-313`
— records "not seen today" as a datum and *skips* writing when discovery returns
zero, so an outage isn't recorded as "everything vanished".

---

## 3. REDDIT / X REMOVAL — requested, NOT started

Owner decision: remove Reddit and X as sentiment sources entirely; keep Amazon,
Google Trends, TikTok, Shopify. X was already retired by decision D15 — do not
resurrect. Touches 20+ files: `sentiment_composite.py`, `product_discovery.py`,
`connectors/social/reddit.py`, `connectors/social/xai_twitter.py`,
`database/product_models.py`, `learning/`, `admin/routes.py`, frontend.

**Owner's call still needed:** code removal is reversible; **dropping the DB
columns holding historical Reddit/Twitter values is a migration and is not**.
Recommend: remove code paths now, leave columns until explicitly approved.

Note Reddit was never actually working: the connector claims `is_available()`
unconditionally and hits the unauthenticated JSON endpoint, which returns **403**
from every tested variant, and `reddit.py:362-364` swallows non-200 and returns
`[]`. Flipping the flag would have produced silent zeros.

---

## 4. COST — 4 of 7 done

**Done:** Apify response cache (`response_cache.py`, migration 009); trends waste
($34.28 of a $45 cycle — 76% — was spent on runs whose results the client
discarded; pytrends is now primary, Apify opt-in via `TREND_WARM_APIFY_ENABLED`);
TikTok cache key (was seeded with per-run product titles ⇒ 100% miss forever ⇒
$48/mo bomb); image-cache poisoning.

**Open:**
- **Qualitative read cache** (~$17/mo + latency). 3,000 grok-3 calls/month, no
  cache. Key on `product_key` + hash of `_collect_evidence` + model; TTL 7d;
  **never cache failures**; add an `OSPRA_QUAL_CACHE_BYPASS` escape or
  `evals/qualitative_source_value.py:446-455` silently measures nothing.
  **Prior results are already persisted** in `DiscoveredProduct.payload['qualitative_assessment']`
  → free backfill, cache starts hot.
- **AE-DS detail cache.** `ds_client.py:109-110` dict is per-process; the cron is
  a fresh process ⇒ ~3,000 calls/mo at ~100% miss. Real damage isn't dollars: the
  serial loop can exceed the 30s wrapper, cancelling ALL pricing so every product
  silently keeps the inflated heuristic cost basis.
- **Cloudinary.** `CLOUDINARY_*` undeclared in `render.yaml`, and the Stability
  enhancer writes to disk directly and never calls `ImageStorage`. Until both are
  fixed there is **no cross-user image amortization**.
- Reconcile the `$0.06`/image constant — code says both 6 credits and 2 credits;
  cost reporting is 20–200% wrong.

---

## 5. ALIEXPRESS DS FEED — 3 bugs fixed, feature gated OFF

Three stacked causes, each producing the identical `[AE-DS] feed empty/dead`:
1. envelope navigation (`resp_result` is a WRAPPER, not an alias for `result`)
2. `DS_Global_topsellers` is **not a valid feed** — this app has 125 valid feeds;
   ask `aliexpress.ds.feedname.get`. Verified working: `DS_Home&Kitchen_bestsellers`,
   `DS_Beauty_bestsellers`, `DS_ConsumerElectronics_bestsellers`,
   `DS_Sports&Outdoors_bestsellers`
3. the intake niche gate rejected 100% of a healthy batch (docstring promised a
   safety valve that was never implemented)

**Then I caused a regression and gated it off.** DS rows are NOT interchangeable
with affiliate rows: `cost_price`/`suggested_price`/`profit` are computed inside
`_fetch_aliexpress` (the AFFILIATE path, `product_discovery.py:3290-3315`). With
the feed broken, every run fell through to that path; with it working, the feed
**suppresses the fallback** and hands the pipeline unpriceable rows — measured
live as AliExpress 9 → 0 per niche.
**To re-enable:** extract the price normalisation out of `_fetch_aliexpress` into
a shared helper, apply it to DS rows, then set `AE_DS_FEED_ENABLED=true`.

**Cross-referencing (0 matches, ever) is NOT a matcher bug.** All 805 real AE×CJ
pairs from the live catalog were scored through the real matcher: max 0.514, and
the top pairs are genuinely different products; 6/6 hand-built same-product pairs
clear the 0.55 threshold. The cause is **sourcing**: AE gets 3–8 trending
keywords, CJ gets ONE hardcoded keyword (`product_discovery.py:3543-3547`).
*Fix:* reverse lookup — for the top-K AE products, `cj_client.smart_search(clean_title)`
and score those against that product. Cost: up to 45 of 100 sourcing points per
missed match (~9 points of base score).

---

## 6. OWNER ACTIONS (only you can do these)

1. **Render env:** `ENVIRONMENT=production`, `REDIS_URL`, `CREDENTIALS_ENCRYPTION_KEY`
   (all 3 services), `JWT_SECRET_KEY` (the 2 crons), `ALIEXPRESS_TRACKING_ID=default`,
   `CLOUDINARY_*`.
2. **LemonSqueezy dashboard:** which webhook URL is configured? If
   `/api/payments/webhook`, subscription **downgrades have never persisted**
   (`payments/lemonsqueezy.py` imports `get_db_session`, which doesn't exist).
   Owner deferred this to last.
3. **Decide:** drop the Reddit/X DB columns? Delete the two dead background jobs?
   Apply the `sentiment_confidence` recalibration (correct, but lowers grades)?
4. **Backfill** the plaintext Shopify credential rows (C2).
5. Verify the Stability per-image credit cost in their dashboard.

---

## 7. RECOMMENDED MCP / CONNECTORS

- **AfterShip TikTok Shop** — real authenticated TikTok Shop data; replaces the
  $48/mo scraper that can never cache.
- **PostHog** (already connected) — the honest answer to "every button works":
  real telemetry on which calls fail for real users.
- **Playwright** — turns "every button works" into a test suite.
- **Shopify** (connected, Oubon Shop / Basic / USD) — real sales data is the
  ground truth the self-learning loop currently lacks.
- **Vercel AI Gateway** — serves "auto-update the AI factory per job": model
  routing, failover, per-call cost tracking by config instead of code.
- **Canva** — ad creatives for the autopilot loop.

**Autopilot decision (owner):** propose-and-approve, not auto-spend. Build
allocation logic, hard caps, kill switch, audit trail; autonomy stays off until
signal quality is proven.
