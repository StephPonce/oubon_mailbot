# Pass 4 — SaaS Modularity / Tenant-Isolation Audit

**Method:** Inventory every SQLAlchemy model in `ospra_os/database/`, classify each by how it isolates data between tenants. Then trace how routes actually enforce tenant scoping. Then sweep the codebase for hardcoded "Oubon Shop" references that would prevent another tenant from cleanly using the platform.

**Scope:** 63 SQLAlchemy models across 19 files in `ospra_os/database/`, plus the tenancy infrastructure under `ospra_os/tenancy/`, plus 27 route files in `ospra_os/api/`, plus a grep for Oubon hardcoded refs across all of `ospra_os/`.

**Tooling:** `/tmp/tenancy_audit.py` (AST walker — finds every `Base` subclass, extracts `__tablename__` + column names, classifies each).

**Result:** Tenant isolation is **functionally correct in production today (single tenant = Oubon)** but has structural debt that will need to be addressed before onboarding a second tenant. Two real bugs identified. Tenancy infrastructure exists but is mostly unused.

---

## 4a — Model classification (63 models)

| Category | Count | Meaning |
|---|---:|---|
| `USER_TABLE` | 2 | The user/tenant identity itself (`users`, `password_reset_tokens`) |
| `TENANT+STORE` | 5 | Has both `user_id` AND `store_id` — fully scoped to a tenant's store |
| `TENANT_SCOPED` | 26 | Has `user_id` — scoped to a tenant directly |
| `STORE_SCOPED` | 3 | Has `store_id` — implicitly tenant-scoped via store ownership |
| `SHARED_OK` | 12 | Legitimately shared (caches, niches, ML weights, white-label config) |
| `AMBIGUOUS` | 15 | No direct `user_id`/`store_id` — needed to be inspected one-by-one |

The 36 in `USER_TABLE / TENANT+STORE / TENANT_SCOPED / STORE_SCOPED` are clearly tenant-scoped. The 12 in `SHARED_OK` are intentionally global (e.g. `niches`, `cached_aliexpress_products` — same niche or same supplier product is the same data for everyone).

The 15 `AMBIGUOUS` tables broke down as follows after manual inspection:

### Indirect tenant-scoped via parent FK (8 tables — OK in principle, fragile in practice)

These have no direct `user_id` but inherit ownership through a parent row. As long as queries always join through the parent, isolation holds:

| Table | Parent | Notes |
|---|---|---|
| `amazon_order_items` | `amazon_orders.user_id` | `cascade="all, delete-orphan"` enforces parent ownership |
| `ab_test_variants` | `ab_tests.user_id` | |
| `ab_test_events` | `ab_tests.user_id` (via test_id) | |
| `ab_test_assignments` | `ab_tests.user_id` (via test_id) | |
| `cross_store_learnings` | `stores.user_id` (via source_store_id + target_store_id) | Both endpoints must belong to the same tenant — currently no DB constraint enforcing that |
| `whitelabel_analytics` | `whitelabel_partners.id` | Partner-scoped, not user-scoped |
| `product_enhanced_images` | None — keyed by URL hash | Cache by image URL → safe to share across tenants |
| `enhanced_image_cache` | None — keyed by URL hash | Same cache pattern |

**Risk:** if a future query forgets the parent join, data leaks between tenants. Acceptable today; brittle long-term.

### Intentionally shared (4 tables — the "intelligence moat")

| Table | Why shared |
|---|---|
| `product_saturation` | Tracks how many users have a product → IS the saturation moat. Must be cross-tenant by definition. |
| `product_velocity` | Global trend velocity per product → cross-tenant by definition. |
| `product_snapshots` | Time-series price/rank/reviews per ASIN — global market data. |
| `product_intelligence` | Calculated momentum/saturation per ASIN — global market data. |

These four are **correctly cross-tenant**. They are platform-level data, not user data.

### Real isolation gaps (3 tables — flagged below)

