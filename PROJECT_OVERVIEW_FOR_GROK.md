# Ospra OS Project Overview for Grok AI

**Date:** 2025-01-27
**Project:** E-commerce Multi-Store Management Platform
**Purpose:** This document provides Grok AI with complete context about the Ospra OS project architecture, tech stack, database schema, and custom logic.

---

## 🏗️ PROJECT STRUCTURE

```
Ospra OS/
├── frontend/                    # React + TypeScript + Vite
│   ├── src/
│   │   ├── components/         # Reusable UI components
│   │   │   ├── portfolio/      # Portfolio-specific components
│   │   │   ├── analytics/      # Analytics components (KPICard, RevenueChart)
│   │   │   └── ...
│   │   ├── pages/              # Main pages/routes
│   │   │   ├── PortfolioDashboard.tsx
│   │   │   ├── UnifiedProductsPage.tsx (tabs: Discovery, Inventory, Orders)
│   │   │   ├── CustomerAnalyticsPage.tsx
│   │   │   ├── EmailDashboard.tsx
│   │   │   └── ...
│   │   ├── contexts/           # React Context providers
│   │   │   ├── ProductsContext.tsx (global product state)
│   │   │   └── AIChatContext.tsx
│   │   ├── index.css           # Tailwind imports
│   │   ├── aurora.css          # Custom aurora background effects
│   │   └── main.tsx            # App entry point
│   ├── package.json
│   ├── tailwind.config.js
│   ├── tsconfig.json
│   └── vite.config.ts
│
├── ospra_os/                   # Python FastAPI Backend
│   ├── main.py                 # FastAPI app entry
│   ├── core/
│   │   └── settings.py         # Pydantic settings
│   ├── dashboard/
│   │   ├── routes.py           # Dashboard API endpoints
│   │   └── routes_multi_store.py
│   ├── intelligence/           # AI/ML product discovery
│   │   ├── unified_product_discovery.py
│   │   ├── velocity_detector.py
│   │   └── ...
│   ├── integrations/
│   │   ├── shopify/            # Shopify API integration
│   │   ├── aliexpress/         # AliExpress scraping
│   │   └── meta/               # Meta Ads integration
│   ├── email_automation/       # Gmail OAuth + automation
│   └── database/
│       └── multi_store_models.py
│
├── pyproject.toml              # Python dependencies (uv)
└── uv.lock

IMPORTANT EXCLUDED FOLDERS (DO NOT ZIP):
- frontend/node_modules/
- frontend/dist/
- frontend/build/
- __pycache__/
- .venv/
- .git/
- .idea/
- data/reports/
```

---

## 💻 TECH STACK

### Frontend
- **Framework:** React 18.3.1
- **Language:** TypeScript
- **Build Tool:** Vite 6.0.11
- **Styling:** Tailwind CSS 3.4.17
- **UI Components:** Custom components (no shadcn/ui, no Material-UI)
- **Icons:** Lucide React
- **HTTP Client:** Axios
- **Routing:** React Router DOM v7
- **State Management:** React Context API (ProductsContext, AIChatContext)

### Backend
- **Framework:** FastAPI (Python)
- **Package Manager:** uv (modern pip replacement)
- **Database:** SQLite (aiosqlite) with async SQLAlchemy
- **Authentication:** OAuth 2.0 (Gmail, Shopify)
- **AI Integration:** Claude API (Anthropic)
- **Web Scraping:** Apify, BeautifulSoup

### APIs & Integrations
- **Shopify Admin API** - Store/product/order management
- **AliExpress Affiliate API** - Product sourcing
- **Meta Ads API** - Ad automation
- **Gmail API** - Email automation
- **Apify Scrapers** - TikTok Shop, Amazon, Reddit sentiment

---

## 🎨 DESIGN SYSTEM

### Color Palette
```css
/* Primary Colors */
--brand-blue: #3b82f6;       /* Primary action color */
--success-green: #10b981;     /* Success states */

/* Background Colors */
--bg-primary: #030712;        /* Gray-950 */
--bg-secondary: #111827;      /* Gray-900 */
--bg-card: rgba(17, 24, 39, 0.5);  /* Gray-900/50 with backdrop blur */

/* Text Colors */
--text-primary: #f9fafb;      /* Gray-100 */
--text-secondary: #9ca3af;    /* Gray-400 */
--text-muted: #6b7280;        /* Gray-500 */

/* Border Colors */
--border-primary: #1f2937;    /* Gray-800 */
--border-secondary: rgba(255, 255, 255, 0.1);
```

