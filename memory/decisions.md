# Architecture & Product Decisions (locked)

Decisions that are NOT up for re-debate each session. If you want to reopen one, add a new dated entry below with the counter-argument — don't silently overturn.

---

## D1 — FastAPI monolith, not microservices (locked)
**Decided:** earlier in 2025. **Reason:** solo founder + AI-assisted codebase. One deploy target (Render), one Dockerfile, one test command. Splitting into services would multiply the ops surface without any scaling need at sub-1k tenants.
**Trigger to revisit:** discovery pipeline starts dominating CPU and can't be Celery-workered out cleanly.

## D2 — Celery is the only scheduler (locked Pass 2)
Removed the `schedule`-library-based `intelligence_scheduler.py`. All periodic work lives in `ospra_os/celery_app.py`'s `include=[…]` + `beat_schedule`.
**Why it matters for Claude:** if you want to add a recurring job, edit `celery_app.py`. Do not reintroduce a second scheduler.

## D3 — uv, not pip / poetry (locked)
`uv sync` for deps, `uv run` for every command. `requirements.txt` is generated, not authored. `pyproject.toml` is the source of truth.

## D4 — Brand is parameterized, Oubon is the default fallback (locked Pass 4b, commit `a01830a`)
All tenant-facing prompts/emails/policies accept a `Brand` object or use factories in `ospra_os/tenancy/policies.py`. Oubon is the default when no tenant is bound. **Do not hardcode "Oubon" in prompt strings** — the pre-commit hook `no-oubon-in-prompts` blocks it.
**Exception:** `memory/`, `docs/`, and marketing-site copy may reference Oubon freely — they describe the reference tenant, not the product.

## D5 — Tenancy is row-level via `TenantScopedSession` (locked Pass 4)
All queries go through `TenantScopedSession(session, ctx)` inside a `tenant_scope()` block. A bare `session.query(Model)` on a user-scoped model is a bug — `TenantScopedSession` will raise `TenantQueryError` if no context is bound.
**Product is scoped via Store, not directly.** Product has `store_id` only. Product-level isolation testing is deferred until `queries.py` disambiguates Product categorization (Pass 4d, task #34).

## D6 — Discovery pipeline is the product moat, not Shopify deploy (locked)
Shopify deploy is table stakes. The moat is: Amazon reviews (Apify) → AliExpress reviews → CJ supplier-quality proxy, combined into a sentiment score that feeds `opportunity_scorer.py`. **Don't gut any sentiment tier** to save API cost — we'd lose the only thing nothing else on the market does.

## D7 — Multi-provider AI via `ospra_os/ai/` abstraction (locked)
Claude (primary), GPT-4o (fallback), Gemini (cost tier), Grok (experimental), Groq (speed). Provider is chosen per-task in `ai/provider_router.py`. **Do not** import `anthropic` or `openai` directly from feature code — always go through the abstraction. This lets us swap models without touching business logic.

## D8 — Per-request tier ceiling is orthogonal to weekly quota (locked 2026-04)
`products_per_week` caps the tenant's total output. `get_products_per_request_ceiling(tier)` caps a single API call so a Nest user can't chain 50 requests to exhaust a week's quota in one burst and so the frontend gets a clean "upgrade to see more" signal via `tier_meta.clamped`.

## D9 — Graceful-degrading router registration (locked)
`main.py` wraps each `include_router` in try/except and logs a warning on import failure. Ruff "unused import" warnings on router modules in `main.py` are false positives — keep the imports. Missing optional dependencies should never crash boot.

## D10 — LemonSqueezy, not Stripe (locked Pass 2)
LS handles EU VAT / MoR so the user (non-US-tax-resident) doesn't touch sales tax. Webhooks live at `/api/webhooks/lemonsqueezy/subscription` and `/order`. Six variant IDs are required env vars (Flight/Soar/Stratosphere × monthly/yearly).

## D11 — White-glove is a pricing tier, not a sales motion (locked Pass 4)
$499 tier exists AS a signup option, not as something sales upsells. New merchants pick it during onboarding. It promises: human-managed store setup, first 30 days of discovery curation, 1:1 weekly check-in. Don't collapse it into "Enterprise — call us."

## D12 — Standalone modules are real SKUs (locked Pass 4)
`$49` Discovery-only and `$149` Discovery+Support exist as API-gated standalone products, separately from the SaaS tiers. The goal is to reach users who already have a store and don't want a new dashboard.

## D13 — Target customer is broader than the 0.1% (locked Pass 4)
Not "scaling dropshippers doing $50k+/mo". The real TAM is merchants on Shopify/WooCommerce who spend >4 hrs/week on product sourcing or support — ~400k globally. See `memory/target_customer.md`.

## D14 — Tests are the commit gate, not linting (locked Pass 4c)
`npm run lint` is soft-fail in CI until Pass 5. `uv run pytest` is hard-fail. `ruff check` is hard-fail on the Python side. If a deletion would break a test, the deletion is wrong — don't loosen the test.

---

## Proposed / not yet locked

_(add here with date + rationale; promote to top once agreed)_

- **P1 — Move from SQLite dev DB to Postgres for local dev** — proposed, not urgent; SQLite is faster for tests and the in-memory fixture pattern works. Revisit once we hit a JSONB feature we actually need.
- **P2 — Switch discovery cache from Redis to DuckDB-on-disk** — proposed only if Redis cost becomes a problem. Currently Redis handles both Celery broker + discovery cache cheaply.
