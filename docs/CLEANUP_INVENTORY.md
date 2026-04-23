# Ospra OS — Cleanup Inventory (Pass 0)

**Generated:** 2026-04-23
**Mode:** read-only — no files changed
**Scope:** every tracked file in the repo
**Goal:** classify, not delete. Nothing is removed in Pass 0.

**Safety rails (non-negotiable):**
- `ospra_os/email_automation/` + `ospra_os/gmail/` — email automation is a core feature, preserved.
- Any file with `oubon` / `Oubon` / `OUBON` — Oubon Shop storefront, preserved.
- Anything reachable from `ospra_os/main.py` — treated as live until proven otherwise.

---

## 1. Headline numbers

| Metric | Tracked | Reality |
|---|---|---|
| Total files in git | 4,068 | — |
| Actually the project | **832** | — |
| Junk (`.venv/` committed) | **3,236** | gitignored but committed-before-rule |
| Python files | 2,274 → **605** after excl `.venv` | 487 inside `ospra_os/` |
| Markdown | 57 | 43 under `docs/`, 14 elsewhere |
| JS/TS | 56 | mostly `frontend/` |
| Uncommitted changes | **40+ modified, 5 deleted** | must commit or stash before Pass 1 |

**Top-level tracked directories (excluding `.venv/`):**

| Dir | Tracked files |
|---|---|
| `ospra_os/` | 492 |
| `frontend/` | 98 |
| `scripts/` | 52 |
| `tests/` | 51 |
| `docs/` | 43 |
| `archive/` | 20 |
| `data/` | 9 |
| `website/` | 7 |
| `migrations/` | 5 |
| root files | ~50 |

---

## 2. CRITICAL tracked junk (Pass 1 removes)

These files are committed to git but listed in `.gitignore` — they were added *before* the ignore rule existed.

| Path | Size / Count | Why it shouldn't be tracked |
|---|---|---|
| `.venv/` | 3,236 files | Python virtualenv. Gitignored `line 12`. Bloats repo. |
| `.coverage` | 167 KB binary | Coverage artifact. Gitignored `*.log` family pattern not catching. |
| `coverage.json` | 2.8 MB | Coverage export. |
| `frontend/package-lock 2.json` | ~? | Finder duplicate of `package-lock.json` |
| `ospra_os/data/ospra 2.sqlite` | ~? | Finder duplicate of `ospra.sqlite` |
| `frontend/audit_screenshots/` | 19 PNGs | One-off visual audit output |
| `frontend/visual_audit_data.json` | ~? | " " |
| `frontend/visual_audit_report.md` | ~? | " " |
| `.aider.input.history` | small | Aider chat history, gitignored but tracked |

**`.venv/` alone dominates every metric.** Removing it is Pass 1 step 1. No runtime risk — it's rebuilt from `requirements.txt` / `uv.lock`.

---

## 3. Root-directory clutter

Files sitting at project root that should move or go away.

### 3a. Root-level tests (→ move to `tests/`)

- `test_apify_account.py` — apify smoke test
- `test_product_discovery.py` — discovery smoke test
- `test_abtesting_api.sh` — shell test
- `test_abtesting_integration.sh`
- `test_trash_data.sh`

### 3b. Root-level one-shot scripts (→ `scripts/` or delete)

- `backup_databases.py` — DB backup. Keep but move to `scripts/`.
- `fix_legacy_imports.py` — one-shot rewriter. **Candidate for archive** — if the legacy imports are already fixed, this is done.
- `remove_emojis.py` — one-shot text cleaner. Probably done, archive candidate.
- `create_grok_package.sh` — references Grok. We've moved off Grok for Twitter → probably obsolete. Verify.

### 3c. Multiple start scripts (consolidate)

- `start-local.sh`
- `start_backend.sh`
- `start_dev_server.sh`
- `scripts/START_CLEAN.sh`
- `scripts/START_SERVERS.sh`
- `scripts/STOP_SERVERS.sh`
- `scripts/RESTART_BACKEND.sh`
- `scripts/RESTART_BACKEND_WITH_ENV.sh`
- `scripts/RESTART_FRONTEND.sh`

**Nine separate shell scripts that overlap.** Pass 1 candidate: collapse into one `scripts/run.sh` with subcommands (`start`, `stop`, `restart`).

### 3d. Runtime state that shouldn't be in the repo

- `deployed_products.json` — deployment state
- `products_to_ship.json` — queue state
- `multi_store.db` (11 MB), `ospra_os.db` (18 MB), `oubon_store.db` (2.5 MB), `ospra_os.db-shm`, `ospra_os.db-wal` — SQLite databases

