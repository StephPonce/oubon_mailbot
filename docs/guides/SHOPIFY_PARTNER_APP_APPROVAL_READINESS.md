# Shopify Partner App — Approval Readiness Checklist

**Last updated:** 2026-04 (Pass 4d)
**Status:** Pre-submission. Treat every "🟡" as a blocker before hitting *Submit for review* in the Shopify Partner dashboard.

This doc is the companion to `SHOPIFY_OAUTH_SETUP_GUIDE.md`. That guide tells a developer how to wire the OAuth flow end-to-end. **This guide** is the checklist Shopify's App Review team uses when deciding whether to publish a public app. Everything below maps to a specific criterion in Shopify's "Requirements for apps" rubric or to a GDPR / data-handling obligation that Shopify enforces on public apps.

> Scope: this doc only covers the things that change between a working internal app and an approvable public app. Pricing, merchant onboarding UX, and billing (Shopify Billing API) are handled in separate docs.

---

## 1. OAuth scopes — request the minimum

Shopify app review rejects apps that ask for more scopes than they demonstrably use. Our current authorization scope list (`SHOPIFY_SCOPES` in `ospra_os/api/shopify_oauth_routes.py`) asks for 24 scopes. The reviewer's perspective is: every scope we request is data we can exfiltrate, so each one needs a visible justification inside the app's UI within one week of install.

**Current scope set (24):**

```
read_products, write_products,
read_orders, write_orders,
read_customers, write_customers,
read_inventory, write_inventory, read_locations,
read_fulfillments, write_fulfillments, read_shipping, write_shipping,
read_analytics,
read_content, write_content,
read_price_rules, write_price_rules, read_discounts, write_discounts,
read_marketing_events, write_marketing_events,
read_themes,
read_draft_orders, write_draft_orders,
read_checkouts, write_checkouts,
```

**Recommended minimum-viable set for Ospra's launch feature set (14):**

| Scope | Justification shown in merchant UI |
|---|---|
| `read_products`, `write_products` | Product discovery → deploy to store |
| `read_orders` | Pipeline analytics + performance learning |
| `read_customers` | Email automation recipient resolution |
| `read_inventory`, `write_inventory`, `read_locations` | Stock sync for deployed products |
| `read_fulfillments`, `write_fulfillments` | Order status tracking |
| `read_analytics` | Store dashboard metrics |
| `read_content`, `write_content` | AI-generated blog + collection copy |
| `read_price_rules`, `write_price_rules` | Auto-pricing optimization |

**To drop (deferred to post-launch):**

- `write_orders` — not used. Orders are read-only in current flows.
- `write_customers` — customer writes belong to Shopify's email+SMS surfaces we don't own.
- `read_marketing_events`, `write_marketing_events` — marketing events API is not wired.
- `read_themes` — theme reads are not in any live code path.
- `read_draft_orders`, `write_draft_orders` — B2B flow is post-launch.
- `read_checkouts`, `write_checkouts` — not used; Shopify Checkout APIs require separate approval.
- `read_shipping`, `write_shipping` — Shipping API access is reserved and will be rejected on review without a business case.
- `read_discounts`, `write_discounts` — duplicate of price_rules for our use case.

🟡 **Action:** before submission, gate the expanded scopes behind a feature flag. Ship the 14-scope set, and re-request additional scopes incrementally *after* the corresponding feature is user-visible and documented.

---

## 2. Required app URLs

Configured in Partner dashboard → **App setup → URLs**. All four must be production HTTPS URLs before submission.

| Field | Value |
|---|---|
| App URL | `https://app.ospra.os/` |
| Allowed redirection URL(s) | `https://app.ospra.os/oauth/shopify/callback` |
| Privacy policy | `https://ospra.os/legal/privacy` |
| Support email | `support@ospra.os` |

Environment variable that has to match: `OUBONSHOP_SHOPIFY_REDIRECT_URI` (see `.env.example`). If the Partner dashboard value and the env value diverge, Shopify returns a 400 at the OAuth callback with no recoverable error message.

🟡 **Action:** point the Privacy policy URL at a real page. Stubs like `/privacy-coming-soon` fail automated pre-submission checks.

---

## 3. Mandatory GDPR webhooks

Every public app must implement three GDPR-mandated webhooks. Shopify pings these during review with a test payload and rejects the app if any returns a non-200.

| Topic | Purpose | Route (to wire) |
|---|---|---|
| `customers/data_request` | Merchant requests a copy of a customer's data we hold | `POST /api/shopify/webhooks/customers/data_request` |
| `customers/redact` | Merchant requests customer data deletion | `POST /api/shopify/webhooks/customers/redact` |
| `shop/redact` | 48h after uninstall, Shopify asks us to delete everything for the shop | `POST /api/shopify/webhooks/shop/redact` |

In addition, wire `app/uninstalled` to soft-delete the `Store` row and revoke the stored OAuth token. This is a convenience webhook (not strictly required for review) but prevents stale tokens and is flagged in post-submission hygiene audits.

