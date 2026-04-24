# Ospra OS Project Structure

Last Updated: December 10, 2025

## Overview

Ospra OS is a comprehensive e-commerce intelligence platform built with FastAPI. The project consists of a modular monolithic architecture with clear separation of concerns across multiple functional domains.

## Project Root Structure

```
Ospra OS/
├── app/                      # Legacy application core
├── ospra_os/                 # Main application package
├── scripts/                  # Utility scripts
├── data/                     # Runtime data storage
├── docs/                     # Documentation
├── frontend/                 # React/Vite frontend
├── .secrets/                 # OAuth credentials (gitignored)
├── main.py                   # Legacy entry point
└── pyproject.toml           # Project configuration
```

## Core Application Structure (`ospra_os/`)

### Entry Point
- **`ospra_os/main.py`** - Main FastAPI application with router registration

### API Routes (`ospra_os/api/`)
All API route modules follow the pattern: `<domain>_routes.py`

Key modules:
- `auth_routes.py` - JWT authentication (login, register, refresh tokens)
- `aliexpress_product_routes.py` - AliExpress product scraping
- `shopify_deployment_routes.py` - Shopify deployment automation
- `email_oauth_routes.py` - Multi-provider email OAuth
- `meta_ads_routes.py` - Facebook/Instagram advertising
- `admin_routes.py` - Admin dashboard endpoints
- `frontend_compat_routes.py` - Legacy route compatibility layer

### Core Systems (`ospra_os/core/`)
- `settings.py` - Centralized configuration management
- `routes.py` - Core API routes
- `tiers.py` - Subscription tier definitions
- `usage_tracking.py` - API usage tracking

### Authentication & Security (`ospra_os/auth/`)
- `jwt_auth.py` - JWT token creation, validation, password hashing
- Functions: `create_access_token()`, `decode_token()`, `hash_password()`, `verify_password()`

### Database (`ospra_os/database/`)
- `multi_store_models.py` - SQLAlchemy models for all entities
  - User, Store, Product, AdCampaign, EmailTemplate, ABTest
  - ProductDeployment, ProductSaturation, ProductVelocity
  - ProductSnapshot, ProductIntelligence
- `db.py` - Database session management

### Tenant Isolation System (`ospra_os/tenancy/`)
GROK Recommendation #14 - Multi-tenant data isolation
- `context.py` - Tenant context management (TenantContext dataclass)
- `middleware.py` - Automatic tenant context injection from JWT
- `queries.py` - Tenant-scoped database queries (TenantScopedSession)
- `audit.py` - Audit logging for compliance (TenantAuditLog model)
- Fixed: `metadata` → `audit_metadata` (SQLAlchemy reserved name)

### Intelligence & Discovery (`ospra_os/intelligence/`)
- `trend_analyzer.py` - Multi-platform trend analysis (Google Trends, TikTok, Instagram)
- `niche_analyzer.py` - Niche market analysis
- `niche_routes.py` - Niche analysis API endpoints
- `unified_product_discovery.py` - Cross-platform product discovery
- `routes.py` - Competitor intelligence endpoints
- `self_learning.py` - AI-powered learning system

### Email Automation (`ospra_os/email_automation/`)
- **OAuth Support (`email_automation/oauth/`)**:
  - `gmail.py` - Google OAuth implementation
  - `outlook.py` - Microsoft OAuth implementation
  - `icloud.py` - Apple iCloud IMAP/SMTP
  - `yahoo.py` - Yahoo IMAP/SMTP
  - `protonmail.py` - ProtonMail Bridge
  - `zoho.py` - Zoho Mail OAuth
- `routes.py` - Email automation endpoints
- `settings_routes.py` - Email settings management

### Analytics (`ospra_os/analytics/`)
- `customer_analytics.py` - Customer behavior analysis
- `ltv_calculator.py` - Lifetime value calculation
- `churn_predictor.py` - Churn prediction models
- `cohort_analyzer.py` - Cohort analysis
- `purchase_patterns.py` - Purchase pattern detection
- `customer_sync.py` - Shopify customer synchronization
- `customer_routes.py` - Customer analytics API

### Platforms (`ospra_os/platforms/`)
- `base.py` - Base adapter interface
- `shopify.py` - Shopify platform adapter
- Multi-platform abstraction layer

### Services (`ospra_os/services/`)
- `product_deployer.py` - Automated product deployment
- `product_content_generator.py` - AI-powered content generation (Claude Sonnet 4.5)
- `image_processor.py` - Image processing (DALL-E 3 + rembg)
- `image_storage.py` - Image storage management

### Background Jobs (`ospra_os/background_jobs/`)
- Celery-based asynchronous task processing
- Background job management

### Integrations (`ospra_os/integrations/`)
- **AliExpress** (`integrations/aliexpress/`): Dropshipping & affiliate APIs
- **Shopify** (`integrations/shopify/`): E-commerce platform integration
- **Meta** (`integrations/meta/`): Facebook/Instagram ads

