# Admin / Smoke-Test Endpoints

All routes are mounted under `/api/discovery/`. Most require a Bearer
token (the standard auth middleware). Use these to verify each source
is connected and returning real data — without running a full
discovery cycle (which is slow and noisy).

---

## Quick reference

| Endpoint | What it does |
|---|---|
| `GET /sources-health` | **One-stop dashboard.** Pings every source in parallel. |
| `GET /test-meta-ads` | Meta Ad Library (Apify) sample + winner heuristic |
| `GET /test-amazon-movers` | Amazon Movers RSS — biggest 24h rank gains |
| `GET /test-amazon-new-releases` | Amazon New Releases RSS — last 30 days |
| `GET /test-etsy-trending` | Etsy trending (Apify) — lifestyle/handmade niches |
| `GET /test-tiktok-shop` | TikTok Shop — Apify + Partner API side-by-side |
| `GET /test-ae-ds` | AliExpress Dropshipping API — real merchant prices |
| `GET /test-cj` | CJ Dropshipping — keyword + category search |
| `POST /refresh-cj-categories` | Force-refresh CJ's category tree from live API |

---

## `GET /sources-health` — start here

The fastest way to answer "is everything working?". Hits every wired
source in parallel and returns a single dashboard view.

**Query params:**
- `niche` (default: `smart_home`) — niche to test all sources against
- `timeout_per_source` (default: `15`) — per-source timeout in seconds

**Example:**
```
GET /api/discovery/sources-health?niche=smart_home
```

**Response shape:**
```json
{
  "success": true,
  "niche": "smart_home",
  "summary": {
    "ok": 4, "no_data": 0, "skipped": 1,
    "not_configured": 1, "error": 0, "timeout": 1
  },
  "total_sources": 7,
  "sources": {
    "meta_ads_library": {"status": "ok", "ad_count": 42, "winners": 3},
    "amazon_movers_rss": {"status": "ok", "item_count": 5, "cached": false},
    "amazon_new_releases": {"status": "ok", "item_count": 5},
    "etsy_trending": {"status": "skipped", "detail": "no Etsy mapping for 'smart_home'"},
    "tiktok_shop": {"status": "ok", "apify_scraper": true, "partner_api_credentials": false},
    "aliexpress_ds_api": {"status": "ok", "detail": "..."},
    "cj_dropshipping": {"status": "ok", "dynamic_categories_loaded": true}
  }
}
```

**Status meanings:**
- `ok` — live data returned
- `no_data` — connected but empty (e.g. niche has no Etsy mapping)
- `skipped` — intentionally not run (e.g. niche not in mapping)
- `not_configured` — missing env var / token (action: add it)
- `error` — raised exception (action: read the `detail` field)
- `timeout` — took longer than `timeout_per_source` seconds

---

## Individual source endpoints

### Meta Ad Library — `GET /test-meta-ads`

Tests Task #10 winner-proof source.

**Query params:**
- `keyword` (default: `smart plug`) — Ad Library search term
- `country` (default: `US`) — ISO 3166-1 alpha-2
- `max_ads` (default: `20`, max `100`)
- `active_only` (default: `true`)

**Returns:** sample of 5 ads + aggregated advertisers + winners that
pass the 14d × 3-variants × Shopify-landing heuristic + a
`manual_url` you can paste into a browser to cross-check.

---

### Amazon Movers — `GET /test-amazon-movers`

Tests Task #12 winner-proof source (free public RSS).

**Query params:**
- `niche` (default: `smart_home`) — Ospra niche or raw Amazon slug
- `max_items` (default: `10`, max `50`)

**Returns:** sample items with ASIN, rank delta, price, extracted
trending keywords.

---

### Amazon New Releases — `GET /test-amazon-new-releases`

Tests Option A — products launched in last 30 days.

**Query params:** same as Movers (`niche`, `max_items`).

---

### Etsy Trending — `GET /test-etsy-trending`

Tests Option B — handmade/lifestyle trending products.

**Query params:**
- `niche` (default: `home_decor`)
- `max_items` (default: `10`, max `50`)

**Returns:** `no_etsy_category_for_niche` error for niches Etsy
doesn't cover (tech, fitness, gaming). That's expected behaviour,
not a bug.

---

### TikTok Shop — `GET /test-tiktok-shop`

Tests Task #11 — both Apify scraper (no creds needed) AND Partner API
(needs `TIKTOK_SHOP_APP_KEY` + `TIKTOK_SHOP_ACCESS_TOKEN`).

**Query params:**
- `niche` (default: `smart_home`)
- `keyword` (optional, overrides niche-derived search term)
- `max_items` (default: `10`, max `50`)

**Returns:** side-by-side comparison of both layers so you can see
which path is contributing data.

---

### AliExpress Dropshipping API — `GET /test-ae-ds`

Tests Task #24 — real merchant prices via DS API.

**Query params:**
- `product_id` (optional) — AE product_id to fetch detail for
- `feed_name` (default: `DS_Global_topsellers`)
- `feed_page_size` (default: `5`, max `20`)

**Returns:** availability + DS feed sample + per-product merchant
pricing detail (when `product_id` provided).

---

### CJ Dropshipping — `GET /test-cj`

**Query params:**
- `keyword` (default: `smart plug`)
- `niche` (default: `smart_home`)
- `limit` (default: `10`, max `50`)

**Returns:** keyword-search results + category-search results +
diagnostic info about the dynamic category map state.

---

### CJ Category Refresh — `POST /refresh-cj-categories`

Force-refresh CJ's category tree from `/product/getCategory`. Useful
when CJ has rotated category IDs and the dynamic map is out of date.

**Query params:**
- `force` (default: `false`) — bypass the 7-day TTL

**Returns:** number of entries in the refreshed map + sample keys.

---

## Common debugging patterns

**"Why is my discovery returning 0 products?"**
1. Hit `/sources-health` — if multiple sources are `error` or
   `timeout`, the issue is environmental (network, downstream APIs).
2. If one specific source is the issue, hit its individual endpoint
   to get the full error message.

**"Why aren't products I expect showing up?"**
1. Hit `/test-meta-ads` and `/test-amazon-movers` with the niche.
2. If they're returning real data, the issue is downstream — in
   scoring/filtering. The Score Breakdown UI on individual products
   will show which signals each product has.

**"Is my Apify token actually working?"**
- Hit `/sources-health`. All Apify-backed sources (`meta_ads_library`,
  `etsy_trending`, `tiktok_shop.apify_scraper`) should return `ok`.
- If they all return `not_configured`, your `APIFY_API_TOKEN` env var
  isn't set.