### Design Patterns

#### Glassmorphic Cards
```tsx
className="bg-gray-900/50 backdrop-blur-lg border border-gray-800 rounded-xl p-6"
```

#### Gradient Headers
```tsx
className="bg-gradient-to-r from-blue-400 to-purple-500 bg-clip-text text-transparent"
```

#### Aurora Background
- 3 animated orbs with blur effects
- CSS keyframes in `aurora.css`
- Applied to main layout background

#### Responsive Grid System
- Mobile: 1 column
- Tablet (md): 2 columns
- Desktop (lg): 4 columns
- Large (xl): 6-7 columns

---

## 🗄️ DATABASE SCHEMA

### Technology
- **Type:** SQLite (development) → PostgreSQL (production ready)
- **ORM:** SQLAlchemy Async
- **Location:** `data/multi_store.db`

### Key Tables

#### `stores`
```sql
CREATE TABLE stores (
    id INTEGER PRIMARY KEY,
    store_name TEXT NOT NULL,
    platform TEXT NOT NULL,  -- 'shopify', 'amazon', 'woocommerce'
    api_key TEXT,
    api_secret TEXT,
    store_url TEXT,
    monthly_revenue REAL DEFAULT 0,
    total_revenue REAL DEFAULT 0,
    total_orders INTEGER DEFAULT 0,
    product_count INTEGER DEFAULT 0,
    active_products INTEGER DEFAULT 0,
    conversion_rate REAL DEFAULT 0,
    rank_position INTEGER,
    rank_change INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### `products`
```sql
CREATE TABLE products (
    id INTEGER PRIMARY KEY,
    store_id INTEGER REFERENCES stores(id),
    shopify_product_id TEXT,
    name TEXT NOT NULL,
    sku TEXT,
    price REAL,
    cost REAL,
    inventory_quantity INTEGER DEFAULT 0,
    velocity_daily REAL DEFAULT 0,  -- Sales per day
    trend_score REAL,               -- 0-100
    niche TEXT,
    image_url TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### `orders`
```sql
CREATE TABLE orders (
    id INTEGER PRIMARY KEY,
    store_id INTEGER REFERENCES stores(id),
    shopify_order_id TEXT,
    shopify_order_number TEXT,
    customer_name TEXT,
    customer_email TEXT,
    product_name TEXT,
    quantity INTEGER,
    total_price REAL,
    fulfillment_status TEXT,  -- 'fulfilled', 'unfulfilled', 'shipped'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### `discovered_products` (AI-powered discovery)
```sql
CREATE TABLE discovered_products (
    id INTEGER PRIMARY KEY,
    name TEXT,
    price REAL,
    cost REAL,
    velocity_score REAL,      -- 0.0-1.0 (product velocity/demand)
    trend_score REAL,          -- 0-100 (trending level)
    profit_margin REAL,
    niche TEXT,                -- 'smart_home', 'fitness', 'beauty', etc.
    source TEXT,               -- 'aliexpress', 'tiktok', 'amazon'
    supplier_url TEXT,
    image_url TEXT,
    data_sources JSONB,        -- JSON with all scraper data
    discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 🔌 API ENDPOINTS

### Base URLs
- **Frontend:** `http://localhost:5173`
- **Backend:** `http://localhost:8001`

### Portfolio/Dashboard
```typescript
GET /api/portfolio/overview
// Returns:
{
  total_revenue: number,
  monthly_revenue: number,
  active_stores: number,
  total_stores: number,
  total_products: number,
  active_products: number,
  avg_conversion_rate: number,
  total_orders: number,
  profit_margin?: number,
  roas?: number,
  avg_order_value?: number,
  best_performing_store: { name: string, revenue: number } | null,
  platforms: { [key: string]: number }
}

GET /api/portfolio/rankings
// Returns: StoreRanking[]
{
  id: number,
  store_name: string,
  platform: string,
  monthly_revenue: number,
  total_revenue: number,
  product_count: number,
  active_products: number,
  conversion_rate: number,
  rank_position: number,
  rank_change: number,
  url?: string,
  isActive: boolean
}
```

### Product Discovery
```typescript
GET /api/dashboard/v2/products?niche={niche}&page={page}
// Returns discovered products from AI engine
{
  products: Product[],
  total: number,
  page: number,
  per_page: number
}

GET /api/dashboard/v2/niches
// Returns available niches
{
  niches: [
    { id: 'smart_home', name: 'Smart Home', count: 234 },
    { id: 'fitness', name: 'Fitness & Sports', count: 189 },
    // ...
  ]
}
```

### Orders
```typescript
GET /api/dashboard/v2/orders
// Returns orders from all stores
{
  orders: Order[],
  total: number
}

POST /api/dashboard/v2/orders/{shopify_order_id}/tracking
// Add tracking info to order
Params: tracking_number, tracking_url, tracking_company
```

---

## 🧠 CUSTOM LOGIC & ALGORITHMS

### 1. Product Discovery Engine

**Location:** `ospra_os/intelligence/unified_product_discovery.py`

**Algorithm:**
```python
def calculate_velocity_score(product_data):
    """
    Velocity Score: 0.0 to 1.0
    Combines multiple signals to predict product success
    """
    # Signal 1: Sales velocity (orders per day)
    sales_velocity = product_data.get('orders_30d', 0) / 30

    # Signal 2: Search trend (Google Trends data)
    search_trend = product_data.get('trend_percentage', 0) / 100

    # Signal 3: Social buzz (TikTok views, Reddit mentions)
    social_score = min(product_data.get('tiktok_views', 0) / 1000000, 1.0)

    # Signal 4: Profit potential
    profit_score = min(product_data.get('profit_margin', 0) / 50, 1.0)

    # Weighted average
    velocity = (
        sales_velocity * 0.35 +
        search_trend * 0.25 +
        social_score * 0.25 +
        profit_score * 0.15
    )

    return min(max(velocity, 0.0), 1.0)  # Clamp 0-1
```

**Discovery Filters:**
- `velocity_score >= 0.5` (Medium-High demand)
- `profit_margin >= 15%` (Profitable)
- `price >= $10` and `price <= $200` (Sweet spot)
- `trend_score >= 60` (Trending)

### 2. Niche Classification

**Niches:**
```typescript
const NICHES = [
  'smart_home',      // Smart home devices, IoT
  'fitness',         // Fitness equipment, supplements
  'beauty',          // Skincare, makeup, beauty tools
  'tech',            // Gadgets, electronics
  'home_garden',     // Home decor, gardening
  'pets',            // Pet supplies
  'fashion',         // Clothing, accessories
  'kitchen',         // Kitchen gadgets, cookware
];
```

**Auto-Classification:**
Uses keywords + AI (Claude) to categorize products into niches.

### 3. Inventory Forecasting

**Location:** `frontend/src/pages/InventoryPage.tsx`

```typescript
interface InventoryForecast {
  days_of_stock: number;        // Days until stockout
  reorder_point: number;         // When to reorder
  estimated_stockout_date: string;
}

// Calculation
const daily_velocity = total_orders / days_since_added;
const days_of_stock = inventory / daily_velocity;
const reorder_point = daily_velocity * lead_time_days;
```

### 4. Customer Segmentation

**Location:** `frontend/src/pages/CustomerAnalyticsPage.tsx`

```typescript
// Customer Tiers (based on orders & spend)
const segments = {
  vip: {                    // 8% of customers
    orders: 5+,
    spend: $500+
  },
  loyal: {                  // 15% of customers
    orders: 3-4
  },
  regular: {                // 27% of customers
    orders: 2
  },
  one_time: {               // 50% of customers
    orders: 1
  }
};

// Lifetime Value (LTV) Calculation
const avg_ltv = total_revenue / unique_customers;
const top_spender = max(customer_total_spend);
```

---

## 🎯 KEY FEATURES

### Portfolio Dashboard
- **7 Metric Cards** (clickable with detail modals):
  1. Monthly Revenue
  2. Total Orders
  3. Active Stores
  4. Active Products
  5. Avg Conversion Rate
  6. Profit Margin
  7. ROAS
- **Store Rankings Table** with drag-sort
- **Revenue Chart** (7-day trend)
- **Date Range Selector** (Today, 7d, 30d, 90d, Year)
- **CSV Export**

### Products Page (3 Tabs)
1. **Product Discovery**
   - AI-powered product recommendations
   - Niche filters (Smart Home, Fitness, Beauty, etc.)
   - Velocity scores, trend indicators
   - Source badges (AliExpress, TikTok, Amazon)

2. **Inventory**
   - Current stock levels
   - Velocity tracking (sales/day)
   - Days of stock remaining
   - Reorder alerts

3. **Orders**
   - Order management
   - Fulfillment tracking
   - Add tracking numbers
   - Auto-email customers

### Customer Analytics
- **Empty State** when no orders exist
- **Derives stats from real orders** when available
- Customer segmentation (VIP, Loyal, Regular, One-time)
- Repeat rate, LTV, churn metrics

### Email Dashboard
- Gmail OAuth integration
- Email categorization (Inbox, Starred, Sent, Important, Trash)
- Compose emails
- Settings link to `/settings`

---

## 🔐 AUTHENTICATION & SECURITY

### OAuth Flows
1. **Gmail:** `.secrets/gmail_token.json`
2. **Shopify:** Store API keys in database
3. **AliExpress:** Affiliate credentials in env

### Environment Variables
```bash
# Backend (.env)
GOOGLE_OAUTH_CLIENT_ID=...
GOOGLE_OAUTH_CLIENT_SECRET=...
SHOPIFY_API_TOKEN=...
SHOPIFY_STORE=...
ANTHROPIC_API_KEY=...  # Claude AI

# Frontend (Vite uses import.meta.env)
VITE_API_BASE_URL=http://localhost:8001
```

---

## 🚀 CURRENT DEVELOPMENT STATUS

### ✅ Working Features
- Portfolio Dashboard with real-time data
- Product Discovery Engine (AI-powered)
- Multi-store management
- Order tracking
- Email dashboard
- Inventory forecasting
- Customer analytics (with real data)
- Clickable metric cards with detail modals

### 🚧 In Progress
- A/B Testing page (placeholder)
- Niche Analysis page (basic)
- Competitors page (basic)
- Live Trends page (placeholder)
- Rankings page (basic)

### 🎨 Design Notes for Grok
- **Theme:** Dark mode with aurora background effects
- **Glass morphism** extensively used (`backdrop-blur-lg`)
- **Gradients** for headers and accents
- **Consistent spacing:** Use Tailwind's spacing scale (p-4, p-6, gap-4, etc.)
- **Hover effects:** Scale, shadow, border color transitions
- **Icons:** Lucide React (already installed)
- **Animations:** CSS transitions (300ms ease), no heavy JS animations
- **Responsive:** Mobile-first, use Tailwind breakpoints (sm, md, lg, xl)

---

## 📦 HOW TO RUN

### Backend
```bash
cd "/Users/stephenponce/Documents/Ospra OS/Bots/Ospra OS"
uv run uvicorn ospra_os.main:app --reload --host 127.0.0.1 --port 8001
```

### Frontend
```bash
cd frontend
npm install
npm run dev
# Runs on http://localhost:5173
```

---

## 🎨 NAVIGATION STRUCTURE

```
Sidebar (10 items):
1. Portfolio       → /                (PortfolioDashboard)
2. Products        → /products        (UnifiedProductsPage - 3 tabs)
3. Customers       → /customers       (CustomerAnalyticsPage)
4. Niche Analysis  → /niches         (NicheAnalysisPage)
5. Competitors     → /competitors     (CompetitiveIntelPage)
6. Emails          → /emails          (EmailDashboard)
7. Live Trends     → /trends          (LiveTrendsPage)
8. Rankings        → /rankings        (RankingsPage)
9. A/B Testing     → /abtesting       (ABTestingPage)
10. Settings       → /settings        (EmailSettings)
```

---

## 💡 TIPS FOR GROK

1. **Match existing component patterns** - See `PortfolioDashboard.tsx` for card layouts
2. **Use existing contexts** - `ProductsContext`, `AIChatContext` already set up
3. **Tailwind classes only** - No inline styles, no CSS modules
4. **TypeScript interfaces** - All components are typed
5. **Async/await for API calls** - Use axios, handle errors with try/catch
6. **Empty states** - Show helpful messages when no data (see `CustomerAnalyticsPage.tsx`)
7. **Loading states** - Use spinner: `<div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>`

---

## 📝 RECENT CHANGES (Jan 27, 2025)

1. **Merged Analytics into Portfolio** - Reduced nav clutter
2. **Made metric cards clickable** - Show detail modals with charts
3. **Fixed Customer Analytics** - Now derives from real orders, shows empty state
4. **Fixed Email Dashboard** - Removed broken EmailSettingsModal import
5. **Added global product state** - ProductsContext persists across navigation
6. **Unified Products page** - 3 tabs: Discovery, Inventory, Orders

---

**END OF OVERVIEW**

This document should give you (Grok) everything needed to build features that perfectly match our existing codebase. Focus on consistency, use our design system, and follow the patterns in `PortfolioDashboard.tsx` and `CustomerAnalyticsPage.tsx` as references.