### Additional Modules
- **`ospra_os/advertising/`** - Multi-platform ad management (Google, Meta, TikTok)
- **`ospra_os/inventory/`** - Inventory tracking and forecasting
- **`ospra_os/testing/`** - A/B testing framework
- **`ospra_os/actions/`** - AI action queue system
- **`ospra_os/ai/`** - AI chat and providers
- **`ospra_os/voice/`** - Voice command processing (Whisper API)
- **`ospra_os/deployment/`** - Deployment automation
- **`ospra_os/monitoring/`** - System health monitoring
- **`ospra_os/federated/`** - Privacy-preserving federated learning (GROK #18)
- **`ospra_os/whitelabel/`** - Agency white-label B2B2C system (GROK #19)
- **`ospra_os/learning/`** - Machine learning and self-learning systems

## Legacy Application (`app/`)

Original monolithic modules (being migrated to `ospra_os/`):
- `settings.py` - Legacy configuration
- `gmail_client.py` - Gmail API wrapper
- `rules.py` - Email classification rules
- `ai_reply.py` - OpenAI-powered auto-replies
- `db.py` - Async database session manager

## Frontend (`frontend/`)

React + Vite + TypeScript application:
```
frontend/
├── src/
│   ├── components/          # Reusable UI components
│   ├── contexts/            # React Context providers
│   ├── pages/               # Page components
│   ├── services/            # API client services
│   ├── hooks/               # Custom React hooks
│   ├── lib/                 # Utility libraries
│   └── App.tsx              # Root application component
├── public/                  # Static assets
└── package.json             # Node dependencies
```

## Scripts

### Import Auditing
- **`scripts/audit_imports.py`** - Full codebase import validation
- **`scripts/audit_project_imports.py`** - Project-only import validation (excludes .venv)
  - Scans: `ospra_os/`, `app/`, `scripts/`
  - Detects: Missing modules, syntax errors, circular imports
  - Outputs: `project_import_audit.md`

## Data Storage (`data/`)

Runtime data directories:
- `data/images/` - Generated product images
- `data/*.db` - SQLite databases
  - `product_history.db` - Product data
  - `inventory_history.db` - Inventory tracking

## Configuration Files

- **`pyproject.toml`** - Project metadata, dependencies (uv)
- **`.env`** - Environment variables (gitignored)
- **`.env.example`** - Environment template
- **`.secrets/`** - OAuth credentials (gitignored)
  - `credentials.json` - Google OAuth credentials
  - `gmail_token.json` - Gmail access/refresh tokens

## Key Import Patterns

### Correct Import Examples
```python
# Core settings
from ospra_os.core.settings import get_settings

# Authentication
from ospra_os.auth.jwt_auth import decode_token, create_access_token

# Database models
from ospra_os.database.multi_store_models import User, Store, Product

# Tenant scoping
from ospra_os.tenancy.context import get_current_tenant
from ospra_os.tenancy.queries import TenantScopedSession
```

### Router Registration Pattern
All routers use conditional loading in `ospra_os/main.py`:
```python
if _HAS_AUTH and auth_router:
    app.include_router(auth_router)
```

## Recent Fixes (2025-12-10)

1. **Import Errors Fixed**:
   - ✅ `decode_access_token` → `decode_token` in middleware.py
   - ✅ Removed 10 missing model imports from queries.py
   - ✅ Fixed syntax error in aliexpress_product_routes.py (added finally block)
   - ✅ Renamed `metadata` → `audit_metadata` in audit.py (SQLAlchemy reserved name)

2. **Missing `__init__.py` Created**:
   - ✅ ospra_os/research/
   - ✅ ospra_os/connectors/
   - ✅ ospra_os/middleware/
   - ✅ ospra_os/forecaster/
   - ✅ ospra_os/scheduler/
   - ✅ ospra_os/api/
   - ✅ app/templates/

3. **Validation**:
   - ✅ Application imports successfully
   - ✅ All router imports valid
   - ✅ Uvicorn starts without errors
   - ✅ Health endpoint responds: `{"status":"ok","service":"Ospra Intelligence Platform"}`

## Development Commands

```bash
# Start backend (OspraOS)
uv run uvicorn ospra_os.main:app --reload --host 127.0.0.1 --port 8001

# Start frontend
cd frontend && npm run dev

# Run import audit
uv run python scripts/audit_project_imports.py

# Run tests
uv run pytest

# Validate imports
python -c "from ospra_os.main import app; print('✅ App imports successfully')"
```

## Architecture Notes

1. **Modular Monolith**: Single codebase with clear module boundaries
2. **Conditional Router Loading**: Graceful degradation for missing dependencies
3. **Tenant Isolation**: Automatic multi-tenant data scoping (GROK #14)
4. **JWT Authentication**: Stateless auth with access/refresh tokens
5. **AI Integration**: Claude Sonnet 4.5, OpenAI, Google Gemini
6. **Multi-Platform**: AliExpress, Shopify, Meta, TikTok, Gmail, etc.

## Known Warnings

⚠️ **Expected Warnings (non-blocking)**:
- `Shopify OAuth router not implemented yet`
- `Report Engine router not loaded: No module named 'reportlab'`
- `ML System router not loaded: No module named 'ospra_os.database.db'`
- `Amazon FBA router not loaded: No module named 'ospra_os.database.db'`
- `White-Label SaaS router not loaded: No module named 'ospra_os.database.db'`

These are optional features that gracefully degrade when dependencies are unavailable.

## Support

For issues or questions:
- Review this document for structure understanding
- Check `scripts/audit_project_imports.py` for import validation
- See `WHITELABEL_IMPLEMENTATION_STATUS.md` for feature-specific docs
