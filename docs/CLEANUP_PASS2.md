# Pass 2 — Dead Modules & Orphaned Routes

**Method:** AST import-graph walk from real entry points (`main.py`, `celery_app.py` with all listed task modules, `alembic/env.py`, `tests/`, `scripts/*.py`, all `routers/*.py`), cross-checked with live `grep` for both Python imports and string references.

**Result:** Of 495 Python files in `ospra_os/`, ~67 are unreferenced anywhere in the live tree. Categorized below by confidence.

---

## TIER 1 — High-confidence pure dead code (DELETED)

These files are imported by **nothing** in the live tree. No Python imports, no string references, no FastAPI registration, no Celery task discovery. The walker reaches 367 modules; these are not among them.

### Backend internals (29 files)
- `ospra_os/background_jobs/intelligence_scheduler.py`
- `ospra_os/background_jobs/scheduler_integration.py`
- `ospra_os/core/exceptions.py`
- `ospra_os/integrations/aliexpress_scraper.py`
- `ospra_os/integrations/amazon_api.py`
- `ospra_os/integrations/instagram_api.py`
- `ospra_os/integrations/tiktok_api.py`
- `ospra_os/integrations/twitter_api.py`
- `ospra_os/intelligence/ai_actions.py`
- `ospra_os/intelligence/change_analyzer.py`
- `ospra_os/intelligence/claude_advisor.py`
- `ospra_os/intelligence/nl_command_parser.py`
- `ospra_os/intelligence/rationale_generator.py`
- `ospra_os/intelligence/recently_trending_filter.py`
- `ospra_os/intelligence/saturation_analyzer.py`
- `ospra_os/intelligence/smart_cache.py`
- `ospra_os/intelligence/smart_sentiment_cache.py`
- `ospra_os/intelligence/supplier_monitor.py`
- `ospra_os/intelligence/velocity_analyzer.py`
- `ospra_os/media/automated_image_pipeline.py`
- `ospra_os/middleware/rate_limit_middleware.py`
- `ospra_os/models/monitoring.py`
- `ospra_os/product_research/apify_client_simple.py`
- `ospra_os/product_research/discovery_rate_limiter.py`
- `ospra_os/product_research/niche_discovery.py`
- `ospra_os/reports/renderers/chart_generator.py`
- `ospra_os/services/oi_memory.py`
- `ospra_os/database/init_multi_store.py`  *(one-shot setup; superseded by alembic)*
- `ospra_os/database/migrate_differentiation.py`  *(one-shot migration; superseded by alembic)*

### Orphaned FastAPI routes (10 files)
Not registered with `app.include_router()` in `main.py`:
- `ospra_os/api/cache_routes.py`
- `ospra_os/api/image_comparison_routes.py`
- `ospra_os/api/intelligence_routes.py`
- `ospra_os/api/nl_routes.py`
- `ospra_os/api/notification_routes.py`
- `ospra_os/api/rate_limit_routes.py`
- `ospra_os/api/scheduler_routes.py`
- `ospra_os/api/search_relevance_routes.py`
- `ospra_os/intelligence/ai_actions_routes.py`
- `ospra_os/intelligence/opportunity_routes.py`
- `ospra_os/platforms/deployment_routes.py`

---

## TIER 2 — CRITICAL FINDING: Billing infrastructure is dead-coded, not deleted

The following files exist as a self-contained orphan **chain** — they only import each other; nothing in the live application enters this chain. This is **a production concern, not a cleanup target.**

- `ospra_os/payments/__init__.py` → exports `payments_router`
- `ospra_os/payments/routes.py` → defines `router`
- `ospra_os/payments/lemonsqueezy.py` → LemonSqueezyClient, checkout URL helpers
- `ospra_os/api/subscription_routes.py` → upgrade/downgrade endpoints with LemonSqueezy variant logic
- `ospra_os/api/user_routes.py` → user CRUD that *would* call billing
- `ospra_os/api/webhook_routes.py` → LemonSqueezy subscription/order webhook handlers
- `ospra_os/core/routes.py` → core routes that import payments
- `ospra_os/core/usage_routes.py` → tier usage tracking endpoints
- `ospra_os/onboarding/routes.py` → onboarding routes
- `ospra_os/waitlist/routes.py` → waitlist routes
- `ospra_os/fulfillment/routes.py`

**What this means:** main.py registers ~65 routers. None of these. So when a user hits `/api/subscription/upgrade`, `/webhooks/lemonsqueezy/subscription`, `/api/users/*`, etc. — those endpoints don't exist on the running server. LemonSqueezy webhook calls that *should* upgrade users on payment are silently dropping.

**LEFT IN PLACE PENDING USER DECISION.** Two options:
1. Wire them up in `main.py` if billing is meant to be live
2. Delete if you're using a different billing path

---

## TIER 3 — EMAIL_AUTOMATION (PROTECTED per standing rule, NOT touched)

Walker shows three files unreferenced. Per user's standing rule (never delete email_automation), they remain in place even though dead:

- `ospra_os/email_automation/automation_engine.py` — only imported by `automation_routes.py`
- `ospra_os/email_automation/automation_routes.py` — not registered in main.py (the live email_automation router is `ospra_os.api.email_automation_routes`)
- `ospra_os/email_automation/rules.py` — no Python imports (the string `"email_automation_rules"` matches a SQLAlchemy `__tablename__`, not a code import)

The active email_automation chain is:
```
main.py
  └─ api/email_automation_routes.py
       ├─ email_automation/email_processor.py
       │    └─ email_automation/smart_reply.py
       │         └─ email_automation/business_hours.py
       └─ email_automation/gmail_client.py
```
All other email_automation files (`ai_responder`, `email_action_executor`, `email_sender`, `email_sync`, `policies`, `refund_processor`, oauth/*) are imported elsewhere and remain live.

---

## TIER 4 — Suspected orphans, kept (false-positive risk too high)

- `ospra_os/actions/action_factory.py` + `ospra_os/actions/auto_pilot.py` — chain only used by each other
- `ospra_os/intelligence/autopilot.py` — string refs only
- `ospra_os/learning/performance_tracker.py`, `self_learning_engine.py`, `trend_velocity_detector.py` — single-ref chains
- `ospra_os/middleware/rate_limiter.py` — string refs in tier_enforcement
- `ospra_os/onboarding/stratosphere_onboarding.py` + `ospra_os/waitlist/stratosphere_waitlist.py`
- `ospra_os/services/shopify/client.py` + `ospra_os/services/shopify/oauth.py`
- `ospra_os/models/inventory.py` — 16 string refs (likely SQLAlchemy table name strings)

These have non-zero references; before deleting, would need per-file inspection of whether the references are live consumers or just sibling-orphans.

---

## What was deleted in this pass

40 files removed (29 backend internals + 11 orphan routes). All deletions verified by:
1. Import-graph walk shows 0 reachability
2. `grep` confirms 0 Python imports, 0 string references
3. Pytest run confirms no test failures introduced

Backups: full git history retains all deleted files; recovery via `git revert` or `git show <sha>:<path>` if needed.
