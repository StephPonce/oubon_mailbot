# Ospra OS — Master Fix Task List

**Generated from a full line-by-line review of the codebase (~238K LOC).**
**Purpose:** hand this to an AI executor (Fable 5) to work through systematically.

## How to use this document

- Tasks are numbered **1–N continuously** and grouped by section (A–K). Reference any task by its number.
- Each task has: **Severity**, **Location(s)**, **Problem**, **Fix**, **Done when**.
- **Line numbers are as-of-review and may drift.** The executor should confirm the exact line/symbol before editing (grep for the described code, don't trust the line number blindly).
- **Priority order to work in:** Section A (secrets) → B (money) → C (auth) → E (crashes) → D (fake data) → F/G (dead code + consolidation) → H/I (architecture) → J/K (hygiene/tests).
- **Golden rule for this codebase:** when two implementations of the same thing exist, do NOT add a third. Pick the live one, wire everything to it, delete the rest. Confirm "live vs dead" with a repo-wide import grep before deleting anything.

**Severity legend:** `P0` = do immediately (security/money/legal). `P1` = serious (correctness/trust). `P2` = structural (dead code/dup/architecture). `P3` = hygiene.

---

# SECTION A — Secrets, Credentials & Repo Hygiene (P0)

### 1. Rotate the leaked Google OAuth credentials
- **Severity:** P0 (most urgent item in the entire list)
- **Location:** git history — `.secrets/credentials.json`, `.secrets/gmail_token.json` (added in first commit `f02ee5f`, untracked later in commit `88acf6a` "untrack leaked credentials")
- **Problem:** These OAuth client secrets/tokens were committed and sat in history for months. Untracking does NOT remove them from history — anyone who clones/fetches the repo can still recover them.
- **Fix:** (a) Rotate the OAuth client secret + revoke the stored tokens in Google Cloud Console NOW. (b) Purge them from git history with `git filter-repo` (preferred) or BFG, then force-push. (c) Confirm no other historical commit contains live secrets.
- **Done when:** old creds are revoked in Google, history no longer contains the files, and app uses freshly-issued creds from env.

### 2. Purge and rotate ALL other secrets ever committed
- **Severity:** P0
- **Location:** repo history generally; also confirm `.secrets/*.json` variants
- **Problem:** If one secret leaked, assume others did. TikTok, AliExpress, CJ, Anthropic, Shopify keys may exist in history.
- **Fix:** Run a history secret scan (`gitleaks detect --log-opts="--all"`), rotate anything found, purge from history.
- **Done when:** gitleaks reports zero findings across full history.

### 3. Remove committed database artifacts from tracking
- **Severity:** P0
- **Location:** tracked file `data/action_history.db-journal`; also root `ospra_os.db` (18MB), `multi_store.db`, `oubon_store.db`, `data/*.db`
- **Problem:** SQLite DB + journal files are tracked in git. They bloat the repo and can contain real customer/order data.
- **Fix:** `git rm --cached` all `*.db`, `*.db-journal`, `*.sqlite` files; confirm `.gitignore` covers them (it does for `*.db` but the journal slipped through — add `*.db-journal`, `*.sqlite3`). Purge large DB blobs from history if they contain PII.
- **Done when:** `git ls-files | grep -E '\.(db|sqlite|db-journal)'` returns nothing.

### 4. Remove the hardcoded whitelabel admin key
- **Severity:** P0
- **Location:** `ospra_os/whitelabel/routes.py:169` — `if x_admin_key != "admin-key-placeholder":`
- **Problem:** All whitelabel admin endpoints (create/activate/suspend partner) are "protected" by a hardcoded string shipped in source. Anyone reading the code is an admin.
- **Fix:** Replace with a real admin auth dependency (see task 30's `require_admin`), read any shared secret from env, and compare with `hmac.compare_digest`.
- **Done when:** no hardcoded key remains; endpoints require a verified admin identity.

### 5. Remove insecure JWT secret fallbacks
- **Severity:** P0
- **Location:** `auth/jwt_auth.py`, `auth/jwt_handler.py`, `middleware/tier_enforcement.py` — each has its own hardcoded `JWT_SECRET_KEY` fallback literal
- **Problem:** Three different hardcoded fallback secrets. If `JWT_SECRET_KEY` env is ever unset in prod, tokens are signed with a public, guessable key → full auth bypass.
- **Fix:** Centralize secret loading in one module; in production, raise on missing secret (fail-closed) instead of falling back. Delete all three literals.
- **Done when:** app refuses to start in prod without a real `JWT_SECRET_KEY`, and only one code path reads it.

### 6. Stop logging and rendering OAuth tokens
- **Severity:** P0
- **Location:** `api/aliexpress_oauth.py:207-234`, `api/aliexpress_affiliate_oauth.py:181-234`
- **Problem:** OAuth callbacks `print()` full request params (incl. `app_key`, computed `sign`) to stdout and embed the complete token JSON response into the HTML page returned to the browser. Tokens land in logs and browser history.
- **Fix:** Remove all `print()` of params/tokens; never render token values into responses. Redirect to a neutral success page. Store tokens server-side only.
- **Done when:** no token/secret value is logged or returned in any OAuth callback.

### 7. Encrypt AliExpress tokens at rest + remove token preview leak
- **Severity:** P0
- **Location:** `database/aliexpress_tokens.py:21-22` (plaintext `Text` columns), `get_token_status()` ~line 178 (returns first 20 chars of raw token)
- **Problem:** Access/refresh tokens stored in plaintext; status endpoint leaks a token prefix.
- **Fix:** Encrypt with the existing `security/credential_encryption.py` Fernet layer (same pattern as Shopify/Amazon). Remove the token-prefix from `get_token_status()`.
- **Done when:** tokens are encrypted columns; no endpoint returns any portion of a token.

### 8. Encrypt TikTok tokens at rest
- **Severity:** P0
- **Location:** `database/tiktok_tokens.py:34-35` (plaintext)
- **Problem:** TikTok access/refresh tokens stored in plaintext.
- **Fix:** Encrypt via `credential_encryption.py`.
- **Done when:** columns encrypted.

### 9. Fix silent plaintext-credential fallback
- **Severity:** P0
- **Location:** `database/store_models.py:100-105` (no log), `database/amazon_models.py:141-153` (logs warning)
- **Problem:** If the encryption module fails to import, credentials silently fall back to plaintext storage.
- **Fix:** Make encryption import failure fail-closed (raise) rather than silently store plaintext. At minimum, both paths must log an error and refuse to persist.
- **Done when:** no path stores credentials in plaintext under any import condition.

### 10. Fix misleading "# Encrypted" comments (actually plaintext)
- **Severity:** P1
- **Location:** `database/whitelabel_models.py:181` (`smtp_password`), `database/user_models.py:45` (`custom_ai_keys`)
- **Problem:** Columns carry `# Encrypted` comments but no encryption occurs.
- **Fix:** Either implement real encryption on write/read, or remove the comment and encrypt in the service layer. Prefer real encryption.
- **Done when:** comment matches reality and sensitive fields are encrypted.

### 11. Stop sending full request headers to Sentry
- **Severity:** P0
- **Location:** `observability/middleware.py:71` — `dict(request.headers)` to Sentry breadcrumbs
- **Problem:** Authorization/Cookie headers (live credentials) are exfiltrated to a third-party SaaS on any exception. The redaction in `error_tracking.py:113` doesn't cover this Sentry surface.
- **Fix:** Redact `Authorization`, `Cookie`, `X-*-Token` before attaching headers; or attach an allowlist of safe headers only.
- **Done when:** no credential header can reach Sentry.

### 12. Remove Fernet-key-to-stdout in migration script
- **Severity:** P1
- **Location:** `scripts/old_tests/migrate_gmail_to_db.py:80-84`
- **Problem:** Auto-generates and prints a raw Fernet encryption key to stdout/logs if env var unset.
- **Fix:** Never print keys. Require the key from env; fail if missing. (This file is also a candidate for deletion — see task 105.)
- **Done when:** no key is printed anywhere.

### 13. Stop passing TikTok bearer tokens via query string / raw JSON
- **Severity:** P1
- **Location:** `tiktok/routes.py`
- **Problem:** Bearer tokens travel in query strings (logged by proxies/servers) and are returned raw in JSON responses.
- **Fix:** Move tokens to Authorization headers / request bodies; never echo tokens in responses.
- **Done when:** tokens never appear in URLs or response bodies.

### 14. Fix in-memory Shopify token dict that leaks across users
- **Severity:** P0
- **Location:** `api/shopify_routes.py:67` (`_connected_stores` global dict, plaintext), `list_stores` ~line 172 (returns ALL stores globally, no user filter)
- **Problem:** Shopify access tokens held in a process-global plaintext dict; the store-listing endpoint returns every user's connected stores to any authenticated caller. Also breaks across workers/restarts.
- **Fix:** Delete this whole parallel Shopify integration; use the DB-backed `shopify_oauth_routes.py` + `Store` model exclusively (see task 124). Filter all store queries by `user_id`.
- **Done when:** no global token dict exists; store lists are per-user.

### 15. Env/DEBUG hygiene for production
- **Severity:** P1
- **Location:** local `.env`, `.env.local` (contain `DEBUG=true` and ~40 live keys — correctly gitignored), `docker-compose.yml` (`FLOWER_BASIC_AUTH` default `admin:ospra123`)
- **Problem:** Ensure `DEBUG` is never true in prod; weak default Flower password.
- **Fix:** Confirm Render sets `DEBUG=false`; require `FLOWER_BASIC_AUTH` from env with no weak default; document that local `.env` holds live keys (back up securely, don't sync to cloud drives).
- **Done when:** prod runs with DEBUG off and no default credentials anywhere.

---

# SECTION B — Money / Financial Safety (P0)

> These are the paths that spend real money or place real orders. Treat every one as "do not enable in production until fixed."

### 16. Add idempotency to auto-fulfillment order placement
- **Severity:** P0
- **Location:** `fulfillment/auto_fulfillment.py` — `_fulfill_via_cj()` ~lines 310-413; order placed at 361-368 BEFORE local save at 377-384
- **Problem:** No check for "has this Shopify order/line-item already been submitted to the supplier?" A retry or webhook redelivery can place duplicate paid orders.
- **Fix:** Add an idempotency key (Shopify order id + line-item id) with a unique DB constraint; check-before-place; record the attempt atomically before/around the API call. Make the local record write happen in the same transaction boundary as marking the order submitted.
- **Done when:** the same order can never be placed twice, proven by a test that replays the same event.

### 17. Wire the auto-fulfillment kill switch to the engine
- **Severity:** P0
- **Location:** flag defined in `fulfillment/routes.py:46` and `:349` (`auto_fulfill_enabled`); engine `fulfillment/auto_fulfillment.py` never reads it (verified: grep finds it only in routes)
- **Problem:** The dashboard "auto-fulfill off" toggle does nothing. An admin who thinks they disabled auto-ordering has not.
- **Fix:** Load `auto_fulfill_enabled` in the engine and hard-return before any supplier call when false. Default false.
- **Done when:** toggling off in the UI provably stops all order placement.

### 18. Fix "order succeeded but reported failed" parse path
- **Severity:** P0
- **Location:** `fulfillment/auto_fulfillment.py:405` (`except Exception` wrapping response parsing)
- **Problem:** If CJ's order succeeds server-side but the JSON response fails to parse, code reports FAILED. Combined with no idempotency (task 16), a retry double-orders.
- **Fix:** Distinguish "API call succeeded" from "parsing failed." On parse failure, treat the order as possibly-placed: record it, alert for manual reconciliation, never blind-retry.
- **Done when:** a parse failure cannot cause a duplicate order.

### 19. Add spend cap, order-count limit, stock & address validation to fulfillment
- **Severity:** P0
- **Location:** `fulfillment/auto_fulfillment.py` — `supplier_cost` captured at 297-298 but never used; address fields `.get(k,'')` at 341-358 with no validation
- **Problem:** No per-order value ceiling, no daily order-count cap, no live stock/price check before ordering, no address validation (missing address1/zip, PO boxes) → malformed or runaway orders submitted.
- **Fix:** Before placing: verify stock/price against supplier, validate required address fields, enforce a configurable max per-order value and max orders/day, and a global daily spend cap. Route anything failing to manual review.
- **Done when:** orders outside limits or with bad addresses are queued for review, not auto-placed.

### 20. Resolve the dead AliExpress fulfillment stub vs. "live" status
- **Severity:** P1
- **Location:** `fulfillment/auto_fulfillment.py:495-527` (`_fulfill_via_aliexpress` builds payload then hits `# TODO`, falls through to manual queue)
- **Problem:** AliExpress auto-fulfillment is a stub, but routing/status endpoints present it as live.
- **Fix:** Either implement it (with all of task 19's guards) or make the status/UI clearly report AliExpress fulfillment as manual-only. No "looks live but isn't."
- **Done when:** status reflects reality.

### 21. Add a hard ceiling to ad budget auto-optimization
- **Severity:** P0
- **Location:** `advertising/scheduler.py:364-416` (`optimize_budgets()` applies `budget * 1.20` every 6h, no cap); `budget_limit` column exists at `database/advertising_models.py:37` but is written/read nowhere
- **Problem:** Budgets compound 20% every 6 hours with no ceiling. $15/day → ~$644/day in 10 days.
- **Fix:** Wire `budget_limit` as a hard ceiling; never exceed it. Add an absolute per-campaign and account-wide daily spend cap. Add a max-increase-per-day throttle.
- **Done when:** no code path can raise a budget above its limit.

### 22. Gate the ad-budget platform write behind the cap (before completing the TODO)
- **Severity:** P0
- **Location:** `advertising/scheduler.py:409-410` (increase only written in-memory; platform write is a TODO)
- **Problem:** The runaway logic is currently inert only because the platform-side write is unfinished. Finishing it without the cap (task 21) turns on uncapped real spend.
- **Fix:** Implement task 21 FIRST. Only then wire the platform budget update, with the cap enforced on the value actually sent.
- **Done when:** the platform write cannot send an uncapped value.

### 23. Persist active-campaign state so safety monitors survive restarts
- **Severity:** P0
- **Location:** `advertising/scheduler.py:81` (`active_campaigns` in-memory dict, never reloaded)
- **Problem:** After any restart/deploy, the hourly auto-pause-of-poor-performers monitor has no campaigns to watch, while real spend continues on the platform.
- **Fix:** Load active campaigns from the DB on startup; treat the DB as source of truth, not the in-memory dict.
- **Done when:** monitors resume protecting all live campaigns after a restart.

### 24. Add a global ad "pause everything" kill switch + budget upper bound
- **Severity:** P1
- **Location:** `advertising/routes.py:52` (`daily_budget: float = 15.0`, no upper bound); no global pause endpoint anywhere
- **Problem:** No way to stop all spend at once; `daily_budget` accepts any value unclamped into Meta (cents) / Google (micros).
- **Fix:** Add a global pause endpoint (admin-gated) that pauses all campaigns on all platforms. Clamp `daily_budget` to a max.
- **Done when:** one call pauses everything; budgets are bounded.

### 25. Fix Google ads enabled under paused campaign
- **Severity:** P1
- **Location:** `advertising/.../google_ads.py:145,163` (ad group + ad created `ENABLED`)
- **Problem:** Meta/TikTok create paused-by-default; Google creates the ad group and ad ENABLED under a paused campaign, so un-pausing the campaign alone starts spend with no further gate.
- **Fix:** Create Google ad groups/ads PAUSED, consistent with Meta/TikTok.
- **Done when:** all platforms create fully paused.

### 26. Require human review before AI listings publish live (or make it explicit)
- **Severity:** P1
- **Location:** `integrations/shopify_auto_deploy.py:250` (`status: "active"`); gated only by `services/auto_deployer.py` `enabled=False` default
- **Problem:** Once the single `enabled` boolean is flipped, AI-generated title/description/price go live to real customers hourly with no per-listing human review.
- **Fix:** Default new auto-deploys to Shopify **draft**; require an explicit per-listing or batch approval to publish. Keep `auto_publish` opt-in and clearly labeled as "publishes without review."
- **Done when:** publishing live requires a deliberate approval step.

### 27. Add idempotency/replay protection to payment webhooks + fix 200-on-failure
- **Severity:** P0
- **Location:** `payments/routes.py:317-323` (DB-write failure still returns HTTP 200)
- **Problem:** No idempotency on webhook events (replay can double-apply). A DB failure during processing returns 200, so LemonSqueezy won't retry → customer pays but isn't upgraded.
- **Fix:** Dedupe by event id (unique constraint); on processing failure return 5xx so the provider retries; make the tier change + event-record atomic.
- **Done when:** replays are no-ops and failed upgrades are retried, not silently dropped.

### 28. Fix crash-broken refund automation
- **Severity:** P0
- **Location:** `email_automation/smart_reply.py` (calls `lookup_order()`, `get_order_status()`, `format_tracking_response()`, `process_refund()` on a `ShopifyClient` that has none of these methods)
- **Problem:** The refund/tracking path throws `AttributeError` on the first real customer email, so the well-designed refund guardrails ($100 cap, 15-day window, ownership check in `refund_processor.py`) never execute. It only "worked" against mocks.
- **Fix:** Add the missing order/refund methods to the canonical `ShopifyClient` (see task 118), wire `smart_reply` to it, and test end-to-end against the real class. Verify the `refund_processor` guardrails actually run.
- **Done when:** a real refund request runs through the guardrails without crashing, and refunds outside limits go to manual review.

### 29. Replace fake "demo mode" Meta ad deployment
- **Severity:** P1
- **Location:** `services/action_executor.py:610-629` (fabricates `platform_campaign_id`, marks DB row active, makes zero API calls)
- **Problem:** One code path fakes ad deployment while another (`schedule_manager.py`) really deploys — inconsistent, and the fake path reports success.
- **Fix:** Route all ad deployment through the real implementation; delete the fake path or clearly mark it as a dev-only mock behind a flag.
- **Done when:** no path claims a campaign was created without creating one.

### 30. Remove hardcoded price in real Meta campaign creation
- **Severity:** P1
- **Location:** `services/schedule_manager.py:176` (`'price': 29.99  # TODO: Get from DB`)
- **Problem:** Every campaign built through this path uses a fabricated $29.99 price regardless of the actual product.
- **Fix:** Fetch the real product price from the DB.
- **Done when:** campaigns use the real price.

### 31. Verify template purchase payment before granting
- **Severity:** P1
- **Location:** `api/template_routes.py:393-419` (`purchase_template` trusts a client `payment_token`, returns "Purchase successful")
- **Problem:** Payment token isn't verified against a processor before granting the paid template → possible free templates.
- **Fix:** Verify the payment with the processor server-side before granting; only then mark purchased.
- **Done when:** unverified tokens cannot unlock paid templates.

---

# SECTION C — Authentication & Authorization (P0/P1)

> Pattern across the app: authentication (is this a valid login?) is mostly right; **authorization (does this user own this thing?) is frequently missing (IDOR)**. Fix by extracting `user_id`/ownership from the JWT, never from client-supplied params.

### 32. Lock down the unauthenticated monitoring/health control surface
- **Severity:** P0
- **Location:** `monitoring/routes.py` — all 24 routes have no auth (verified: router has no `dependencies=`, no per-route `Depends`). Includes `POST /api/health/jobs/{name}/trigger|disable|enable` and `GET /api/health/errors` (full stack traces)
- **Problem:** Anyone unauthenticated can disable/trigger production background jobs and read internal errors/stack traces.
- **Fix:** Add an admin auth dependency at the router level (`dependencies=[Depends(require_admin)]`). Keep only a minimal unauthenticated `GET /api/health` liveness probe returning `{"status":"ok"}` with no internals.
- **Done when:** all control/detail endpoints require admin; only a trivial liveness check is public.

### 33. Fix IDOR + open mail relay in task trigger routes
- **Severity:** P0
- **Location:** `api/task_routes.py:299-460` — trigger endpoints take unchecked `user_id`/`store_id` query params; `/trigger/send-email` takes arbitrary `to`/`subject`/`body`
- **Problem:** Any logged-in user can run actions for ANY user_id/store_id, and send arbitrary email as the platform (open spam/phishing relay on a trusted domain).
- **Fix:** Derive `user_id` from the JWT; verify store ownership; remove arbitrary-recipient email sending (restrict to the authenticated user's own verified addresses/templates).
- **Done when:** users can only act on their own resources; no arbitrary email send.

### 34. Admin-gate the admin panel
- **Severity:** P0
- **Location:** `admin/routes.py:9,97,143,154` — uses `get_current_user` (any authenticated user), not `require_admin`
- **Problem:** Any authenticated free-tier user can hit `/admin/*` and view aggregate business data. A correct `require_admin` already exists at `auth/dependencies.py:175-189` and is simply never imported here.
- **Fix:** Replace `get_current_user` with `require_admin` on every admin route.
- **Done when:** non-admins get 403 on all `/admin/*`.

### 35. Fix unauthenticated WebSocket alerts endpoint
- **Severity:** P0
- **Location:** `api/alert_routes.py:327-372` (`websocket_alerts_root`) — trusts client-supplied `user_id` from first message, falls back to `"anonymous"`; a correct JWT-validating handler exists ~lines 234-271 in the same file
- **Problem:** Any client can read any user's alert stream by supplying their `user_id`.
- **Fix:** Delete the insecure root handler; keep only the JWT-validated one. Require a valid token before streaming.
- **Done when:** alert streams require a validated token and are scoped to that user.

### 36. Verify the Gmail Pub/Sub webhook
- **Severity:** P0
- **Location:** `email_automation/automation_routes.py:100-120` (`POST /gmail/pubsub/webhook`) — no auth/signature
- **Problem:** Anyone hitting the URL triggers `process_emails_background` → paid AI calls, auto-replies, refunds.
- **Fix:** Verify the Google Pub/Sub OIDC token (audience + issuer) on every request; reject unverified.
- **Done when:** only Google-signed pushes are processed.

### 37. Authenticate the AliExpress product endpoints
- **Severity:** P1
- **Location:** `api/aliexpress_product_routes.py` — `/feed-names`(728), `/hot`(738), `/bestsellers`(758), `/details`(770), `/product/{id}`(897) unauthenticated; sibling `/search`(783), `/hybrid-discover`(913) correctly gated
- **Problem:** Free, unlimited access to product intelligence + burns API quota; inconsistent within one file.
- **Fix:** Add the same auth + tier enforcement used by `/search` to all product endpoints.
- **Done when:** all product endpoints require auth and count against tier limits.

### 38. Admin/tier-gate auto-deploy controls
- **Severity:** P0
- **Location:** `api/auto_deploy_routes.py` — `/enable`,`/disable`,`/criteria`,`/run-now` only require `get_current_user`; operates on a global singleton (not tenant-scoped)
- **Problem:** Any authenticated user can enable auto-deployment, change the AI cost ceiling, or force a run for the whole system.
- **Fix:** Require admin; scope to the caller's tenant/store; remove the global singleton or key it by tenant.
- **Done when:** only admins control auto-deploy, scoped to their own stores.

### 39. Tier-gate autopilot enable/disable/config
- **Severity:** P1
- **Location:** `api/autopilot_routes.py` — enable/disable/config not gated (only the aggressive preset uses `require_tier`)
- **Problem:** Unattended-spend automation can be toggled without tier checks.
- **Fix:** Apply `require_tier(...)` consistently to all state-changing autopilot endpoints.
- **Done when:** enabling autopilot requires the appropriate tier.

### 40. Authenticate deployment `/preview`
- **Severity:** P1
- **Location:** `api/deployment_routes.py:593` (`preview_deployment` has no `current_user`, unlike siblings)
- **Problem:** Unauthenticated callers trigger paid AI content + DALL-E image generation (~$0.02–0.06 each).
- **Fix:** Require auth; rate-limit.
- **Done when:** preview requires auth and is rate-limited.

### 41. Decide + document auth on trends endpoints
- **Severity:** P1
- **Location:** `api/trends_routes.py` — `/live`,`/movers`,`/breakouts`,`/product/{id}`,`/heatmap` all unauthenticated
- **Problem:** Core trend intelligence exposed with zero auth, unlike the rest of the app. May be intentional (public page) but nothing says so.
- **Fix:** If intentionally public, mirror `public_routes.py` (anonymize, rate-limit, document). Otherwise require auth.
- **Done when:** the auth posture is deliberate, documented, and safe.

### 42. Fix intelligence action-execute IDOR
- **Severity:** P0
- **Location:** `intelligence/intelligence_core_routes.py:173-300` — `/action/preview`,`/execute`,`/undo/{id}`,`/grade/*`,`/progress/*`,`/tier/upgrade` have no `current_user`; `/action/execute` uses client-supplied `request.user_id` (a comment claims this was removed for security, but the code still uses it)
- **Problem:** Anyone can execute a product deploy / price change / tier upgrade for an arbitrary user_id.
- **Fix:** Add `Depends(get_current_user)`; derive user_id from the token; delete `user_id` from the request model. Make the comment true.
- **Done when:** these endpoints require auth and ignore any client-supplied user_id.

### 43. Fix billing tier-change IDOR
- **Severity:** P0
- **Location:** `payments/routes.py:205-240` (`POST /change-tier`) — no auth, no ownership; calls `lemonsqueezy.change_subscription_tier()` on any `subscription_id`
- **Problem:** Anyone can re-tier any subscription, including other paying customers'.
- **Fix:** Require auth; verify the subscription belongs to the caller before changing.
- **Done when:** users can only change their own subscription.

### 44. Neutralize the deprecated insecure tier upgrade
- **Severity:** P0
- **Location:** `subscription/tier_manager.py:180-225` (`upgrade_tier(user_id, new_tier)` writes tier from bare args, no payment proof; "deprecated" but live)
- **Problem:** Fully functional path to set any user's tier with no payment.
- **Fix:** Delete it, or make tier state derivable ONLY from verified payment events. Grep for callers first.
- **Done when:** no code can set a paid tier without a verified payment.

### 45. Authenticate analytics customer routes + stop token-in-query
- **Severity:** P0
- **Location:** `analytics/customer_routes.py` (~20 routes, zero auth; `shopify_token` accepted as query param at ~441, ~481)
- **Problem:** No auth on customer analytics; Shopify token leaks via URL into logs/history.
- **Fix:** Require auth on all routes; move the token to a header or (better) load it server-side from the store record; never accept it as a query param.
- **Done when:** all routes authenticated; no token in any URL.

### 46. Authenticate reports routes + fix IDOR
- **Severity:** P1
- **Location:** `reports/routes.py` (all routes, zero auth; IDOR on report/schedule IDs)
- **Problem:** Anyone can read/generate/schedule reports for any ID.
- **Fix:** Require auth; scope every report/schedule query by owner.
- **Done when:** reports are per-user and authenticated.

### 47. Authenticate testing/A-B routes + fix IDOR
- **Severity:** P1
- **Location:** `testing/routes.py` (20 routes, zero auth; can end/implement-winner on another store's live price test)
- **Problem:** Cross-tenant manipulation of live pricing experiments.
- **Fix:** Require auth; verify store ownership on every test operation.
- **Done when:** users can only touch their own tests.

### 48. Stop exposing the raw platform AliExpress token
- **Severity:** P0
- **Location:** `aliexpress/routes.py:487-501`
- **Problem:** Returns the raw platform AliExpress access token to any authenticated tenant.
- **Fix:** Remove this endpoint or restrict to admin and never return the token value.
- **Done when:** no tenant can retrieve the platform token.

### 49. Add ownership check to federated insight outcome
- **Severity:** P1
- **Location:** `federated/routes.py` (`record_insight_outcome` — no check the caller owns `application_id`)
- **Problem:** A tenant can write outcomes against another tenant's application id.
- **Fix:** Verify `application_id` ownership against the authenticated tenant.
- **Done when:** cross-tenant outcome writes are rejected.

### 50. Admin-gate AliExpress manual token entry
- **Severity:** P0
- **Location:** `api/aliexpress_token_routes.py` `/manual-entry` POST (any authenticated user can overwrite prod tokens; only length-checked)
- **Problem:** Any user can overwrite production API tokens.
- **Fix:** Require admin; validate token format; audit-log the change.
- **Done when:** only admins can set tokens.

### 51. Stop treating a paid tier as "admin"
- **Severity:** P1
- **Location:** `api/aliexpress_product_routes.py` `_is_admin` ~1079 (treats `subscription_tier == "stratosphere"` as admin); exposes `/debug/raw-response`, `/test/order-create-check` (attempts a real placeorder), `/test/enrichment/{id}`
- **Problem:** The highest-paying customer gets admin/debug/test access, including a real order-create attempt against production creds.
- **Fix:** Use a real admin flag (`require_admin`), not a paid tier. Environment-gate all `/debug` and `/test` endpoints off in prod.
- **Done when:** debug/test endpoints are admin-only and disabled in prod.

### 52. Bound password length on reset
- **Severity:** P2
- **Location:** `api/password_reset_routes.py:297` (only `len < 8` checked)
- **Problem:** No max length → bcrypt DoS with a multi-MB password.
- **Fix:** `Field(..., min_length=8, max_length=128)` on the model.
- **Done when:** over-long passwords are rejected before hashing.

### 53. Fix hardcoded single-user Gmail OAuth
- **Severity:** P1
- **Location:** `gmail/routes.py:119-121` (hardcoded `user_id == 1`, "Default User")
- **Problem:** OAuth writes to one global user regardless of who authenticated; inconsistent with the multi-tenant model and writes to two token stores that can drift.
- **Fix:** Use the `get_current_user` pattern; persist tokens to the per-user DB store only (see task 114).
- **Done when:** Gmail OAuth is per-authenticated-user.

---

# SECTION D — Fabricated / Fake / Placeholder Data (P1)

> These surfaces show invented numbers as if real, usually with no `is_mock` flag. Fix = replace with real data OR return an explicit "data unavailable / not connected" state the UI honors. Never blend mock fields silently into real payloads.

### 54. Daily brief performance snapshot is hardcoded
- **Severity:** P1
- **Location:** `intelligence/daily_brief.py:171-211` (`_get_performance_snapshot` returns zeros + `health_score: 75.0`; fed to Claude as fact)
- **Problem:** Users see "business health 75/100" and $0 metrics narrated as real by the AI.
- **Fix:** Compute from real data, or return `data_unavailable` and have the brief say so explicitly.
- **Done when:** the brief never states fabricated metrics.

### 55. Momentum tracker fabricates its baseline
- **Severity:** P1
- **Location:** `intelligence/momentum_tracker.py:191-192` (`baseline = current * 0.7`)
- **Problem:** "Trending velocity" is computed against a baseline invented from the current value, mathematically guaranteeing ~+43% for everything. The whole "stock-market" trends view is fake.
- **Fix:** Use real historical time-series (you have `product_timeseries`); if no history, return "insufficient history," not a synthetic baseline.
- **Done when:** momentum reflects real change or reports insufficient data.

### 56. Realtime updater writes mock products into the live cache
- **Severity:** P1
- **Location:** `intelligence/realtime_updater.py:152-182` (`_generate_mock_products` random.uniform → same `cache['trending']` as real data, no flag)
- **Problem:** On discovery failure, fabricated products enter the production cache indistinguishably from real ones.
- **Fix:** On failure, keep last-known-good or return empty with an error flag; never inject random products. If a mock is ever used, tag `is_mock: true` and have the API/UI honor it.
- **Done when:** no unflagged mock data can reach the cache.

### 57. Unified context has hardcoded-empty data sources
- **Severity:** P1
- **Location:** `intelligence/unified_context.py:250-307` (`_get_email_signals`, `_get_social_data`, `_get_competitor_data` return hardcoded empties despite docstring)
- **Problem:** The AI's "single source of truth" silently omits three declared categories; correlation detection always reports zero for them.
- **Fix:** Implement the fetchers or return explicit `not_connected` markers the briefing surfaces to the user.
- **Done when:** the context reports real data or an honest gap.

### 58. "Master" recommendation engine runs on fake products
- **Severity:** P1
- **Location:** `intelligence/smart_recommendations.py:266-288` (`_discover_products` returns `f"Product {i} in {niche}"` with fabricated scores)
- **Problem:** The file billed as the "master algorithm" feeds fake products into saturation/marketing/tier logic downstream.
- **Fix:** Call the real discovery engine; if unavailable, return empty, not synthetic products.
- **Done when:** recommendations use real discovered products.

### 59. AI pricing fallback invents ratings/orders
- **Severity:** P1
- **Location:** `intelligence/ai_pricing_generator.py:190-192` (`rating = random.uniform(3.8,4.7)`, `orders = random.uniform(200,2000)`)
- **Problem:** Rule-based fallback returns fabricated ratings/order counts in the same shape as the real path.
- **Fix:** Omit unknown fields or mark them null/unknown; never fabricate ratings/orders.
- **Done when:** pricing output contains no invented metrics.

### 60. Reports engine is fabricated end-to-end
- **Severity:** P1
- **Location:** `reports/report_engine.py` (all 8 sections hardcoded/zeroed; fabricated narrative like "AOV up 12%")
- **Problem:** Entire report output is fake, presented as real business reporting.
- **Fix:** Wire to real analytics queries; if a section has no data, say so.
- **Done when:** every report figure traces to real data.

### 61. Customer analytics is 100% fixtures
- **Severity:** P1
- **Location:** `analytics/customer_analytics.py` (every method returns hardcoded fake customers/churn/retention); `analytics/customer_routes.py` wired to `get_mock_customers()` returning `[]`
- **Problem:** The polished-looking analytics product outputs fixtures; the "real" engine is fed an empty stub so it produces nothing.
- **Fix:** Wire the real engines to real synced customer data (`customer_sync.py`); remove the mock fixtures and the empty stub.
- **Done when:** customer analytics computes from real data.

### 62. Analytics engine blends undisclosed mock fields
- **Severity:** P1
- **Location:** `analytics/analytics_engine.py:429-431` (`random.uniform` fake daily revenue chart), `previous_revenue = monthly_revenue * 0.8  # Mock`
- **Problem:** Mock fields mixed into otherwise-real payloads with no flag.
- **Fix:** Compute previous period from real data; remove the random chart or clearly mark placeholder.
- **Done when:** no mock field ships unflagged.

### 63. Inventory forecasts run on random fake history
- **Severity:** P1
- **Location:** `inventory/routes.py:28-55` (`generate_mock_sales_history` random.uniform); real `shopify_sync.py` not wired to primary routes
- **Problem:** The (correct) forecasting math runs on randomly generated "sales history" in every reachable route.
- **Fix:** Wire the real Shopify-synced history to the forecasting routes; drop the mock generators.
- **Done when:** forecasts use real sales history.

### 64. Niche analyzer fabricates trend deltas and fields
- **Severity:** P1
- **Location:** `intelligence/niche_analyzer.py:746` (`change_30d = score-50`, `change_90d = score-45`), `:791` (`new_sellers_30d` no date filter), `:919` (`is_seasonal = False` hardcoded), `:1128` (`total_reviews` never incremented → avg always 0)
- **Problem:** "30/90-day trend," "new sellers," "seasonal," and "avg reviews" are simulated from single-point data or hardcoded.
- **Fix:** Compute from real historical rows; if absent, report insufficient data. Fix the `total_reviews` increment. Implement or remove `is_seasonal`.
- **Done when:** niche metrics are real or explicitly unavailable.

### 65. Progress flow hardcodes review-stage numbers
- **Severity:** P2
- **Location:** `intelligence/progress_flow.py:253` (progress `50`), `:287` (days `2`) for REVIEW stage (module is also orphaned — see task 88)
- **Problem:** Fabricated precise-looking values.
- **Fix:** Compute from real stage data, or delete the module (task 88).
- **Done when:** removed or computed.

### 66. Background jobs emit "completed" for no-op work
- **Severity:** P1
- **Location:** `intelligence/background_jobs.py` `track_trends`(468-493), `weekly_report`(495-523)
- **Problem:** Scheduled daily/weekly jobs do nothing but push "completed" alerts, implying work happened.
- **Fix:** Implement them or remove the jobs and their fake success alerts.
- **Done when:** no job reports success for work it didn't do.

### 67. Hardcoded success-rate and ROI in AI-facing context
- **Severity:** P1
- **Location:** `learning/summary_generator.py:239` (`success_rate = 0.75` placeholder, surfaced via `context_builder`), `services/store_service.py:364` (`projected_roi = 150.0` for every recommendation)
- **Problem:** Static 75% success rate and flat 150% ROI presented as computed intelligence.
- **Fix:** Compute from real outcomes or omit; don't feed constants to the AI/user as metrics.
- **Done when:** these values are real or absent.

### 68. Amazon `sync_listings` is a stub that claims success
- **Severity:** P1
- **Location:** `services/amazon_service.py:574-600` (returns 0, updates timestamp; docstring says "Sync all listings")
- **Problem:** Method signature implies real sync; body is a TODO.
- **Fix:** Implement or clearly mark unimplemented and don't update the "last synced" timestamp.
- **Done when:** behavior matches the docstring.

### 69. product_research `intelligence_engine` is fake + dead
- **Severity:** P2
- **Location:** `product_research/intelligence_engine.py:433-565` (all data integrations hardcoded stubs; zero importers)
- **Problem:** 100% fabricated and unused. (Confirmed by `connectors/social/youtube.py` docstring referencing it as the placeholder it replaced.)
- **Fix:** Delete the file (see task 94).
- **Done when:** deleted.

### 70. Price optimizer competitor lookup always empty
- **Severity:** P2
- **Location:** `product_research/price_optimizer.py:180-190` (`_find_competitor_prices` always returns `[]`)
- **Problem:** Every live pricing call silently takes the "no competitors" branch despite implying real competitor data.
- **Fix:** Implement or clearly mark as not-yet-available; don't imply competitor pricing exists.
- **Done when:** behavior is honest.

### 71. TikTok Shop comment sentiment is a fixed fabrication
- **Severity:** P1
- **Location:** `product_research/connectors/apify/tiktok_shop.py:356-385` (`_analyze_comments` returns fixed 0.75/0.15/0.10, `total_analyzed: 0`)
- **Problem:** Fabricated sentiment ratio with no "not real" flag for callers.
- **Fix:** Compute from real comments or return `null`/unavailable.
- **Done when:** no fixed fake sentiment is returned.

### 72. TikTok client fabricates prices
- **Severity:** P1
- **Location:** `integrations/tiktok_client.py` (`_estimate_price` random.uniform mixed with real engagement metrics; `_search_videos` placeholder)
- **Problem:** Fake prices flow into the same product dict as real metrics, indistinguishable.
- **Fix:** Remove fabricated prices or mark estimated; implement or disable `_search_videos`.
- **Done when:** no fabricated price ships as real.

### 73. Frontend-compat serves demo data on any error + stub analytics
- **Severity:** P1
- **Location:** `api/frontend_compat_routes.py:325-387` (`DEMO_PRODUCTS` fallback on any exception), `:500-550` (hardcoded `/analytics/*` stubs with a "note" admitting fake)
- **Problem:** A transient DB blip silently serves fabricated products; several "endpoints" are permanent stubs.
- **Fix:** On error, return an error status, not demo products (or require `is_mock` honored by the UI). Implement or remove the stub analytics endpoints.
- **Done when:** real errors surface as errors; no permanent fake endpoints.

### 74. Notifications claim delivery but send nothing
- **Severity:** P1
- **Location:** `services/notifications.py:376-403` (email/slack/webhook/in-app all TODO stubs), `services/notification_routes.py:136` (returns "Notification sent successfully")
- **Problem:** Nothing is sent or persisted (in-memory list), but the API reports success.
- **Fix:** Implement real delivery + DB persistence, or return an honest "not configured" status.
- **Done when:** success responses correspond to real deliveries.

### 75. `FORWARD` email action fakes success
- **Severity:** P2
- **Location:** `email_automation/automation_engine.py:259-269` (returns `success: True`, "not yet implemented")
- **Problem:** Callers checking `success` believe forwarding happened.
- **Fix:** Implement or return `success: False`/not-implemented.
- **Done when:** the result is truthful.

### 76. A/B test p-values are a crude lookup table (false significance)
- **Severity:** P1
- **Location:** `testing/statistics.py:110-154` (14-entry hardcoded p-value table, snaps to nearest bucket; docstring claims `erf`/CDF but `math.erf` is never called)
- **Problem:** Distorted p-values near α=0.05/0.01 — the exact thresholds driving rollout decisions (e.g. z=0.01 → reports p≈0.617 instead of ≈0.992).
- **Fix:** Compute the p-value from the real normal CDF (`statistics.NormalDist().cdf` or `math.erf`). Remove the table; make the docstring true.
- **Done when:** p-values match a real CDF.

### 77. Price-test winner never reaches Shopify
- **Severity:** P1
- **Location:** `testing/price_test_manager.py` `implement_winning_price` (never calls Shopify despite docstring)
- **Problem:** Admin believes a winning price went live when it didn't.
- **Fix:** Implement the Shopify price update or report not-implemented.
- **Done when:** implementing a winner actually changes the price.

### 78. Ad-test manager fake CPM constant
- **Severity:** P2
- **Location:** `testing/ad_test_manager.py` (hardcoded CPM)
- **Problem:** Fabricated cost metric.
- **Fix:** Use real platform CPM or mark estimated.
- **Done when:** CPM is real or clearly estimated.

### 79. Oi action executor is mostly PENDING stubs
- **Severity:** P1
- **Location:** `oi/action_executor.py` (6 of 9 actions return PENDING; deploy/fulfill/email are stubs)
- **Problem:** The in-dashboard AI can't actually do most actions; confirmation scaffolding gates nothing.
- **Fix:** Implement the real actions by delegating to the ONE canonical action executor (task 109), or clearly surface "not available yet" in the UI.
- **Done when:** Oi actions either work or honestly report unavailability.

### 80. Competitive-learning parse fallback invents numbers
- **Severity:** P2
- **Location:** `intelligence/competitive_learning.py:261-310, 465-498` (defaults `confidence=0.7`, `sample_size=len(products)`, `success_match=0.5` on parse failure)
- **Problem:** Fabricated confidence/metrics when the LLM's free-text parse fails, with no signal.
- **Fix:** On parse failure, return an explicit failure, not invented numbers.
- **Done when:** parse failures don't produce fake metrics.

### 81. Unified deployer is scaffolding with hardcoded test store
- **Severity:** P2
- **Location:** `deployment/unified_deployer.py:157` (`existing = None  # Mock`), `:899-911` (hardcoded `test.myshopify.com`/`test_token`), `:822-844` (NameError on undefined `product`)
- **Problem:** Elaborate but non-functional; would only ever write to a fake store. (Also dead — see task 110.)
- **Fix:** Delete it and standardize on the real deployer (task 110).
- **Done when:** removed.

### 82. Fine-tuning training data is partly fabricated
- **Severity:** P2
- **Location:** `ml/training_data.py:150-160` (hand-templated "assistant" reasoning text), `:189-244` (two collectors return `[]`)
- **Problem:** Fine-tuning examples train the model to imitate a template, not real successful completions; 2 of 5 data sources are empty stubs.
- **Fix:** Use real captured completions as training targets; implement or remove the empty collectors.
- **Done when:** training data is genuine.

---

# SECTION E — Correctness Bugs (P1)

> Confirmed crashes, NameErrors, and wrong logic. Several make a whole endpoint/feature non-functional.

### 83. `/ws/trends` WebSocket crashes on every message (NameError)
- **Severity:** P1
- **Location:** `main.py:4429,4460,4484` (uses `timezone.utc` but `from datetime import datetime` only; `timezone` never imported)
- **Problem:** First update raises `NameError`; the except handler also uses `timezone.utc` and crashes again. Endpoint cannot function.
- **Fix:** `from datetime import datetime, timezone`.
- **Done when:** the socket streams updates without NameError.

### 84. `/api/auth/refresh` returns wrong `expires_in`
- **Severity:** P1
- **Location:** `auth/routes.py:360` (hardcoded `expires_in = 15*60`; actual is `ACCESS_TOKEN_EXPIRE_MINUTES`, default 3600s)
- **Problem:** Frontends refresh 45 min early or mismanage sessions.
- **Fix:** Return the real configured lifetime.
- **Done when:** `expires_in` matches the actual token TTL.

### 85. Blocking `psutil` call in async health check
- **Severity:** P1
- **Location:** `utils/health_monitor.py:112` (`psutil.cpu_percent(interval=1)` inside `async def`)
- **Problem:** Blocks the event loop for a full second per call; serializes other coroutines.
- **Fix:** Use `interval=None` (non-blocking) or wrap in `run_in_executor`.
- **Done when:** the health check doesn't block the loop.

### 86. `monitoring/health_monitor.py` NameError on logger
- **Severity:** P1
- **Location:** `monitoring/health_monitor.py:554` (`logger.warning(...)`, `logger` never imported)
- **Problem:** Crashes on any psutil failure.
- **Fix:** Add a module logger.
- **Done when:** no NameError.

### 87. `monitoring/routes.py` NameError on `timezone`
- **Severity:** P1
- **Location:** `monitoring/routes.py:68` (`timezone.utc`, not imported)
- **Problem:** Likely crashes the `/api/health` root endpoint.
- **Fix:** Import `timezone`.
- **Done when:** the endpoint responds.

### 88. `monitoring/job_monitor.trigger_job` is a no-op that reports success
- **Severity:** P2
- **Location:** `monitoring/job_monitor.py:221-243`
- **Problem:** Returns `{"success": True}` without triggering anything.
- **Fix:** Implement or return not-implemented.
- **Done when:** truthful.

### 89. Google Trends connector always returns `[]` (TypeError)
- **Severity:** P1
- **Location:** `product_research/connectors/trends/google_trends.py:188` (passes `metadata=` kwarg that `ProductCandidate` doesn't accept → TypeError, swallowed by broad except)
- **Problem:** The connector is silently non-functional.
- **Fix:** Add `metadata` to the `ProductCandidate` dataclass or stop passing it.
- **Done when:** the connector returns real results.

### 90. `sales_sync_service` NameError masks all store-sync errors
- **Severity:** P1
- **Location:** `services/sales_sync_service.py:109` (`logger` never imported; file uses `print` elsewhere)
- **Problem:** The "don't fail the whole batch" resilience path itself throws `NameError` on any store error.
- **Fix:** Add a module logger.
- **Done when:** per-store errors are logged, batch continues.

### 91. `schedule_manager` UnboundLocalError in error path
- **Severity:** P1
- **Location:** `services/schedule_manager.py:106-108` (references `session` before assignment in except)
- **Problem:** Masks the real DB error during a connectivity failure.
- **Fix:** Initialize `session = None` before the try; guard the except.
- **Done when:** the real error surfaces.

### 92. Auto-deployer ValueError silently drops candidates
- **Severity:** P1
- **Location:** `services/auto_deployer.py:363` (`saturation_levels.index("unknown")` where list lacks "unknown")
- **Problem:** `.index()` raises ValueError, caught by the per-niche broad except, silently disqualifying all candidates for that niche.
- **Fix:** Handle "unknown"/missing saturation explicitly (default rank or skip with a clear reason).
- **Done when:** unknown saturation doesn't drop candidates silently.

### 93. Cohort analyzer week-bucketing bug
- **Severity:** P2
- **Location:** `analytics/cohort_analyzer.py` (`%W` vs ISO-week mismatch)
- **Problem:** Mis-buckets cohorts near year/week boundaries.
- **Fix:** Use ISO week consistently (`isocalendar()`), or align both sides.
- **Done when:** cohorts bucket correctly.

### 94. LTV double-counting flaw
- **Severity:** P2
- **Location:** `analytics/ltv_calculator.py:139-143`
- **Problem:** Minor double-counting in the LTV formula.
- **Fix:** Correct the aggregation; add a unit test with a known dataset.
- **Done when:** LTV matches hand-computed expected value.

### 95. Shopify sync sets cost = price (margin always 0) and ignores variants
- **Severity:** P1
- **Location:** `inventory/shopify_sync.py:86-87` (`unit_cost` and `unit_price` from the same field), `:78` (only first variant read)
- **Problem:** Real synced data has zero margin and drops all SKUs beyond the first.
- **Fix:** Map cost and price to their correct distinct fields; iterate all variants.
- **Done when:** margins compute correctly and all variants sync.

### 96. Tier-limit enforcement is defeated (always allows)
- **Severity:** P1 (breaks monetization, not security)
- **Location:** `core/usage_tracking.py:540-561` (expects nested dicts `limits`/`aliexpress`/`features`; `core/tiers.py` `TIER_DEFINITIONS` is flat) → `get_tier_limit()` always returns None → `can_perform()` defaults to allow (~line 642)
- **Problem:** Every usage-gated action is effectively unlimited for all tiers.
- **Fix:** Align the lookup with the actual flat `TIER_DEFINITIONS` structure; add tests asserting each tier's limits are enforced.
- **Done when:** limits actually cap usage per tier.

### 97. Async AI router blocks the event loop
- **Severity:** P1
- **Location:** `ai/model_router.py` (`async def _call_*` call synchronous SDK clients without `run_in_executor`)
- **Problem:** Each Claude/Groq/OpenAI call blocks the loop for the full round-trip; cascading latency under load.
- **Fix:** Wrap sync SDK calls in `asyncio.to_thread`/`run_in_executor`, or use the async SDK clients.
- **Done when:** AI calls don't block the loop.

### 98. Oi learning system never persists (lost on restart)
- **Severity:** P1
- **Location:** `oi/learning_system.py:485` (`save_data()` has zero callers; only `_user_profiles` is loaded)
- **Problem:** Interactions/feedback/patterns accumulate in memory and vanish on restart — undercutting the "self-improvement" premise.
- **Fix:** Call `save_data()` after each interaction or on an interval; load all state on startup. Better: back it with the DB.
- **Done when:** learning state survives restarts.

### 99. Competitive-learning reads the wrong API-key env var
- **Severity:** P1
- **Location:** `intelligence/competitive_learning.py:530` (reads `CLAUDE_API_KEY`; rest of the codebase uses `ANTHROPIC_API_KEY`)
- **Problem:** Throws on every call when only `ANTHROPIC_API_KEY` is set (the convention).
- **Fix:** Standardize on `ANTHROPIC_API_KEY` everywhere.
- **Done when:** the factory works with the standard env var.

### 100. DB auto-recovery drops ALL tables (data-loss risk)
- **Severity:** P0
- **Location:** `database/connection.py:402-413` (on `create_all` failure against a non-empty DB, runs `DROP TABLE ... CASCADE` on every table, no gate)
- **Problem:** A transient error during deploy could cascade into total data loss.
- **Fix:** Remove the auto-drop entirely; on schema error, fail loudly and require manual migration. Never auto-drop in prod.
- **Done when:** no code path can drop all tables automatically.

### 101. Silent SQLite fallback when `DATABASE_URL` unset
- **Severity:** P1
- **Location:** `database/connection.py:96-99`
- **Problem:** If `DATABASE_URL` is missing in prod, the app silently uses ephemeral SQLite → data vanishes on restart, no alert.
- **Fix:** In production, require `DATABASE_URL`; fail-fast if missing. SQLite only in explicit local/dev mode.
- **Done when:** prod refuses to boot on SQLite.

### 102. Second hand-rolled sqlite persistence layer (not durable on Render)
- **Severity:** P1
- **Location:** `database/product_history.py` (1219 lines, raw `sqlite3` to `data/product_history.db`, opens a new connection per call; `:514-515` hardcodes `rating: 4.5`, `orders: 1000`)
- **Problem:** A parallel persistence layer owning orders/deployments/notifications, wiped on every Render deploy, that also fabricates rating/orders defaults.
- **Fix:** Migrate this data to the Postgres/SQLAlchemy layer; delete the raw-sqlite DAL. Remove the fabricated defaults.
- **Done when:** order/deployment history is durable in Postgres and this file is gone.

### 103. A/B auto-implement-winner race condition
- **Severity:** P2
- **Location:** `testing/background_jobs.py` (`_auto_implement_winners` check-then-write, no lock)
- **Problem:** Can double-apply a winner and duplicate Shopify images.
- **Fix:** Use a DB lock/atomic status transition (e.g., `UPDATE ... WHERE status='pending'`).
- **Done when:** a winner can be applied at most once.

### 104. Inventory restock/history not idempotent + in-memory IDs
- **Severity:** P2
- **Location:** `inventory/routes.py:140-187` (restock orders in an in-memory list, id = `len()+1`), `historical_tracking.save_snapshot` (no uniqueness → duplicate rows skew averages)
- **Problem:** Race conditions, total loss on restart, duplicate snapshots.
- **Fix:** Persist to DB with real PKs; add uniqueness constraints on snapshots.
- **Done when:** restocks/snapshots are durable and de-duplicated.

### 105. "Remember me" checkbox does nothing
- **Severity:** P3
- **Location:** frontend `LoginForm.jsx:101` vs `useAuth.jsx:71` (arg swallowed into `retries` due to signature mismatch)
- **Problem:** UI affordance is silently inert.
- **Fix:** Align the function signatures; implement the remember-me behavior.
- **Done when:** the checkbox has an effect.

### 106. WooCommerce blocking I/O + broken error constructor
- **Severity:** P1
- **Location:** `platforms/woocommerce.py` (every method uses blocking `requests` inside `async def`; `PlatformAPIError(..., status_code=...)` kwarg the base class doesn't accept → TypeError masks real errors)
- **Problem:** Blocks the loop; real API errors become misleading TypeErrors.
- **Fix:** Use `httpx.AsyncClient`; fix the exception constructor to accept `status_code`.
- **Done when:** async-safe and errors surface correctly.

### 107. Amazon platform methods are stubs + blocking
- **Severity:** P1
- **Location:** `platforms/amazon.py` (4 of 9 methods hardcoded-failure stubs; `delete_product` fakes success via the broken `update_inventory`; blocking sync SDK in async)
- **Problem:** Amazon platform integration is not functional but partly presents as such.
- **Fix:** Implement or clearly mark Amazon as not-production-ready; make async-safe. (Coordinate with task 156.)
- **Done when:** behavior matches capability; async-safe.

### 108. Fake AWS SigV4 signing (Amazon SP-API 403s in prod)
- **Severity:** P1
- **Location:** `integrations/amazon_client.py:80-89` (docstring: "Simplified — use python-amazon-sp-api for production")
- **Problem:** Real requests get 403; the client can't work in production as written.
- **Fix:** Use `python-amazon-sp-api` or a correct SigV4 implementation.
- **Done when:** SP-API calls authenticate.

### 109. Naive timezone in the email auto-responder (quiet hours wrong)
- **Severity:** P1
- **Location:** `email_automation/ai_responder.py:93-96` (`is_operating_hours` uses naive `datetime.now().time()`, flat 7am-9pm, no weekend)
- **Problem:** On a UTC server (typical on Render) the "quiet hours" window is off by 4-5 hours vs the business's timezone. This path is live via `AutomationEngine` AI_REPLY.
- **Fix:** Use the pytz-based logic from `business_hours.py` (which is correct) everywhere; delete the naive version.
- **Done when:** one correct, timezone-aware business-hours check is used app-wide.

### 110. Harden email loop-prevention against self/spoofed threads
- **Severity:** P1
- **Location:** `email_automation/email_processor.py:210-254` (`is_customer_response = bool(references or in_reply_to)`)
- **Problem:** Any threading header satisfies "customer response," so a re-ingested own-reply or a spoofed `In-Reply-To` could restart the loop.
- **Fix:** Also verify the sender is not one of the system's own aliases and that the message isn't the bot's prior outbound; check direction, not just header presence.
- **Done when:** the bot cannot reply to its own messages under any header condition.

### 111. Webhook revenue double-counting on retries
- **Severity:** P1
- **Location:** `webhooks/webhook_utils.py:275-379` (`upsert_product_performance_from_order` docstring claims order-id dedup; code has none)
- **Problem:** Shopify webhook retries double-count revenue.
- **Fix:** Dedup by order id before incrementing performance metrics.
- **Done when:** replays don't inflate revenue.

---

# SECTION F — Dead Code & Unneeded Files (P2, delete)

> Confirm zero live importers with a repo-wide grep before deleting each. Deleting these removes a large class of "edited the wrong copy" bugs.

### 112. Delete `intelligence/autopilot.py`
- **Severity:** P2 — **Location:** `ospra_os/intelligence/autopilot.py` (556 lines, zero importers; the live one is `intelligence/auto_pilot.py`)
- **Fix:** Delete. **Done when:** gone and app still boots.

### 113. Delete `intelligence/product_description_generator.py`
- **Severity:** P2 — **Location:** 173 lines, zero callers. **Fix:** Delete.

### 114. Delete `intelligence/progress_flow.py`
- **Severity:** P2 — orphaned (zero importers). **Fix:** Delete (resolves task 65).

### 115. Delete `intelligence/grade_reasoning.py`
- **Severity:** P2 — orphaned. **Fix:** Delete (or wire it in if you actually want explainable grades — but currently dead).

### 116. Delete `learning/trend_velocity_detector.py`
- **Severity:** P2 — only re-exported in `learning/__init__.py`, never instantiated. **Fix:** Delete and remove the re-export.

### 117. Delete the entire `models/` package
- **Severity:** P2 — **Location:** `ospra_os/models/` (`competitor.py`, `customer.py`, `inventory.py`, `report.py`, `ad_schedule.py`) — each defines its own `declarative_base()`, zero real importers; live models live in `database/*_models.py`
- **Fix:** Delete the package. **Done when:** gone; confirm nothing imports `from ospra_os.models` / `from models`.

### 118. Delete `product_research/discovery.py`
- **Severity:** P2 — dead + buggy (`get_stats():386` references `self.reddit`, never set → AttributeError). Only reached via swallowed fallbacks in `main.py`. **Fix:** Delete; remove the dead fallback call sites in `main.py`.

### 119. Delete `product_research/pipeline.py`
- **Severity:** P2 — dead (only caller wraps it in a silent try/except in `admin/routes.py:35`). **Fix:** Delete; remove the caller.

### 120. Delete `product_research/intelligence_engine.py`
- **Severity:** P2 — dead + 100% fabricated (task 69). **Fix:** Delete.

### 121. Delete `product_research/scorer.py`
- **Severity:** P2 — orphaned. **Fix:** Delete (confirm no import).

### 122. Delete `actions/action_factory.py` and `actions/auto_pilot.py`
- **Severity:** P2 — dead (zero external imports; `undo_manager.py` is the only live file in `actions/`). **Fix:** Delete both.

### 123. Delete `jobs/scheduler.py`
- **Severity:** P2 — dead (start call commented out in `main.py:1566`, all job bodies are stubs). **Fix:** Delete; remove commented references.

### 124. Delete `observability/logging_config.py`
- **Severity:** P2 — dead but dangerous (calls `root_logger.handlers.clear()`; the live logger is `observability/logger.py`). **Fix:** Delete.

### 125. Delete `observability/posthog_client.py`
- **Severity:** P2 — zero call sites. **Fix:** Delete (or wire up PostHog if intended).

### 126. Delete `background_jobs/token_refresh_job.py`
- **Severity:** P2 — orphaned; the live token refresher is `api/aliexpress_token_scheduler.py`. **Fix:** Delete (after task 114 in Section H resolves storage).

### 127. Resolve the deprecated shims
- **Severity:** P2 — **Location:** `intelligence/tier_system.py` (deprecated → `core.tiers`), `intelligence/self_learning.py` + `learning/self_learning_engine.py` (deprecated → `HybridLearningEngine`)
- **Fix:** Update any remaining importers to the canonical modules, then delete the shims.

### 128. Delete dead frontend components
- **Severity:** P3 — **Location:** `OiChat.jsx`, `autopilot/AutopilotControls.jsx` (likely dead duplicates of live components). **Fix:** Confirm unrouted, delete.

### 129. Delete/guard dangerous one-off scripts
- **Severity:** P1 — **Location:** `scripts/delete_user.py:74` (hardcoded email, real `DELETE FROM users`, no confirm/env guard), `scripts/auto_create_store_pages.py:11` (hardcoded path to a non-existent sibling project → dead)
- **Fix:** Delete `auto_create_store_pages.py`; add a `--confirm` flag + env guard to `delete_user.py` or delete it.

### 130. Prune dead-code comment cruft in `main.py`
- **Severity:** P3 — ~150 lines of comments documenting already-removed endpoints. **Fix:** Delete the comment blocks.

### 131. Fix garbled emoji regex
- **Severity:** P3 — **Location:** `api/product_analysis_routes.py:785` (malformed character class mixing literal bracket-words). Harmless but broken. **Fix:** Delete the dead line (the following `#\w+` regex does the real work).

### 132. Remove theater test files
- **Severity:** P2 — **Location:** `tests/.../test_complete_system.py`, `test_amazon_adapter.py` (zero assertions, `except: print(...)`, pass even if server is down). **Fix:** Rewrite with real assertions or delete.

### 133. Remove stale coverage artifact
- **Severity:** P3 — **Location:** `coverage.json` (3MB, from April, committed, misleading 17.78%), `htmlcov/`. **Fix:** `git rm --cached`, add to `.gitignore`, regenerate on demand.

### 134. Remove committed `.DS_Store` files
- **Severity:** P3 — scattered throughout. **Fix:** `git rm --cached` all, add `.DS_Store` to `.gitignore`.

### 135. Clean up `oubon_site` leftovers
- **Severity:** P3 — dead `trycloudflare.com` demo tunnel; 3 near-duplicate TikTok OAuth callback HTML files. **Fix:** Remove the dead demo; consolidate to one callback file.

---

# SECTION G — Duplication & Consolidation (P2)

> The dominant architectural problem. For each: pick the ONE live implementation, wire all callers to it, delete the rest. Grep imports before deleting.

### 136. Consolidate the autopilot engines (3–4 → 1)
- **Location:** `intelligence/auto_pilot.py` (LIVE, via `api/autopilot_routes.py`), `intelligence/autopilot.py` (dead, task 112), `actions/auto_pilot.py` (dead, task 122)
- **Fix:** Keep `intelligence/auto_pilot.py`; move its in-memory state to the DB (task 148); delete the others.
- **Done when:** one autopilot engine, DB-backed.

### 137. Consolidate the 6 action executors → 1
- **Location:** `actions/action_factory.py`+`auto_pilot.py`, `intelligence/action_executor.py`, `oi/action_executor.py`, `services/action_executor.py`
- **Fix:** Choose the most complete (`services/action_executor.py` has real before/after state + platform calls); make it the single executor; route Oi/intelligence/actions callers to it; delete the rest. This also fixes tasks 79 and the fake-undo (task 138).
- **Done when:** one action-execution contract across the app.

### 138. Wire the live undo to the REAL executor
- **Location:** `actions/undo_manager.py` (all 5 handlers just log "Simulating..." and return success) — while a real implementation sits unused in `services/action_executor.py`
- **Fix:** Make undo call the real executor's undo (with real Shopify/Meta calls).
- **Done when:** undo actually reverses actions.

### 139. Consolidate the 3 deployment engines → 1
- **Location:** `deployment/unified_deployer.py` (dead scaffolding, task 81), `services/auto_deployer.py`+`services/product_deployer.py` (LIVE), `integrations/shopify_auto_deploy.py` (a 3rd path used by `main.py`)
- **Fix:** Standardize on `auto_deployer`+`product_deployer`; route `main.py`'s path through it; delete `unified_deployer.py`.
- **Done when:** one deployment path.

### 140. Consolidate the 3 AI client/router stacks → 1
- **Location:** `ai/model_router.py`, `ai/factory.py`+`ai/multi_provider_client.py`, `ml/model_router.py`+`ml/ai_client.py` (all live, 3 separate cost tables, none reconcile with `ai/cost_tracker.py`)
- **Fix:** Pick one router + one client; one MODELS/cost table; route every AI call through `ai/cost_tracker.track_usage`. Delete the others.
- **Done when:** one AI abstraction and one cost ledger.

### 141. Consolidate the 12 AliExpress signing functions → 1 module
- **Location:** 12 copies across 8 files (`api/aliexpress_oauth.py`, `api/aliexpress_affiliate_oauth.py`, `api/aliexpress_product_routes.py`, `api/aliexpress_token_refresh.py`, `aliexpress/ds_client.py` (×2), and more) in 3 incompatible algorithm families (HMAC-SHA256 no-prefix, HMAC-SHA256 path-prefixed, MD5-wrapped)
- **Problem:** At least one family signs requests incorrectly; changes must be made in 12 places.
- **Fix:** Create `ospra_os/aliexpress/signing.py` with the ONE correct implementation (verify against AliExpress's current spec); replace all 12 call sites.
- **Done when:** one signing function, all callers use it, requests verified working.

### 142. Consolidate the 3 AliExpress OAuth flows → 1
- **Location:** `aliexpress/oauth.py`, `api/aliexpress_oauth.py`, `api/aliexpress_affiliate_oauth.py` (90% duplicate; the CSRF state-check fix was applied to one but not the others)
- **Fix:** One parameterized handler (`api_type: "dropship"|"affiliate"`); apply the CSRF state verification uniformly.
- **Done when:** one OAuth handler with consistent CSRF protection.

### 143. Single AliExpress token storage (DB only)
- **Location:** DB (`database/aliexpress_tokens.py`) vs flat JSON (`api/aliexpress_token_refresh.py` reads/writes `.secrets/*.json`)
- **Problem:** Two incompatible stores that never sync; on Render redeploy the JSON files vanish, so the scheduled refresh silently no-ops while DB tokens expire.
- **Fix:** Use the DB store everywhere; delete the file-based path; point the scheduler at the DB.
- **Done when:** one durable token store; refresh works after redeploy.

### 144. Consolidate the 2 JWT systems → 1
- **Location:** `auth/jwt_auth.py` vs `auth/jwt_handler.py` (duplicate hash/verify/decode/blacklist; documented to have disagreed in prod)
- **Fix:** Keep one; update all importers; delete the other. Centralize token TTL constants.
- **Done when:** one JWT implementation.

### 145. Resolve the duplicate `ProductDiscoveryEngine` class name
- **Location:** `intelligence/product_discovery.py:621` (real, 7251-line engine) and `product_research/discovery.py:25` (dead stub, task 118)
- **Fix:** Delete the stub (task 118); the naming collision disappears. If both must exist, rename one.
- **Done when:** only one class by that name.

### 146. Unify the 3 `ShopifyClient` classes + add order/refund methods
- **Location:** `integrations/shopify/client.py` (products only), `services/shopify/client.py` (orders/analytics), `api/shopify_routes.py` (stub)
- **Fix:** One `ShopifyClient` with product AND order/refund methods (unblocks task 28). Delete the others.
- **Done when:** one client with full coverage.

### 147. Disambiguate the image generators
- **Location:** `integrations/ai_image_generator.py` (background removal), `media/ai_image_generator.py` (text-to-image), plus a same-named method in `services/image_processor.py`
- **Problem:** Not true duplicates (different jobs) but identical names invite confusion.
- **Fix:** Rename for clarity (e.g. `image_background_removal.py`, `image_generation.py`); fix the redundant local re-imports in `intelligence_core_routes.py`.
- **Done when:** names reflect distinct purposes.

### 148. Consolidate the 2 rate limiters
- **Location:** `security/production_security.py` (Redis-backed) vs `middleware/rate_limiting.py`/`security/rate_limiting.py` (in-memory `SensitiveEndpointRateLimiter`)
- **Problem:** In-memory limiter silently ineffective across multiple workers (brute-force protection divided by worker count).
- **Fix:** Standardize on the Redis-backed limiter for all sensitive endpoints; delete or back the in-memory one with Redis.
- **Done when:** one shared-state rate limiter.

### 149. Consolidate the 3 logging setups
- **Location:** `observability/logger.py` (live), `observability/logging_config.py` (dead, task 124), plus a third setup
- **Fix:** One logging config; delete the rest (both call `handlers.clear()` and would clobber each other).
- **Done when:** one logging setup.

### 150. Consolidate the 2 morning-brief pipelines
- **Location:** `intelligence/daily_brief.py` vs `intelligence/briefing_engine.py`
- **Fix:** Pick one; route the API to it; delete/merge the other.
- **Done when:** one briefing pipeline.

### 151. Consolidate the 2 CJ Dropshipping clients
- **Location:** `integrations/cj_dropshipping.py` vs `integrations/cj_dropshipping/client.py` (same class name)
- **Fix:** Keep the newer/complete one; update importers; delete the other.
- **Done when:** one CJ client.

### 152. Delete the in-memory Shopify OAuth flow
- **Location:** `api/shopify_routes.py` (in-memory) vs `api/shopify_oauth_routes.py` (DB-backed, correct)
- **Fix:** Delete `shopify_routes.py`'s connect/callback/stores endpoints (task 14); keep the DB-backed flow.
- **Done when:** one Shopify OAuth path.

### 153. De-duplicate the frontend Sidebar
- **Location:** triplicated in `Layout.jsx`, `Dashboard.jsx`, `Settings.jsx` (already drifted — Settings missing 2 nav items)
- **Fix:** Extract one `<Sidebar>` component; use it everywhere.
- **Done when:** one Sidebar source.

### 154. Fix the colliding `paginated_response` helpers
- **Location:** `utils/api_response.py` and `utils/pagination.py` (two functions, same name, different signatures, both exported from `utils/__init__.py`)
- **Fix:** Keep one; update callers; remove the other export.
- **Done when:** one pagination helper.

### 155. Consolidate the duplicate `/upgrade` endpoints
- **Location:** `api/user_routes.py` `/upgrade` vs `payments`/`subscription` `/upgrade` (two LemonSqueezy checkout builders)
- **Fix:** One checkout-URL builder; route both callers to it.
- **Done when:** one upgrade path.

### 156. Use `schemas.py` instead of re-defining models locally
- **Location:** `api/marketing_routes.py` redefines `MarketingAngleRequest` etc. that already exist in `api/schemas.py`
- **Fix:** Import from `schemas.py`; delete the local duplicates.
- **Done when:** shared models live in one place.

### 157. Consolidate the velocity/trend systems (3–4 → 1)
- **Location:** `intelligence/velocity_detector.py`, `intelligence/momentum_tracker.py`, `learning/trend_velocity_detector.py` (dead), `intelligence/trend_trajectory.py` (newer, more rigorous, written to replace them but not wired)
- **Fix:** Adopt `trend_trajectory.py` as canonical; migrate callers; delete the others (fixes tasks 55, 116).
- **Done when:** one velocity/trend implementation.

### 158. Split the 7251-line `product_discovery.py`
- **Location:** `intelligence/product_discovery.py` (one class, ~90 methods)
- **Fix:** Split by concern: source connectors / scoring engine / matching-and-dedup / niche gating. No behavior change, just modularize for testability.
- **Done when:** the engine is several focused modules.

---

# SECTION H — Persistence & Architecture (P1/P2)

### 159. Move ephemeral local state to durable storage
- **Location:** `services/oi_alerts.py` (in-memory), `intelligence/auto_pilot.py` (in-memory safety limits/daily counters), `advertising/scheduler.py` (task 23)
- **Problem:** State (alerts, autopilot daily spend/limits) resets on every restart/deploy and isn't shared across workers — silently defeating the safety limits.
- **Fix:** Back all of it with the DB (Postgres).
- **Done when:** state survives restarts and is shared across workers.

### 160. Persist generated/processed images to cloud storage
- **Location:** `services/image_processor.py:294` (`data/processed_images`), `services/image_storage.py:42` (`data/images`) — local paths, wiped on Render; Cloudinary/S3 code exists but gated off (`enable_cloud_upload=False`)
- **Fix:** Enable cloud upload by default in prod; store/serve from the cloud URL.
- **Done when:** images persist across deploys.

### 161. Fix the orphaned `declarative_base()` instances
- **Location:** `database/template_models.py:18`, `database/tiktok_tokens.py:26`, `database/aliexpress_tokens.py:12`, `database/cached_products.py:14` — each its own Base, not created by normal startup
- **Problem:** These tables won't be created by the app's normal `create_all` path unless separately targeted.
- **Fix:** Use the single shared `database/base.py` `Base` for all models.
- **Done when:** all models share one metadata; tables create on startup.

### 162. Make schema management coherent (one system)
- **Location:** mixed `Base.metadata.create_all()` + `migrations/*.py` + `database/migrations/*.py` + `alembic/` (and `alembic/env.py` appears missing); migration 003 documents a real prod incident from this
- **Fix:** Standardize on Alembic; restore `alembic/env.py`; stop calling `create_all` in prod; convert manual scripts to migrations.
- **Done when:** schema changes flow through one migration system.

### 163. Make tenant isolation enforced, not optional
- **Location:** `tenancy/dependencies.py:18` (unfiltered `get_db` importable alongside `get_tenant_db`); `tenancy/context.py:48-54` (`can_access_store` always returns True); `tenancy/middleware.py:196-222` (accepts client `store_id`, no ownership check); `tenancy/dependencies.py:111-139` (`require_store` doesn't re-verify); `tenancy/queries.py:399-413` (`bulk_update_mappings` no tenant filter), `:183-186,461-463` (raw_session/execute unguarded bypass); `tenancy/audit.py:254-328` (no authz on `tenant_id`)
- **Problem:** For a multi-tenant SaaS this is the make-or-break: a single route using `get_db` or `require_store` is a silent cross-tenant leak with no error.
- **Fix:** Implement real ownership checks in `can_access_store`; verify `store_id`/`tenant_id` ownership in middleware/deps; remove/guard the raw bypasses; add a lint/test that fails if a route uses the unfiltered session. Re-verify `is_admin`/`is_superuser` against the DB, not just JWT claims.
- **Done when:** tenant A provably cannot read/write tenant B's data via any route; a test enforces it.

### 164. Close the self-learning loop (or stop advertising it)
- **Location:** write side real (`learning/hybrid_learning_engine.py`), but `get_adjusted_score()` has no automated caller in discovery→scoring→deploy
- **Problem:** The flagship "self-learning adjusts future recommendations" is not happening end-to-end.
- **Fix:** Call `get_adjusted_score()` from the scoring/deployment path so learned weights actually affect recommendations; add a test proving a recorded outcome changes a future score.
- **Done when:** outcomes measurably change future scoring.

---

# SECTION I — Scheduler Sprawl (P2)

### 165. Consolidate to one scheduling system
- **Location:** Celery Beat (`celery_app.py`/`tasks/`), APScheduler (`background_jobs/`), `jobs/scheduler.py` (dead), `jobs/schedule_processor.py` (live loop), `threading.Thread` loops in `main.py`, `api/aliexpress_token_scheduler.py`
- **Problem:** 5–6 overlapping schedulers; several jobs are double-owned.
- **Fix:** Pick Celery Beat as the single system (it's the apparent intended one); migrate the APScheduler/thread/loop jobs into it; delete the rest.
- **Done when:** one scheduler runs all recurring work.

### 166. Fix double-scheduled jobs
- **Location:** product discovery (`background_jobs/auto_discovery.py` vs `tasks/product_tasks.py` stub vs `tasks/catalog_warm.py` cron), product monitoring (`background_jobs/product_monitor.py` vs `tasks/product_tasks.py` stub), token refresh (`background_jobs/token_refresh_job.py` dead vs `api/aliexpress_token_scheduler.py` live)
- **Problem:** Once a stub is completed, two systems run the same job → double execution.
- **Fix:** Delete the duplicate/stub implementations; keep one per responsibility.
- **Done when:** each recurring job has exactly one owner.

### 167. Fix Celery Beat clock collisions
- **Location:** 2:00 AM UTC (`learning_tasks.analyze_learnings` vs `feedback_tasks.evaluate_outcomes_task`), 3:00 AM UTC (`analytics_tasks.cleanup_old_data` vs `feedback_tasks.process_learning_task`)
- **Fix:** Stagger the schedules.
- **Done when:** no two heavy jobs start at the same minute.

### 168. Add `max_instances` to interval jobs
- **Location:** `background_jobs/token_refresh_job.py` (no `max_instances`)
- **Fix:** Set `max_instances=1`, `misfire_grace_time` (consistent with `auto_discovery.py`). (Moot if deleted per task 126.)
- **Done when:** no job can overlap itself.

### 169. Gate the stubbed Celery action executor
- **Location:** `tasks/action_tasks.py` (`execute_action:34` fully stubbed, no approval/idempotency)
- **Problem:** Poised to double-execute real price/inventory/ad actions once its dispatch TODO is filled.
- **Fix:** Route it through the one canonical action executor (task 137) with idempotency + approval before implementing dispatch.
- **Done when:** it can't double-execute and respects approvals.

---

# SECTION J — Config, Ops & Frontend Hygiene (P3)

### 170. Harden the root Dockerfile
- **Location:** root `Dockerfile` (runs as root; stale "Oubon MailBot" comment; not used by Render, which uses `runtime: python`)
- **Fix:** Add a non-root user; fix/remove the stale comment; delete the Dockerfile if truly unused, or make it the real build.
- **Done when:** container runs as non-root or the file is removed.

### 171. Move JWT out of localStorage (or accept the risk explicitly)
- **Location:** frontend `services/auth.js:34-35,108-111` (access + refresh tokens in `localStorage`)
- **Problem:** Any XSS steals a long-lived refresh token.
- **Fix:** Prefer HttpOnly, Secure, SameSite cookies for the refresh token; keep only a short-lived access token in memory. If keeping localStorage, document the accepted risk and shorten refresh TTL.
- **Done when:** refresh tokens aren't readable by JS, or the risk is explicitly owned.

### 172. Remove console logging and fix port fallbacks in the frontend
- **Location:** 124 `console.*` calls shipped to prod; inconsistent localhost fallback (8000 vs 8001) across 5 files
- **Fix:** Strip `console.*` in the production build (or a logger util); unify the dev API port.
- **Done when:** no stray console logs in prod; one dev port.

### 173. Implement or remove the frontend rate-limit stub
- **Location:** `services/api.js` `getRateLimitStatus()` (hardcoded stub)
- **Fix:** Wire to a real endpoint or remove.
- **Done when:** it reflects real state or is gone.

### 174. Fix the rate limiter that's off unless `ENVIRONMENT=production`
- **Location:** `middleware/rate_limiter.py` (disabled unless the env var is exactly "production")
- **Problem:** Staging/self-hosted get zero discovery rate limiting.
- **Fix:** Enable by default; allow explicit opt-out, not opt-in.
- **Done when:** rate limiting is on outside prod too.

### 175. Environment-gate debug endpoints
- **Location:** `api/image_generation_routes.py` debug endpoints (`/debug-url-hash`, `/list-cached-files`, `/cache-index`, etc. — leak filesystem paths)
- **Fix:** Wrap in `if DEBUG` / admin-only; disable in prod.
- **Done when:** debug endpoints are off in prod.

### 176. Reconcile dependency manifests
- **Location:** `requirements.txt` vs `pyproject.toml` vs `uv.lock`
- **Fix:** Pick one source of truth (uv/pyproject recommended); generate the rest; ensure Render installs the intended set.
- **Done when:** one authoritative dependency list.

### 177. Remove weak default in docker-compose
- **Location:** `docker-compose.yml` `FLOWER_BASIC_AUTH` default `admin:ospra123`
- **Fix:** Require it from env; no default. (Dev-only file, but still.)
- **Done when:** no default credential.

---

# SECTION K — Tests & Verification (P1/P2)

### 178. Add money-path safety tests
- **Fix:** After fixing Section B, add tests: replaying a fulfillment event places one order (task 16); budget optimizer never exceeds `budget_limit` (task 21); refund flow runs guardrails without crashing (task 28); payment webhook replay is a no-op and a DB failure returns 5xx (task 27).
- **Done when:** these tests exist and pass.

### 179. Add a tenant-isolation enforcement test
- **Fix:** A test that fails if any route uses the unfiltered `get_db`; an integration test proving tenant A can't read tenant B's stores/orders/audit logs (task 163).
- **Done when:** cross-tenant access is covered by a failing-if-broken test.

### 180. Add auth-coverage tests for the IDOR fixes
- **Fix:** For each endpoint in Section C, assert 401/403 for unauthenticated/unauthorized callers.
- **Done when:** every Section C fix has a regression test.

### 181. Re-baseline coverage honestly
- **Fix:** Regenerate coverage after cleanup; keep `--cov-fail-under` meaningful; don't commit `coverage.json` (task 133).
- **Done when:** coverage reflects the current suite.

---

# Quick Index (by priority)

**P0 — do first (security, money, legal, data-loss):** 1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 14, 16, 17, 18, 19, 21, 22, 23, 27, 28, 32, 33, 34, 35, 36, 38, 42, 43, 44, 45, 48, 50, 100, 101.

**P1 — serious (correctness, trust, blocking calls, fake data in key surfaces):** 10, 12, 13, 15, 20, 24, 25, 26, 29, 30, 31, 37, 39, 40, 41, 46, 47, 49, 53, 54–74, 76, 77, 79, 83–92, 95, 96, 97, 98, 99, 102, 106, 107, 108, 109, 110, 111, 129, 163, 164, 178, 179, 180.

**P2 — structural (dead code, duplication, architecture, schedulers):** 51, 65, 69, 75, 78, 80, 81, 82, 93, 94, 103, 104, 112–128, 130, 131, 132, 136–162, 165–169, 181.

**P3 — hygiene:** 52, 105, 128, 133, 134, 135, 170, 171, 172, 173, 174, 175, 176, 177.

---

## Notes for the executor
- Work top-down within each priority band. Do NOT create new parallel implementations — consolidate onto the live one.
- Before deleting any file/function, run a repo-wide import grep to confirm zero live callers; if callers exist, migrate them first.
- After each change, run the test suite; add a regression test for every P0/P1 fix.
- Line numbers may have drifted — locate code by the described symbol/string, not the number alone.
- Treat every "auto" feature (auto-fulfill, auto-deploy, auto-budget, auto-reply/refund) as OFF in production until its section is fully fixed and tested.

