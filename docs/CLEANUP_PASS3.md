# Pass 3 — Docs Pruning & Consolidation

**Method:** Inventory every `.md` in the repo, separate live operational docs from completion reports / point-in-time audits / superseded migration plans. Archive (don't delete) the historical ones so the link history survives. Rewrite the two top-level docs that misrepresented the project.

**Scope:** 56 markdown files across `docs/`, `docs/guides/`, `docs/archive/`, plus root-level `README.md` / `CLAUDE.md` and a handful of subpackage READMEs.

**Result:** Top-level `docs/` shrunk from **35 live docs to 21**. Archive grew from 4 to 18 indexed historical docs. README + CLAUDE rewritten to match what the codebase actually is.

---

## 3a — Archive 13 completed/dated docs

Moved to `docs/archive/`. Each had served its purpose; none reflects current state.

### G4 feedback-loop project (5 files, all dated 2025-12-12)
- `G4_IMPLEMENTATION_STATUS.md`
- `G4_COMPLETION_SUMMARY.md`
- `G4_ACTIVATION_GUIDE.md`
- `G4_PHASE_4_COMPLETE.md`
- `G4_FEEDBACK_LOOP_IMPLEMENTATION.md`

The G4 feedback loop is live in production. Code lives in `ospra_os/learning/`, `ospra_os/database/performance_models.py`, `ospra_os/api/feedback_routes.py`. Five separate "what we built" reports about the same project don't add value beyond the code itself.

### app/ → ospra_os/ migration (2 files)
- `T2_MIGRATION_COMPLETE.md`
- `app_migration_plan.md`

The `app/` directory no longer exists in the repo (verified). All code is under `ospra_os/`.

### One-shot audits (6 files)
- `T7_API_CONSOLIDATION.md` — analysis was the input to cleanup Pass 2
- `routes_audit.md` — point-in-time route inventory (60 lines)
- `INTELLIGENCE_AUDIT_DEC2024.md` — capability audit, superseded by current cleanup work
- `DEPLOYMENT_AI_AUDIT.md` — Dec 2025 deployment audit
- `APIFY_CLEANUP.md` — completed action doc
- `TASK_20_TWITTER_APIFY_EVALUATION.md` — Grok vs. Apify decision memo (decision shipped)

Added `docs/archive/README.md` indexing every archive entry with a one-line "why it's here" so future readers don't waste time re-reading historical docs as if they were current.

---

## 3b — Rewrite README.md and CLAUDE.md

Both docs misrepresented the project.

**README.md (was 426 lines / now 159):**
- Linked to 7 docs that don't exist (`LEVEL3_AI_STATUS.md`, `QUICK_START.md`, `RUNTIME_ERROR_FIXES_COMPLETE.md`, `LUCIDE_ICON_FIX_COMPLETE.md`, `DATA_STRUCTURE_FIX_COMPLETE.md`, `TIKTOK_INTEGRATION_COMPLETE.md`, `WEBSITE_COMPLETE.md`).
- Linked to 2 missing scripts (`scripts/TEST_LEVEL3_AI.sh`, `scripts/TEST_PRODUCTS.sh`).
- Documented a "Legacy MailBot on port 8000" entry point that doesn't exist (root-level `main.py` was deleted in the T2 migration).
- Directory tree showed `app/` which is gone.
- Headline framing was "Level 1/2/3 AI" rather than what the app actually does (discovery + sentiment + Shopify deployment + Gmail automation).

New README:
- Documents the actual feature set (discovery, sentiment three-tier, AI grading, Shopify deployment, email automation, G4 feedback loop, LemonSqueezy billing).
- Quick start uses `./scripts/run.sh` (the consolidated dev script from Pass 1 — replaces the 9 overlapping start/stop scripts).
- Doc index only links to files that exist after Pass 3a archival.
- Real env var list including LemonSqueezy + Apify + CJ.

**CLAUDE.md (was 143 lines / now 102):**
- Was describing "Oubon MailBot" with an `app/` directory architecture and two FastAPI apps (root `main.py` legacy + `ospra_os/main.py`).
- Carried no standing rules.

Rewritten to:
- Document Ospra OS architecture as it stands today (one FastAPI app, `ospra_os/main.py` only).
- Carry standing rules across sessions: push back honestly, never delete `email_automation/`, preserve Oubon refs, never use computer-use, run tests before deleting.
- Reference cleanup history (CLEANUP_INVENTORY, CLEANUP_PASS2) so future agents know which deletions have already been considered and rejected (TIER 4 "kept" candidates).
- Note the LemonSqueezy wiring done in Pass 2.

**pyproject.toml:** package renamed from `oubon_mailbot` to `ospra_os`; description updated. `uv.lock` regenerated to match.

---

## 3c — Cross-reference fixes + archive project_structure.md

**Archived:** `docs/project_structure.md` — Dec 2025 layout doc that still referenced the deleted `app/` directory and root `main.py`. Its content is now better expressed in the rewritten README + CLAUDE, so archive rather than rewrite.

**Cross-refs fixed:** four live docs linked to files moved to archive in Pass 3a. Updated each to point at `archive/<name>` and labeled them "(historical)":
- `docs/SATURATION_SCORING.md` → `archive/APIFY_CLEANUP.md`
- `docs/DISCOVERY_PIPELINE_ARCHITECTURE.md` → `archive/APIFY_CLEANUP.md` (also dropped a dead link to a never-existed `DISCOVERY_SYSTEM_STATUS.md`)
- `docs/DATA_SOURCES.md` → `archive/APIFY_CLEANUP.md`
- `docs/IMAGE_ENHANCEMENT_INTEGRATION.md` → `archive/DEPLOYMENT_AI_AUDIT.md`

---

## What was NOT touched

Live docs in `docs/` left in place — each was checked and currently reflects production state:

| Doc | Why kept |
|---|---|
| `API_DOCUMENTATION.md` | Live REST surface |
| `ALIEXPRESS_API_STATUS.md` | Current AE affiliate API state |
| `AUTO_DEPLOYMENT_SERVICE.md` | Live feature |
| `CLEANUP_INVENTORY.md` | Pass 0 record (operational history) |
| `CLEANUP_PASS2.md` | Pass 2 record (operational history) |
| `DATA_SOURCES.md` | Current data source map |
| `DATABASE_DEPLOYMENT.md` | Live Postgres / SQLite setup |
| `DEPLOYMENT_GUIDE.md` | Live Render deploy |
| `DEPLOYMENT_ENV_SETUP.md` | Live env var reference |
| `DISCOVERY_PIPELINE_ARCHITECTURE.md` | Discovery internals |
| `dropshipping_apis.md` | Supplier API comparison |
| `FRONTEND_AUTO_DEPLOYMENT_INTEGRATION.md` | Live |
| `IMAGE_ENHANCEMENT_INTEGRATION.md` | Stability cleanup pipeline |
| `PLATFORM_BADGES_USAGE.md` | Frontend filter chips (Pass 4 of original task list) |
| `PRODUCT_CONTENT_GENERATOR.md` | Live AI title/description gen |
| `SATURATION_SCORING.md` | Live scoring |
| `SECURITY_FUTUREPROOFING.md` | Auth + multi-tenancy |
| `SHOPIFY_AI_INTEGRATION.md` | Live |
| `SHOPIFY_SEO_CHECKLIST.md` | **Oubon Shop reference — protected** |
| `SHOPIFY_SETUP_GUIDE.md` | Live |
| `TESTING_GUIDE.md` | Live multi-store testing |
| `X_TWITTER_SENTIMENT_API.md` | Grok sentiment is still wired (`ospra_os/product_research/connectors/social/xai_twitter.py` exists). Apify Twitter from Task 20 was added alongside, not replacing. |

`docs/guides/*` (5 files): all live integration guides — kept.

Subpackage READMEs (`ospra_os/database/README.md`, `ospra_os/database/INIT_MIGRATION_GUIDE.md`, `ospra_os/dashboard/MULTI_STORE_API.md`, `frontend/README.md`, `tests/README.md`, `website/README.md`, `marketing-site/README.md`): all live, untouched.

---

## Summary

| Metric | Before | After |
|---|---|---|
| Live `docs/` markdown | 35 | 21 |
| Archived `docs/archive/` | 4 | 18 (+ README) |
| Dangling doc cross-refs | 5 | 0 |
| README links to missing files | 9 | 0 |
| CLAUDE.md accuracy | misrepresented project | matches reality |

Three commits:
- `75141f7` Pass 3a: archive 13 completed/dated docs
- `1cb16e8` Pass 3b: rewrite README.md and CLAUDE.md to match reality
- `60ac992` Pass 3c: archive project_structure.md and fix cross-refs