1. **`tiktok_tokens`** — single platform-wide row, no `user_id`. **Wrong for SaaS.**
2. **`email_followups`** — no `user_id`, PK is `gmail_message_id`. **Wrong shape.**
3. **`action_templates`** — has `creator_id` (uncategorized by audit because the field isn't named `user_id`/`owner_id`). Marketplace-style template — author is tracked but templates are intentionally consumable by any tenant. **OK once classified.**

---

## 4b — Tenancy infrastructure: exists, mostly unused

`ospra_os/tenancy/` contains a real multi-tenant framework:

- **`context.py`** — `TenantContext` dataclass + contextvars-based `get_current_tenant()` / `set_current_tenant()`. ✅ correct.
- **`middleware.py`** — `TenantMiddleware` extracts `user_id` from JWT, sets context per request, clears on exit. `RequireTenantMiddleware` returns 403 on non-exempt paths. **Registered in `main.py:1011-1012`.** ✅ active.
- **`queries.py`** — `TenantScopedSession` wrapper around SQLAlchemy `Session` that auto-filters queries by tenant.
- **`dependencies.py`** — FastAPI deps (`get_tenant_db`, `require_admin`, `RequireSubscription`, etc.).

### Findings

**1. `TenantScopedSession` is wired up but only knows about 6 of 63 models.**

```python
# ospra_os/tenancy/queries.py:36-56
DIRECT_TENANT_MODELS = {Store, EmailTemplate, ABTest, AdCampaign}
USER_SCOPED_MODELS = {Product}
STORE_SCOPED_MODELS = {Product}
UNSCOPED_MODELS = {User}
```

Any other model passed to `tenant_db.query(SomeModel)` would hit the `else` branch at line 141:
```python
raise TenantQueryError(
    f"Model {model.__name__} is not categorized for tenant scoping..."
)
```

So you cannot use `TenantScopedSession` for `Email`, `Action`, `Niche`, `AmazonOrder`, etc. without first adding them to the categorization sets.

**2. The categorization is wrong for the 4 models it does cover.**

`DIRECT_TENANT_MODELS` filters by `tenant_id`:
```python
# queries.py:122-128
if model in DIRECT_TENANT_MODELS:
    if hasattr(model, 'tenant_id'):
        query = query.filter(model.tenant_id == self._tenant.tenant_id)
    else:
        raise TenantQueryError(
            f"Model {model.__name__} is marked as DIRECT_TENANT but has no tenant_id field"
        )
```

But `Store`, `EmailTemplate`, `ABTest`, `AdCampaign` all use `user_id`, not `tenant_id` (verified in audit). So calling `tenant_db.query(Store)` raises `TenantQueryError` immediately.

**3. Only 2 of 27 route files actually use `TenantScopedSession`:**
- `ospra_os/api/store_routes.py`
- `ospra_os/api/aliexpress_product_routes.py`

The other 25 route files use this pattern (from `ospra_os/api/dependencies.py`):
```python
CurrentUser = Annotated[User, Depends(get_current_user)]
DB = Annotated[Session, Depends(get_db)]
```
…and manually filter by `current_user.id`. This works but has zero structural enforcement — every route author has to remember.

### Net verdict on the tenancy layer

- `TenantContext` + middleware: correct, active, doing real work (every authenticated request has a tenant context).
- `TenantScopedSession` + `get_tenant_db`: **dead code**. Can't even be used on the models it claims to cover.
- Real tenant filtering happens via the older `current_user`-based pattern in 25 route files.

**Decision:** the structural overhaul to make `TenantScopedSession` actually work would touch every route. Defer until the second tenant is real. For now, document that the infrastructure is aspirational and the real isolation comes from manual `user_id` filters in each route.

---

## 4c — Route-level filtering spot check

Sampled a handful of high-traffic routes to verify each `db.query(X)` either filters by `current_user.id` or operates on a public/shared resource. The pattern is consistent: routes that take a `current_user: CurrentUser` parameter filter by `user_id` in the query body.

**Caveat:** spot-checked, not exhaustively audited. Before onboarding any second tenant, every route file should be re-read with this single question: "does this query filter by `user_id`, or does it return cross-tenant data?"

---

## 4d — Hardcoded "Oubon" sweep across `ospra_os/`

40 files reference "Oubon" / "OUBON" / "oubonshop". Categorized:

### PROTECTED — never modify (per standing rule)
- All of `ospra_os/email_automation/` (`smart_reply.py`, `ai_responder.py`, `refund_processor.py`, `policies.py`) — Oubon's own customer-service brain. Standing rule: never delete this module.

### LEGITIMATE — Oubon is the brand for the operator
- `core/settings.py`: `BRAND_NAME = "Oubon Shop"`, `SUPPORT_FROM_EMAIL = "support@oubonshop.com"`, `GMAIL_LABEL_PREFIX = "OUBON"`. These are env-overridable defaults — fine for single-tenant Oubon deployment. For SaaS, every tenant just needs to override via env.
- `aliexpress/*`, `aliexpress_tokens.py`: single Oubon AE app serves all users (intentional — AE rate-limits per app, so platform-wide token is correct).
- All docs (`README.md`, `CLAUDE.md`, `database/INIT_MIGRATION_GUIDE.md`, `dashboard/MULTI_STORE_API.md`): documentation references — fine.

### SAAS-BLOCKER — would prevent another tenant from using cleanly
- `core/settings.py` line ~?: `env_prefix = "OUBONSHOP_"` on the Pydantic settings class. Means every env var is `OUBONSHOP_*`. For multi-tenant SaaS this should be `OSPRA_OS_*` (or unprefixed). Currently this is consistent with single-tenant Oubon deployment, but locks every future tenant deployment into the `OUBONSHOP_*` namespace. **Fix when SaaS rollout starts.**
- `intelligence/ai_product_analyzer.py:898`: `"store_name": "Oubon Shop"` is hardcoded into the AI prompt context. Means another tenant's product analysis would get Oubon's store name injected into its AI reasoning. **Fix: read from tenant context.**
- `intelligence/opportunity_scorer.py:255` and `intelligence/product_discovery.py:220`: env var lookup falls back to `OUBONSHOP_APIFY_API_TOKEN`. Same `OUBONSHOP_` prefix issue.
- `aliexpress/routes.py`: error messages reference `OUBONSHOP_ALIEXPRESS_API_KEY` / `OUBONSHOP_ALIEXPRESS_APP_SECRET` env var names. Cosmetic — would confuse a non-Oubon admin reading error messages.

None of these are urgent. Each is a 5-minute change when the time comes.

---

## 4e — Real bugs to fix

### Bug 1 — `tiktok_tokens` is platform-wide (1 token shared across all users)

`ospra_os/database/tiktok_tokens.py:19-43`:
```python
class TikTokToken(Base):
    __tablename__ = "tiktok_tokens"
    id = Column(Integer, primary_key=True)
    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text, nullable=True)
    # ... no user_id ...
```

Today this works because there's one Oubon TikTok account. The moment a second tenant connects their TikTok, it overwrites Oubon's token. AliExpress is correctly platform-wide (per-app rate limits force it). TikTok is not — every user has their own TikTok account and their own OAuth.

**Fix:** add `user_id` column + unique constraint on `user_id`. Defer until SaaS rollout starts (no harm today).

### Bug 2 — `email_followups` has no `user_id`, PK is `gmail_message_id`

`ospra_os/database/email_models.py:377-400`:
```python
class EmailFollowup(Base):
    __tablename__ = "email_followups"
    gmail_message_id = Column(String, primary_key=True)
    customer_email = Column(String, nullable=False)
    # ... no user_id ...
```

Two users running the same Gmail-integrated workflow would (in theory) collide on `gmail_message_id` PK. In practice Gmail message IDs are globally unique per Google account, so no real collision. But the model has no way to filter "show me followups for tenant X" — `EmailFollowup.query.all()` returns every tenant's followups.

**Fix:** add `user_id` column. Make composite PK (`user_id`, `gmail_message_id`) or add a surrogate key. Defer until SaaS rollout.

### Bug 3 — `TenantScopedSession` is broken for the models it claims to cover

`ospra_os/tenancy/queries.py:122-128` filters `model.tenant_id` but the 4 models in `DIRECT_TENANT_MODELS` use `user_id`. Either:
- (a) Fix the wrapper to filter `user_id` for these models, OR
- (b) Delete the `tenancy/queries.py` + `tenancy/dependencies.py` files entirely since they're effectively dead code (only 2 routes import them, and even those routes don't depend on the broken methods).