Gitignore has `*.db` and `*.sqlite` → **these were tracked before the rule**. Same pattern as `.venv/`. Pass 1 untracks them.

---

## 4. `scripts/` directory audit

**52 tracked files.** Breakdown:

### 4a. Legitimate scripts (keep)

- `aliexpress_oauth_helper.py`
- `init_db.py`, `migrate_db.py`, `migrate_stores_table.py`
- `populate_products.py`
- `auto_create_store_pages.py`
- `seed_learning_from_shopify.py`
- `utilities/init_database.py`, `utilities/migrate_add_tier_fields.py`, `utilities/run_email_check.py`, `utilities/run_migrations.py`
- `start_g4_celery.sh`

### 4b. Task verification tests (keep — these are the scripts the task list points to)

- `test_aliexpress_signal.py` (Task #19 ✓)
- `test_stability_enhancer.py` (Task #9 ✓)
- `test_ai_analysis_variance.py`, `test_ai_images.py`, `test_caption_variance.py`
- `test_score_variance.py`, `test_sentiment_refresher.py`, `test_trend_discovery.py`
- `test_full_discovery.py`, `test_full_integration.py`, `test_all_sources.py`
- `test_multi_user_learning.py`, `test_postgresql_migration.py`, `test_scalable_memory.py`
- `test_live_email.py` ← **preserve** (email automation)
- `verify_discovery_system.py`, `verify_learning_pipeline.py`, `verify_webhooks.py`
- `smoke_test_deployment.py`, `e2e_test.py`

### 4c. One-shot audit scripts (Pass 2 candidate to archive)

These scripts were each written to answer a one-time question. If they served their purpose, they belong in `archive/`:

- `audit_app_directory.py`
- `audit_imports.py`
- `audit_intelligence.py`
- `audit_models.py`
- `audit_project_imports.py`
- `audit_routes.py`
- `audit_sentiment.py`
- `debug_scoring.py`
- `diagnose_cj.py` — Task #7 completed, probably done
- `shopify_store_audit.py`
- `split_models.py` — one-shot refactor
- `add_shopify_router.py` — one-shot add
- `cleanup_obsolete_files.sh` — meta-cleanup script
- `fix_dependencies.sh`
- `delete_user.py` — dangerous, confirm usage

### 4d. `scripts/old_tests/` — explicit archive candidate

- `init_email_tables.py`
- `migrate_gmail_to_db.py`
- `test_ai_context_awareness.py`
- `test_ai_integration.py`

Directory is literally named `old_tests/`. Move to `archive/` or delete entirely.

---

## 5. `frontend/` clutter

### Root-level frontend junk (Pass 5 removes)

| File | Why it's junk |
|---|---|
| `ADD_STORE_MODAL_INTEGRATION_EXAMPLE.tsx` | Example code, not wired |
| `AI_SETTINGS_INTEGRATION_EXAMPLE.tsx` | " " |
| `STORE_SELECTOR_INTEGRATION_EXAMPLE.tsx` | " " |
| `DEBUG_API.html` | Dev debug page |
| `FIX_DASHBOARD_NOW.html` | Emergency fix page, presumably done |
| `FIX_BLANK_PAGE.sh` | " " |
| `FIX_REACT_TYPES.sh` | " " |
| `FORCE_RELOAD.html` | Dev utility |
| `DIAGNOSE.sh` | Diagnostic, ad-hoc |
| `test.html` | Bare test page |
| `update_remaining.sh` | One-shot update script |
| `visual_audit_report.md` | One-off audit output |
| `visual_audit_data.json` | " " |
| `audit_screenshots/` (19 PNGs) | " " |
| `package-lock 2.json` | Finder duplicate |

### Vite config duplicate
- `frontend/vite.config.js` (deleted in working tree)
- `frontend/vite.config.ts` (active)

Working tree has correctly removed `.js` — commit will finalize.

---

## 6. `docs/` audit

### 6a. Top-level `docs/` (43 tracked .md files)

Most useful. Flagged as potentially obsolete (need user confirmation in Pass 3):

- `INTELLIGENCE_AUDIT_DEC2024.md` — dated audit, likely superseded
- `T2_MIGRATION_COMPLETE.md` — migration done, archive?
- `T7_API_CONSOLIDATION.md` — consolidation done, archive?
- `G4_ACTIVATION_GUIDE.md`, `G4_COMPLETION_SUMMARY.md`, `G4_FEEDBACK_LOOP_IMPLEMENTATION.md`, `G4_IMPLEMENTATION_STATUS.md`, `G4_PHASE_4_COMPLETE.md` — 5 "G4" docs, consolidate?
- `DEPLOYMENT_AI_AUDIT.md` — audit snapshot
- `APIFY_CLEANUP.md` — action doc, done?
- `TASK_20_TWITTER_APIFY_EVALUATION.md` — Task #20 done, archive

### 6b. `docs/archive/` (4 files)

- `APIFY_CONFIGURATION.md`
- `GMAIL_OAUTH_SETUP.md`
- `OSPRA_OS_AI_AUTOMATION.md`
- `UNIFIED_DISCOVERY_API.md`

Already archived — leave unless user says otherwise.

---

## 7. `ospra_os/` subpackage census (487 Python files)

Sorted by size. No deletion candidates in Pass 0 — flagged for SaaS modularity audit in Pass 4.

| Subpackage | Files | Role | Status |
|---|---|---|---|
| `intelligence/` | 53 | product discovery, scoring, AI analysis | **core** |
| `api/` | 50 | FastAPI routes | **core** |
| `product_research/` | 32 | connectors layer (Amazon, AE, Reddit, etc.) | **core** |
| `integrations/` | 26 | Shopify, CJ, Stability, AI providers | **core** |
| `database/` | 26 | SQLAlchemy models, migrations | **core** |
| `email_automation/` | 24 | **EMAIL AUTOMATION — DO NOT TOUCH** | **protected** |
| `services/` | 23 | product_deployer, image_processor, etc. | **core** |
| `ai/` | 14 | provider abstraction | **core** |
| `learning/` | 12 | feedback loop, RLHF bits | check live |
| `analytics/` | 12 | dashboards | **core** |
| `routers/` | 10 | API mounting | **core** |
| `inventory/` | 10 | stock mgmt | check live |
| `advertising/` | 10 | ad integrations (Meta, Google, TikTok) | check live |
| `testing/` | 9 | test utilities | keep |
| `tasks/` | 9 | Celery tasks | **core** |
| `security/` | 9 | auth, encryption | **core** |
| `observability/` | 8 | tracing | keep |
| `core/` | 8 | config | **core** |
| `background_jobs/` | 8 | scheduler jobs | **core** |
| `utils/` | 7 | helpers | **core** |
| `reports/` | 7 | reporting | check live |
| `platforms/` | 7 | platform abstractions | check |
| `oi/` | 7 | "OI" chat / intelligence | check |
| `models/` | 7 | pydantic schemas | **core** |
| `middleware/` | 7 | FastAPI middleware | **core** |
| `tenancy/` | 6 | multi-tenant isolation | **core for SaaS** |
| `monitoring/` | 6 | metrics | keep |
| `auth/` | 6 | auth | **core** |
| `ml/` | 5 | ML models | check live |
| `federated/` | 5 | federated learning? | check |
| `whitelabel/` | 4 | white-label | check |
| `webhooks/` | 4 | webhook handlers | **core** |
| `notifications/` | 4 | alerts | check |
| `media/` | 4 | media handling | check |
| `jobs/` | 4 | job queue | check (overlap with tasks/?) |
| `actions/` | 4 | auto-pilot actions | **core** |
| `waitlist/` | 3 | launch waitlist | keep if live |
| `payments/` | 3 | Lemon Squeezy hooks | **core for SaaS** |
| `onboarding/` | 3 | user onboarding | **core** |
| `fulfillment/` | 3 | order fulfillment | **core** |
| `dashboard/` | 3 | dashboard | keep |
| `aliexpress/` | 3 | AE routes | **core** |
| `voice/` | 2 | voice? | verify live |
| `tiktok/` | 2 | TikTok integration | verify live |
| `subscription/` | 2 | sub logic | **core** |
| `scraping/` | 2 | general scraping | check vs product_research |
| `gmail/` | 2 | **GMAIL — DO NOT TOUCH** | **protected** |
| `deployment/` | 2 | deploy helpers | check |
| `admin/` | 2 | admin panel | keep |
| `scheduler/` | 1 | task scheduler | check vs tasks/ |
| `research/` | 1 | research? | check vs product_research |
| `forecaster/` | 1 | forecasting | check live |
| `connectors/` | 1 | connectors? | check vs product_research |

**Potential overlap/duplication flagged (Pass 2):**
- `tasks/` vs `jobs/` vs `scheduler/` vs `background_jobs/` — four scheduler-adjacent dirs
- `product_research/` vs `research/` vs `scraping/` vs `connectors/` — four research/scraping dirs
- `services/image_processor.py` vs `integrations/ai_image_generator.py` — two image pipelines (confirmed in Task #9 — Stability vs rembg)

---

## 8. Duplicate filename analysis

**225 unique duplicate names** across ospra_os/ — mostly benign:

- `__init__.py` × 73 — expected
- `routes.py` × 25 — expected (per-module routes)
- `client.py` × 5, `base.py` × 5 — normal
- `scheduler.py` × 3 — **investigate overlap**
- `middleware.py` × 3
- `dependencies.py` × 3
- `action_executor.py` × 3 — **investigate**
- `model_router.py` × 2
- `inventory.py` × 2
- `image_processor.py` × 2 — **confirmed Task #9 overlap**

Flagged for Pass 2 import-graph review.

---

## 9. Email automation footprint (preserved)

Explicitly preserved across all cleanup passes:

- `ospra_os/email_automation/` (24 files)
  - `ai_responder.py`, `analytics_routes.py`, `automation_engine.py`, `automation_routes.py`
  - `business_hours.py`, `email_action_executor.py`, `email_processor.py`, `email_sender.py`
  - `email_sync.py`, `gmail_client.py`, `oauth/`, `policies.py`, `refund_processor.py`
  - `rules.py`, `settings_routes.py`, `smart_reply.py`, `sync_routes.py`
- `ospra_os/gmail/` (2 files) — `routes.py`, oauth
- `scripts/test_live_email.py` — live email smoke test
- `scripts/utilities/run_email_check.py`
- `scripts/old_tests/init_email_tables.py`, `migrate_gmail_to_db.py` — pre-existing archive candidates

---

## 10. Oubon footprint (preserved)

13 Python files reference Oubon. Each will be audited in-place during Pass 4 (SaaS modularity) — Oubon references stay intact unless user explicitly approves each change:

- `ospra_os/intelligence/product_discovery.py`
- `ospra_os/intelligence/opportunity_scorer.py`
- `ospra_os/integrations/cj_dropshipping/client.py`
- `ospra_os/integrations/amazon_api.py`
- `ospra_os/product_research/connectors/social/amazon_reviews.py`
- `ospra_os/gmail/routes.py`
- `ospra_os/aliexpress/routes.py`
- `ospra_os/api/aliexpress_product_routes.py`
- `ospra_os/database/init_multi_store.py`
- `ospra_os/core/settings.py`
- `ospra_os/ai/response_cache.py`
- `ospra_os/email_automation/policies.py`
- Docs: `INIT_MIGRATION_GUIDE.md`, `MULTI_STORE_API.md`, `backup_databases.py`, `README.md`, etc.

---

## 11. Pending changes (must resolve before Pass 1)

`git status` shows **40+ modified and 5 deleted files** in the working tree — uncommitted work. Includes:

**Modified (live code):**
- `ospra_os/actions/auto_pilot.py`
- `ospra_os/ai/providers/claude.py`
- `ospra_os/api/*` — 13 route files modified
- `ospra_os/background_jobs/auto_discovery.py`
- `ospra_os/database/__init__.py`, `action_models.py`, `connection.py`
- `ospra_os/integrations/ai_image_generator.py`, `cj_dropshipping.py`, etc.
- `ospra_os/intelligence/ai_product_analyzer.py`
- `frontend/src/components/*` (5 files), `services/api.js`, `services/auth.js`

**Deleted:**
- `frontend/public/test-api-direct.html`
- `frontend/public/vite.svg`
- `frontend/src/components/auth/ProtectedRoute.jsx`
- `frontend/src/components/dashboard/Dashboard.jsx`
- `frontend/vite.config.js`
- `ospra_os/api/auto_pilot_routes.py`
- `ospra_os/database/actions_models.py`

**User action required before Pass 1:** commit these (if in-flight) or stash them, so Pass 1 starts on a clean tree.

---

## 12. Pass plan (reminder)

| Pass | Scope | Risk | Reversible? |
|---|---|---|---|
| **0** | Inventory only — this doc | none | n/a |
| **1** | Hygiene: remove `.venv/`, tracked DBs, junk files, consolidate start scripts | low | yes (git) |
| **2** | Dead module removal via import-graph | medium | yes (git) |
| **3** | Docs pruning | low | yes (git) |
| **4** | SaaS modularity — tenant isolation audit | high | yes (git) |
| **5** | Frontend cleanup — integration examples, debug HTML | low | yes (git) |
| **6** | Test consolidation — root tests into `tests/` | low | yes (git) |

Tests run at the start of each pass and after any deletion. No pass proceeds until the previous one is committed and verified.