🟡 **Action:** these three routes are **not yet implemented**. Create `ospra_os/api/shopify_gdpr_webhooks.py` exposing the four endpoints above. Each must:
1. Verify the `X-Shopify-Hmac-Sha256` header against `SHOPIFY_API_SECRET`.
2. Return `200` within 5 seconds even if the underlying work is queued (use `BackgroundTasks`).
3. Log a structured audit entry with `shop_domain`, `topic`, `hmac_valid`, `action_taken`.

Test payload examples are in the Partner dashboard → **API credentials → Webhook test**.

---

## 4. Data handling policy

Reviewers read the privacy policy and cross-check it against our scope requests. The policy page must answer these six questions concretely, not with generic boilerplate:

1. **What merchant data do we store?** Product titles, images, inventory counts, order IDs + status (never PAN/card data).
2. **What customer data do we store?** Email, first name, order history summary. We do **not** store shipping addresses, phone numbers, or credit-card data.
3. **Where is it stored?** Postgres 15 on AWS `us-east-1`, encrypted at rest (AES-256) via RDS KMS. Application-layer encryption for OAuth tokens via `ospra_os.security.credential_encryption` (AES-GCM, per-tenant DEK).
4. **Who has access?** Ospra's on-call engineers (audit-logged); Anthropic/OpenAI via inference APIs with zero-retention commits; no third-party ad / analytics brokers.
5. **How long do we keep it?** 30 days after store disconnect (GDPR `shop/redact` grace window); 7-day rolling window for inference logs.
6. **How do users export / delete?** Self-serve in the app under Settings → Data & Privacy; the same handlers wired to the GDPR webhooks.

🟡 **Action:** answers 1–5 match the implementation; answer 6 requires a frontend Settings → Data & Privacy page (`frontend/src/pages/Settings/DataPrivacy.jsx`) that calls the same GDPR handlers the webhooks call. Not yet built.

---

## 5. Submission checklist

Order matters — the earlier items gate the later ones. Shopify's dashboard does not allow you to submit while any required field is missing, but it will happily let you submit with stale or placeholder values, and those get rejected with a 2–4 week review cycle cost.

- [x] Scopes trimmed to the 14-scope minimum-viable set (#41)
- [ ] `App URL`, `Redirect URL`, `Privacy policy`, `Support email` set to prod HTTPS values
- [ ] `OUBONSHOP_SHOPIFY_REDIRECT_URI` in prod `.env` matches the Partner dashboard redirect URL
- [x] Three GDPR webhooks (`customers/data_request`, `customers/redact`, `shop/redact`) implemented and returning 200 on Shopify's test payload — `ospra_os/security/gdpr.py` + `ospra_os/api/webhook_routes.py`, tested in `tests/test_gdpr.py` (#42)
- [x] `app/uninstalled` webhook implemented — store soft-delete + Shopify-billed-tier downgrade in `ospra_os/webhooks/shopify_webhooks.py::process_app_uninstalled` (#44)
- [ ] HMAC verification on every inbound Shopify webhook (we have this for OAuth callback; it needs extending to the webhooks)
- [x] Billing integration via Shopify Billing API (`appSubscriptionCreate` in 2024-10 API) — `ospra_os/payments/shopify_billing.py` + two routes `POST /api/subscription/shopify/create-charge` / `GET /api/subscription/shopify/activate`, tested in `tests/test_shopify_billing.py` (#44)
- [ ] Listing assets: 1 app icon (1200×1200), 3+ screenshots (1600×900), 1 feature video (optional but boosts approval rate), short description (≤120 chars), long description (markdown, ≤2000 chars)
- [ ] Test store with populated data for reviewers; credentials in the Partner dashboard "Test store access" field
- [ ] Install walkthrough video (60–90s, demonstrates install → first value within 5 min)
- [ ] Support response SLA documented (≤24h business-hour response)

---

## 6. Known gaps vs. approval (2026-04 status)

| Gap | Blocking? | Owner | Target |
|---|---|---|---|
| GDPR webhooks not implemented | ✅ Done | Backend | #42 — landed |
| Settings → Data & Privacy page not built | ✅ Done | Frontend | #43 — landed |
| Shopify Billing API integration | ✅ Done | Backend | #44 — landed |
| Scope list not yet trimmed | ✅ Done | Backend | #41 — landed |
| Privacy policy URL is a stub | 🟡 Should | Legal/Ops | blocker for submission |
| Listing assets (screenshots, video) | 🟡 Should | Design | blocker for submission |
| HMAC verification on non-OAuth Shopify webhooks | 🟡 Should | Backend | follow-up |

**Bottom line (2026-04 update):** all four 🔴 code blockers are now resolved. Submission is gated on three remaining 🟡 items — the privacy policy URL, listing assets, and extending HMAC verification to non-OAuth webhooks. The first two are non-code work; the third is a focused follow-up.

---

## 7. Related docs

- `docs/guides/SHOPIFY_OAUTH_SETUP_GUIDE.md` — how to wire OAuth end-to-end (developer-facing).
- `docs/SHOPIFY_SETUP_GUIDE.md` — internal / single-tenant connection flow (legacy; not the public-app path).
- `.env.example` — the canonical source of required env vars. Look for the `# [REQUIRED][SHOPIFY]` block.