**Recommendation:** (a) when you actually want to use it. (b) is fine for now — the middleware-set context is what's doing the real work, the wrapper isn't.

---

## 4f — What was NOT touched in Pass 4

- No code changes. Pass 4 is an audit pass.
- `email_automation/` not modified (protected).
- AliExpress platform-wide token kept (intentional architecture).
- Frontend not audited (Pass 5).
- Test suite not audited (Pass 6).

---

## Summary

| Question | Answer |
|---|---|
| Is the app multi-tenant safe today (1 tenant)? | Yes. |
| Is the app multi-tenant safe with 2+ tenants? | No — `tiktok_tokens`, `email_followups`, hardcoded `"Oubon Shop"` in product analyzer, `OUBONSHOP_*` env prefix all need fixing. |
| Is the tenancy framework actually used? | Middleware yes. Query wrapper no (dead/broken). |
| How is tenant filtering enforced today? | Manual `user_id` filters in each of ~25 route files. Works but has no structural backstop. |
| Critical bug count | 0 in production. 3 design bugs that activate when the second tenant arrives. |
| New audit tooling | `/tmp/tenancy_audit.py` — re-runnable AST walker, classifies all 63 models in seconds. |

### Decisions for the user (sponce96@icloud.com)

These are not urgent today. They become urgent the day you onboard the second tenant.

1. **TikTok per-user vs. platform-wide?** Today it's platform-wide (one Oubon TikTok account). For SaaS, every user needs their own. Confirm: should every tenant connect their own TikTok account?
2. **`email_followups` — single-user only?** Today this only tracks Oubon's own customer-service follow-ups. Confirm: should other tenants get the same feature, or is this Oubon-internal?
3. **Hardcoded `"Oubon Shop"` in AI product analyzer** — this gets injected into every product-analysis prompt. Should be replaced with the tenant's own store name. OK to fix?
4. **`OUBONSHOP_*` env var prefix** — locks every deployment into `OUBONSHOP_*` env vars. For SaaS this should be `OSPRA_OS_*`. OK to rename when SaaS rollout starts (you'd have to update every Render env var)?
5. **Dead `TenantScopedSession`** — fix it (path A) or delete it (path B)? Fixing is the right long-term move; deleting is honest since today nothing depends on it working.

No commits made — this pass is informational only.
