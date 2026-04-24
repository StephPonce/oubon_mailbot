# Ospra OS

**AI-powered e-commerce automation for dropshipping.** Product discovery, social-sentiment scoring, AI grading, automated Shopify deployment, and Gmail-based customer support automation — all in one FastAPI app.

The reference storefront running on this stack is **Oubon Shop** (`oubonshop.com`).

---

## Quick start

```bash
# 1. Install dependencies (uses uv, not pip)
uv sync

# 2. Configure environment
cp .env.example .env
# Edit .env with your API keys

# 3. Initialize database
uv run python scripts/init_db.py

# 4. Start backend + frontend
./scripts/run.sh start

# Backend → http://localhost:8001  (docs at /docs)
# Frontend → http://localhost:5173
```

`./scripts/run.sh` is the single consolidated dev script (`start | stop | restart | backend | frontend | status | logs | clean`).

---

## What it does

1. **Product discovery** — pulls candidate products from CJ Dropshipping, AliExpress (official affiliate API), Amazon, and Apify-driven trend feeds (Google Trends, TikTok). Discovery is the priority feature.

2. **Social-sentiment scoring** — three-tier signal:
   - **Amazon reviews via Apify** (primary, weight 88) — real-world buyer sentiment
   - **AliExpress reviews** (weight capped at 78) — supplier-side proof
   - **CJ supplier-quality proxy** (weight 70) — for CJ-only products with no review data

3. **AI grading** — Claude/GPT-4o/Gemini ensemble scores each product 0–100 on opportunity (margin, trend, saturation, sentiment). Variance is locked across refreshes (verified by `scripts/test_ai_analysis_variance.py`).

4. **Automated Shopify deployment** — push approved products to Shopify with AI-generated titles, descriptions, and Stability-enhanced images.

5. **Gmail email automation** — Gmail OAuth + AI auto-reply with rule-based classification (orders / VIP / important / routine), template substitution, and Shopify order lookup for "where's my order" replies.

6. **Feedback loop (G4)** — tracks per-product performance after deployment and feeds outcomes back into AI scoring weights, both globally and per-user.

---

## Architecture

```
ospra_os/                  # the FastAPI app
├── main.py                # entry point
├── celery_app.py          # background scheduler
├── intelligence/          # product discovery, scoring, AI analysis
├── api/                   # FastAPI routes (~50 modules)
├── product_research/      # source connectors (Amazon, AliExpress, Reddit, Apify)
├── integrations/          # Shopify, CJ Dropshipping, Stability, AI providers
├── database/              # SQLAlchemy models, alembic migrations
├── email_automation/      # Gmail-based customer support
├── learning/              # G4 feedback loop
├── payments/              # LemonSqueezy billing
└── ...
frontend/                  # React + Vite dashboard
scripts/                   # run.sh + utilities
tests/                     # pytest
docs/                      # live docs (see docs/archive/ for historical)
```

See `CLAUDE.md` for a fuller architecture breakdown.

---

## Configuration

Required environment variables (see `.env.example`):

```bash
# AI providers
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...                  # for AI ensemble + email auto-reply

# Discovery sources
APIFY_TOKEN=apify_api_...              # Amazon reviews, Google Trends, TikTok
ALIEXPRESS_APP_KEY=...                 # affiliate API
ALIEXPRESS_APP_SECRET=...
ALIEXPRESS_SESSION_KEY=...
CJ_DROPSHIPPING_API_TOKEN=...          # must have product-access scope
STABILITY_API_KEY=sk-...               # background cleanup for product images

# Shopify
SHOPIFY_STORE=yourstore.myshopify.com
SHOPIFY_API_TOKEN=shpat_...

# Gmail (email automation)
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...

# Database
DATABASE_URL=postgresql://...          # or sqlite:///./data/ospra.db for local

# Billing (LemonSqueezy)
LEMONSQUEEZY_API_KEY=...
LEMONSQUEEZY_WEBHOOK_SECRET=...
LEMONSQUEEZY_STORE_ID=...
LEMONSQUEEZY_VARIANT_FLIGHT_MONTHLY=...
LEMONSQUEEZY_VARIANT_FLIGHT_YEARLY=...
LEMONSQUEEZY_VARIANT_SOAR_MONTHLY=...
LEMONSQUEEZY_VARIANT_SOAR_YEARLY=...
LEMONSQUEEZY_VARIANT_STRATOSPHERE_MONTHLY=...
LEMONSQUEEZY_VARIANT_STRATOSPHERE_YEARLY=...
```

