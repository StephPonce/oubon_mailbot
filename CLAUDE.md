# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Project Overview

**Ospra OS** is an AI-powered e-commerce automation SaaS for dropshipping. It does product discovery (AliExpress + CJ Dropshipping + Amazon + Apify-driven trend signals), social-sentiment scoring, AI grading, automated Shopify deployment, and Gmail-based customer support automation.

The user's own storefront is **Oubon Shop** (`oubonshop.com`) — it's the reference tenant and the first customer. As of Pass 4b (commit `a01830a`), all tenant-facing prompts, policies, and AI output are parameterized via `ospra_os/tenancy/brand.py` + factory functions in `policies.py`. Oubon is the default fallback, not a hardcode.

The codebase is one FastAPI app — `ospra_os/main.py`. There is no longer a legacy `app/` directory or root-level `main.py`; both were consolidated during the December 2025 migration (see `docs/archive/T2_MIGRATION_COMPLETE.md`).

### Important memory files — read these first each session

- `TASKS.md` — current task list (what's pending / in progress / blocked)
- `memory/decisions.md` — locked architecture and product decisions with rationale
- `memory/target_customer.md` — who we're building for (broadened Pass 4)
- `memory/pricing.md` — tier ladder + standalone modules + white-glove
- `memory/competitors.md` — competitive landscape + our edges
- `memory/roadmap_priorities.md` — ordered roadmap with ship rules

## Standing rules (carry across sessions)

- **Don't manage the user's time or schedule.** Never say "let's stop here," "call it for the night," "we're done for today," "you've earned a break," or anything that implies when to stop working. The user decides when the session ends — Claude works until the user says so. Claude has no sleep schedule; the user does and will manage it themselves.

- **ALWAYS ask before structural / architectural decisions.** Before creating new routes, tabs, components, endpoints, database tables, or anything that changes the system's shape — ASK. Don't decide unilaterally that "the new flow needs a separate page" or "this should be a new tab." Confirm with the user FIRST. Same for renaming, splitting, or merging existing features.

- **NEVER say "can't be done" or "browser limitation, sorry."** Always find a workaround. Streaming responses, pagination, background jobs with polling, deferred work, lazy loading — there is always a way. Defeatism is unacceptable; "I haven't figured out how yet" is the honest version when needed.

- **Don't add features the user didn't ask for.** If the user hasn't explicitly requested AI image generation, semantic matching as a default, auto-rating, or any other "enhancement" — DON'T do it on the cold path. Such features are manual-click / opt-in by default. The user explicitly called out AI image gen as a manual-click feature that should run only when explicitly invoked, with caching so cost amortizes across users.

- **Use ALL connected APIs by default, not just one.** Discovery should run social sentiment (X/Twitter, Reddit, Amazon reviews via Apify) IN PARALLEL with sourcing (AliExpress, CJ Dropshipping) and winner-proof signals (Meta Ad Library, TikTok Shop, Amazon Movers, Etsy, Pinterest, Google Trends). Don't make any one API the centerpiece — they're all inputs to the same scoring pipeline. Social sentiment FIRST, sourcing second.

- **Audit your own work before declaring done.** Read back what you wrote. Trace the data flow. Check that the change doesn't break sibling features or introduce duplicate surfaces. If a tab/route/component already exists for this purpose, EXTEND it instead of creating a new one.

- **Push back honestly.** The user is non-technical ("im not the coder i had ai do it ALL for me beleive it or not so i need you to help me decide"). Don't sugarcoat — if a change is risky, say so plainly.
- **Product discovery is priority #1.** Anything that touches the discovery pipeline gets extra scrutiny.
- **Social sentiment is the differentiator.** Amazon reviews (Apify) → AliExpress reviews → CJ supplier-quality proxy. Don't gut any tier.
- **Never delete `ospra_os/email_automation/` files.** Email automation is a core feature even when individual files look orphaned. The active chain is `api/email_automation_routes.py` → `email_automation/email_processor.py` → `gmail_client.py` etc.
- **Preserve all Oubon references.** They tie real production data to the user's storefront.
- **Run tests before deleting.** `uv run pytest` (or `bash scripts/run_tests.sh`). If a deletion would break a test, stop and ask.
- **Never use computer-use** for this project. The user has explicitly disabled it.

## Development commands

```bash
# Install / sync dependencies (uv, not pip)
uv sync

# Lint + format
uv run ruff check .
uv run ruff format .

# Tests
uv run pytest                      # full suite
uv run pytest -k "discovery"       # filter by keyword
bash scripts/run_tests.sh          # convenience wrapper

# Run servers (consolidated into one script)
./scripts/run.sh start             # backend + frontend
./scripts/run.sh backend           # backend only (port 8001)
./scripts/run.sh frontend          # frontend only (port 5173)
./scripts/run.sh stop              # kill both
./scripts/run.sh status            # what's listening
./scripts/run.sh logs              # tail both logs

# Direct uvicorn (matches Render production)
uv run uvicorn ospra_os.main:app --host 0.0.0.0 --port 8001 --reload

# Celery worker (background jobs / scheduled discovery)
uv run celery -A ospra_os.celery_app worker --loglevel=info
bash scripts/start_g4_celery.sh    # convenience wrapper
```

## Architecture

### Top-level layout

```
ospra_os/                         # the FastAPI app
├── main.py                       # entry point — registers ~65 routers via include_router
├── celery_app.py                 # Celery worker config (auto-discovers tasks/)
├── core/                         # settings, config
├── intelligence/                 # discovery, scoring, AI analysis (53 files)
├── api/                          # FastAPI route modules (50 files)
├── product_research/             # source connectors (Amazon, AliExpress, Reddit, etc.)
├── integrations/                 # Shopify, CJ, Stability, AI providers
├── database/                     # SQLAlchemy models, alembic migrations
├── email_automation/             # PROTECTED — core feature, never delete
├── gmail/                        # PROTECTED — Gmail OAuth integration
├── services/                     # product_deployer, image_processor
├── ai/                           # AI provider abstraction (Claude, GPT-4o, Gemini)
├── learning/                     # G4 feedback loop (RLHF-style learning)
├── tasks/                        # Celery tasks
├── tenancy/                      # multi-tenant isolation (SaaS)
├── payments/                     # LemonSqueezy billing
├── auth/                         # JWT, sessions
└── ...
frontend/                         # React + Vite dashboard (port 5173)
scripts/                          # run.sh, init_db.py, test_*.py, etc.
tests/                            # pytest suite
docs/                             # live docs (see archive/ for historical)
alembic/                          # migrations
```

### Routing pattern

`main.py` does a bunch of `try: import …router … include_router(…)` blocks. Routers that fail to import log a warning instead of crashing the app — this is intentional graceful degradation for optional integrations. **Side-effect:** static analysis tools see "unused imports" but they're really conditional registrations.

### Discovery pipeline (the heart of the app)

`ospra_os/intelligence/product_discovery.py` orchestrates:
1. Pull candidate products from per-niche sources (CJ, AliExpress, Amazon, Apify trend feeds).
2. Score each with `opportunity_scorer.py` (margin, trend, saturation, sentiment).
3. Enrich with social sentiment via `product_research/connectors/social/*` (Amazon reviews via Apify is the primary signal; AliExpress reviews second; CJ proxy for CJ-only products).
4. Rank and return.

The active grading lock is verified by `scripts/test_ai_analysis_variance.py`. Don't loosen variance bounds without re-running it.

### Background work

- **Celery** (`ospra_os/celery_app.py`) runs scheduled tasks listed in its `include=[...]`. To add a new periodic task, add the module path to that list.
- The `schedule`-library based scheduler in `ospra_os/intelligence/intelligence_scheduler.py` was removed in cleanup Pass 2 (it was orphaned). Celery is now the only scheduler.

### Billing

LemonSqueezy infrastructure was wired up in cleanup Pass 2 (it had been silently dead-coded — webhooks were dropping). Routers:
- `ospra_os/payments/routes.py` → `/api/payments/*`
- `ospra_os/api/subscription_routes.py` → `/api/subscription/*`
- `ospra_os/api/webhook_routes.py` → `/api/webhooks/lemonsqueezy/subscription` and `/order`
- `ospra_os/api/user_routes.py` → `/api/users/*`

These require env vars: `LEMONSQUEEZY_API_KEY`, `LEMONSQUEEZY_WEBHOOK_SECRET`, `LEMONSQUEEZY_STORE_ID`, plus six variant IDs (Flight/Soar/Stratosphere × monthly/yearly).

## Cleanup history

Recent systematic cleanup is documented in `docs/CLEANUP_INVENTORY.md` (Pass 0 inventory) and `docs/CLEANUP_PASS2.md` (dead-module removal). Read those before doing more deletions — they explain which files have non-zero references but live in dead chains and need per-file inspection.

## Testing notes

- `tests/` uses pytest fixtures defined in `tests/conftest.py`.
- Some tests have pre-existing failures unrelated to cleanup work: bcrypt 72-byte limit in `test_security.py`, missing `groq` module in `test_differentiation.py`, sqlalchemy fixture issues in `test_actions_routes.py`. These are environment issues, not regressions.
- Before deleting any file, search for both Python imports AND string references (SQLAlchemy table names, Celery task names, dynamic imports). Pass 2's import-graph walker (`/tmp/orphan_walker_v2.py`) does this — adapt it if you need to re-run.
