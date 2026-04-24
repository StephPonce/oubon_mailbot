# docs/archive/

Historical documentation kept for reference. **None of these are kept up to date.** Refer to the live docs in `docs/` for current state.

## Why these are archived

Each file here was either (a) a completion report for finished work, (b) a point-in-time audit superseded by newer work, (c) a migration plan that has fully executed, or (d) a decision memo whose decision is now in production.

## Index

### Feedback-loop project (G4) — completed Dec 2025
- `G4_IMPLEMENTATION_STATUS.md` — status snapshot during build
- `G4_COMPLETION_SUMMARY.md` — wrap-up summary
- `G4_ACTIVATION_GUIDE.md` — how-to-activate guide (now in production)
- `G4_PHASE_4_COMPLETE.md` — final phase completion report
- `G4_FEEDBACK_LOOP_IMPLEMENTATION.md` — design doc

The G4 feedback loop is live. Code lives in `ospra_os/learning/`, `ospra_os/database/performance_models.py`, `ospra_os/api/feedback_routes.py`.

### app/ → ospra_os/ migration — completed Dec 2025
- `T2_MIGRATION_COMPLETE.md` — migration report
- `app_migration_plan.md` — original plan

The legacy `app/` directory no longer exists. All code is under `ospra_os/`.

### One-shot audits and analyses
- `T7_API_CONSOLIDATION.md` — API route consolidation analysis (executed in cleanup Pass 2)
- `routes_audit.md` — point-in-time route inventory
- `INTELLIGENCE_AUDIT_DEC2024.md` — capability audit, superseded by current cleanup work
- `DEPLOYMENT_AI_AUDIT.md` — deployment audit snapshot
- `APIFY_CLEANUP.md` — Apify scraper cleanup report
- `TASK_20_TWITTER_APIFY_EVALUATION.md` — Grok vs. Apify decision memo (resolved)

### Earlier archive entries
- `APIFY_CONFIGURATION.md`
- `GMAIL_OAUTH_SETUP.md`
- `OSPRA_OS_AI_AUTOMATION.md`
- `UNIFIED_DISCOVERY_API.md`