Setup guides for each integration live in `docs/` — see the index below.

---

## Documentation index

### Setup & deployment
- `docs/DEPLOYMENT_GUIDE.md` — production deployment (Render)
- `docs/DEPLOYMENT_ENV_SETUP.md` — env vars for unified product deployment
- `docs/DATABASE_DEPLOYMENT.md` — database setup (SQLite → Postgres)
- `docs/SHOPIFY_SETUP_GUIDE.md` — Shopify integration

### Architecture & features
- `docs/DATA_SOURCES.md` — every data source the app touches
- `docs/DISCOVERY_PIPELINE_ARCHITECTURE.md` — discovery internals
- `docs/SATURATION_SCORING.md` — how saturation is computed
- `docs/AUTO_DEPLOYMENT_SERVICE.md` + `docs/FRONTEND_AUTO_DEPLOYMENT_INTEGRATION.md`
- `docs/SHOPIFY_AI_INTEGRATION.md` — AI-powered Shopify flow
- `docs/PRODUCT_CONTENT_GENERATOR.md` — AI titles/descriptions
- `docs/IMAGE_ENHANCEMENT_INTEGRATION.md` — Stability image cleanup
- `docs/PLATFORM_BADGES_USAGE.md` — supplier/warehouse badges + filter chips
- `docs/SECURITY_FUTUREPROOFING.md` — auth, encryption, multi-tenancy

### API & integrations
- `docs/API_DOCUMENTATION.md` — REST API surface
- `docs/ALIEXPRESS_API_STATUS.md` — affiliate API state
- `docs/X_TWITTER_SENTIMENT_API.md` — Grok-based Twitter sentiment
- `docs/dropshipping_apis.md` — supplier API comparison
- `docs/guides/AFFILIATE_API_GUIDE.md` — AliExpress deep-dive
- `docs/guides/SHOPIFY_OAUTH_SETUP_GUIDE.md`
- `docs/guides/SHOPIFY_OPTIMIZATION_GUIDE.md`
- `docs/guides/AI_PROVIDER_BASE_GUIDE.md` — adding a new AI provider
- `docs/guides/AD_AUTOMATION_SYSTEM_GUIDE.md` — Meta/Google/TikTok ads
- `docs/guides/TIKTOK_SETUP_GUIDE.md`

### Operations
- `docs/TESTING_GUIDE.md` — multi-store testing
- `docs/SHOPIFY_SEO_CHECKLIST.md` — Oubon storefront SEO checklist

### Cleanup history (operational record)
- `docs/CLEANUP_INVENTORY.md` — Pass 0: full repo classification
- `docs/CLEANUP_PASS2.md` — dead-module / orphan-route removal
- `docs/archive/` — completed/dated docs (G4 phases, T2 migration, audits)

---

## Testing

```bash
uv run pytest                          # full suite
uv run pytest -k "discovery"           # filter by keyword
bash scripts/run_tests.sh              # convenience wrapper

# Targeted scripts (live-data smoke tests)
uv run python scripts/test_ai_analysis_variance.py     # grading lock
uv run python scripts/test_aliexpress_signal.py        # AE sentiment
uv run python scripts/test_full_discovery.py           # end-to-end discovery
uv run python scripts/diagnose_cj.py                   # CJ token health
uv run python scripts/smoke_test_deployment.py         # Shopify deploy
```

---

## Project status

| Component | Status |
|---|---|
| Product discovery (CJ + AliExpress + Amazon + Apify) | Live |
| Social sentiment (Amazon reviews via Apify) | Live |
| AI grading (Claude + GPT-4o + Gemini ensemble) | Live, variance-locked |
| Shopify deployment | Live |
| Gmail email automation | Live |
| LemonSqueezy billing | Wired up; needs env vars + dashboard config to activate |
| Frontend (React) | Live |
| G4 feedback loop | Live |
| TikTok integration | Partial — used as sentiment source, not for posting |

---

## License

Proprietary — all rights reserved.
