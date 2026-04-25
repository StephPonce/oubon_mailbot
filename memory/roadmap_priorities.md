# Roadmap Priorities

Ordered list. Higher = sooner. Ship rules at the bottom are as important as the order.

---

## Now (in-flight — next 2–4 weeks)

1. **Pass 5 — Frontend cleanup (#30)**
   - Consume `tier_meta` in the discovery UI (show upgrade-nudge when `clamped=true`).
   - Fix `npm run lint` so we can flip CI from soft-fail to required.
   - Delete dead components / stale routes revealed by the lint pass.

2. **Pass 6 — Test suite consolidation (#31)**
   - Fix pre-existing failures: bcrypt, `groq` import, sqlalchemy fixtures.
   - Archive legacy `tests/test_tenant_isolation.py`.
   - Coverage for tier clamp + feature flags.

3. **Pass 4d — OAuth partner + prompt caching + docs (#34)**
   - Claude prompt caching on grading + support prompts (5-min TTL).
   - Disambiguate Product in `tenancy/queries.py` so the scaffold grows a Product-level test.
   - Shopify Partner App approval doc (OAuth scopes, privacy URL, data retention).

## Next (1–2 months, post-debt)

4. **TikTok Shop API (#36)** — new discovery source; weights 0.25 in scorer once data volume is meaningful.
5. **Pinterest Trends source (#37)** — via Apify; weights 0.15.
6. **PostHog wiring (#38)** — feature flags + acquisition funnel events. **This unblocks data-driven iteration of everything below.**

## Later (1–2 quarters)

7. **Refund-risk predictor** — model trained on supplier history + sentiment spread + category. Ship on Stratosphere first.
8. **Agency Mode (multi-client dashboard)** — Stratosphere add-on, priced at +$100/mo per 5 clients above the included 10.
9. **Embed Mode (white-label discovery widget)** — iframe + REST API. Targets consultancies.
10. **Mobile app (RN)** — discovery feed + support inbox. Build ONLY after PostHog data shows mobile session share >25%.

## Maybe / watchlist (don't build yet)

- Klaviyo partnership / integration
- Native TikTok-Shop-only tenant type
- On-device AI for grading (privacy play for EU merchants)
- Browser extension for scraping competitor stores

---

## API integrations — build vs. skip (Pass 4 decision)

### Build (in roadmap above)

1. **TikTok Shop API** — #36
2. **Pinterest Trends via Apify** — #37
3. **PostHog** — #38
4. **Claude prompt caching** — #34

### Skip (documented reasons)

1. **Instagram Graph API** — Meta's review cycle is brutal and the data overlaps with TikTok Shop + Pinterest. Low marginal value.
2. **Reddit API (paid tier)** — the free quota via an MCP is plenty for our signal needs; paid tier's cost doesn't justify it until we're 100x our current volume.
3. **Etsy** — different buyer archetype, no dropship fit, would dilute focus.
4. **Alibaba (B2B)** — our merchants buy AliExpress consumer listings, not wholesale pallets. Adding Alibaba expands scope without helping the persona.
5. **Stripe Connect** — we're on LemonSqueezy (D10). Don't reopen.
6. **Freshdesk / Intercom integrations** — merchants who have Freshdesk aren't buying our support AI; they already solved that problem.
7. **Webflow deploy** — our target is Shopify + WooCommerce. Webflow ecomm is a different persona.

---

## Ship rules (as important as the order)

- **Ship behind a feature flag.** Every new integration lives behind `Settings.FOO_ENABLED` + a PostHog flag. Default off in prod, on in Oubon's tenant for dogfooding.
- **Dogfood on Oubon first.** Any new discovery source runs on Oubon's catalog for at least 7 days before it's exposed to other tenants.
- **Variance-lock before shipping grading changes.** `scripts/test_ai_analysis_variance.py` must pass. Don't loosen variance bounds without a written reason in `memory/decisions.md`.
- **Never widen tenant blast radius casually.** Any change to `tenancy/` or `auth/` requires the tenant-isolation scaffold to pass AND an explicit mention in the commit body.
- **No speculative framework changes.** If a refactor doesn't serve a roadmap item above, punt it.
- **Pricing page changes require `memory/pricing.md` update in the same commit.** Prevents drift.
