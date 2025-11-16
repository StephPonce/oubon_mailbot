# Portfolio Dashboard - Multi-Store Management

**Location:** `/frontend/src/pages/PortfolioDashboard.tsx`

Complete React dashboard for managing multiple e-commerce stores in one unified interface.

---

## 📁 Files Created

### Main Page
- `/frontend/src/pages/PortfolioDashboard.tsx` - Main dashboard page

### Components
- `/frontend/src/components/portfolio/MetricCard.tsx` - Overview metric cards
- `/frontend/src/components/portfolio/StoreRankingsTable.tsx` - Store rankings table
- `/frontend/src/components/portfolio/RevenueChart.tsx` - Revenue trend chart
- `/frontend/src/components/portfolio/QuickActions.tsx` - Quick action buttons

---

## 🎨 Features

### 1. Overview Metrics (Top Row)

Four metric cards showing:
- **Total Revenue** - Monthly revenue with % change
- **Active Stores** - Count with change indicator
- **Total Products** - Count with weekly change
- **Avg Conversion** - Conversion rate across all stores

**Features:**
- ✅ Color-coded trend indicators (green up, red down)
- ✅ Icon badges for each metric
- ✅ Hover effects with shadows
- ✅ Responsive grid layout

### 2. Store & Platform Selectors

**Store Selector:**
- Dropdown to switch between stores or "All Stores" view
- Shows all connected stores with platform

**Platform Filter:**
- Button group: All, Shopify, Amazon, WooCommerce
- Active state highlighting
- Filters rankings table dynamically

**Add Store Button:**
- Gradient button with icon
- Opens add store modal (to be implemented)

### 3. Store Rankings Table

**Columns:**
- **Rank** - Position with colored badges (Gold #1, Silver #2, Bronze #3)
- **Change** - Rank change with ↑↓ arrows and color coding
- **Store** - Name with ID and external link icon
- **Platform** - Color-coded badge (Shopify=purple, Amazon=orange, etc.)
- **Revenue** - 30-day and total revenue
- **Conversion** - Conversion rate percentage
- **Products** - Active/total product count
- **Status** - Active/inactive badge

**Features:**
- ✅ Sortable by rank, revenue, conversion
- ✅ Click row to navigate to store dashboard
- ✅ Hover effects on rows
- ✅ Color-coded platform badges
- ✅ Rank change indicators with icons

### 4. Revenue Chart

**Chart Type:** Line chart using Recharts

**Features:**
- ✅ Last 30 days revenue trends
- ✅ Multiple lines (one per store + total)
- ✅ Color-coded by platform
- ✅ Interactive tooltip
- ✅ Legend with store names
- ✅ Summary stats (total, daily average)
- ✅ Growth indicator (+12.5%)

### 5. Quick Actions Panel

**Action Cards:**
1. **Discover Products** - Navigate to product discovery
2. **Add New Store** - Open add store modal
3. **View All Orders** - Navigate to orders page
4. **AI Settings** - Configure AI features

**Additional Stats:**
- AI Credits remaining
- Active tasks count

**Features:**
- ✅ Color-coded action cards
- ✅ Hover animations (scale, translate)
- ✅ Icon badges
- ✅ Navigation on click

### 6. Best Performer Badge

Shows the top-performing store with trophy icon and gradient background.

---

## 🔌 API Integration

### Endpoints Used

**GET /api/portfolio/overview**
```typescript
{
  total_revenue: number;
  monthly_revenue: number;
  active_stores: number;
  total_stores: number;
  total_products: number;
  active_products: number;
  avg_conversion_rate: number;
  best_performing_store: string | null;
  total_orders: number;
  platforms: Record<string, number>;
}
```

**GET /api/portfolio/rankings**
```typescript
[
  {
    id: number;
    store_name: string;
    platform: string;
    monthly_revenue: number;
    total_revenue: number;
    conversion_rate: number;
    product_count: number;
    active_products: number;
    rank_position: number;
    rank_change: number;
    rank_change_label: string;
  }
]
```

### Data Flow

1. **On Mount** - `useEffect` triggers data fetch
2. **Loading State** - Shows spinner while fetching
3. **Error State** - Shows error message with retry button
4. **Success State** - Renders dashboard with data
5. **Filtering** - Client-side filtering by platform

---

## 🎨 Styling

### Theme
- **Background:** `bg-gray-900` (dark)
- **Cards:** `bg-gray-800` with `border-gray-700`
- **Primary:** Blue gradient (`from-blue-500 to-purple-600`)
- **Accents:** Electric blue (`text-blue-400`)

### Platform Colors
```typescript
shopify:     purple (#8B5CF6)
amazon:      orange (#F97316)
woocommerce: blue   (#3B82F6)
etsy:        pink   (#EC4899)
ebay:        yellow (#EAB308)
```

### Responsive Breakpoints
- **Mobile:** 1 column grid
- **Tablet:** 2 column grid (`md:grid-cols-2`)
- **Desktop:** 4 column grid (`lg:grid-cols-4`)

---

## 📦 Dependencies

### Required Packages

```bash
# Install recharts for charts
npm install recharts

# Or with yarn
yarn add recharts
```

### Existing Dependencies
- ✅ React
- ✅ TypeScript
- ✅ Tailwind CSS
- ✅ Lucide React (icons)

---

## 🚀 Usage

### Add to Router

```typescript
// In App.tsx or Router.tsx
import PortfolioDashboard from './pages/PortfolioDashboard';

// Add route
<Route path="/portfolio" element={<PortfolioDashboard />} />
```

### Set as Homepage

```typescript
// Make portfolio the default page
<Route path="/" element={<PortfolioDashboard />} />
```

### Navigation

```typescript
// Navigate to portfolio
navigate('/portfolio');

// Navigate to specific store
navigate(`/store/${storeId}`);
```

---

## 🔧 Customization

### Change API Base URL

```typescript
// In PortfolioDashboard.tsx, update:
const API_BASE = 'http://localhost:8001';

// To your production URL:
const API_BASE = 'https://api.yourdomain.com';
```

### Add More Metrics

```typescript
// Add to metrics object:
metrics.newMetric = {
  value: overview.some_value,
  change: 5.2,
  trend: 'up' as const
};

// Add MetricCard:
<MetricCard
  title="New Metric"
  value={metrics.newMetric.value.toString()}
  change={metrics.newMetric.change}
  trend={metrics.newMetric.trend}
  icon={YourIcon}
  subtitle="Description"
/>
```

### Customize Platform Colors

```typescript
// In StoreRankingsTable.tsx:
const colors: Record<string, string> = {
  yourplatform: 'bg-color-500/20 text-color-400 border-color-500/50'
};
```

---

## 🎯 Future Enhancements

### Planned Features
1. **Real-time Updates** - WebSocket for live data
2. **Export Data** - CSV/PDF export functionality
3. **Date Range Picker** - Custom date ranges for charts
4. **Advanced Filters** - Filter by niche, revenue range, etc.
5. **Drag & Drop** - Reorder dashboard widgets
6. **Mobile App** - React Native version
7. **Notifications** - Push notifications for events
8. **Goals & Targets** - Set and track revenue goals

### Component Improvements
1. **Add Store Modal** - Complete add store workflow
2. **Store Details Page** - Individual store dashboard
3. **Product Discovery** - AI product finder integration
4. **Settings Page** - User preferences and configuration
5. **Analytics** - Detailed analytics and reports

---

## 🐛 Troubleshooting

### Recharts Not Found

**Error:** `Module not found: Can't resolve 'recharts'`

**Solution:**
```bash
cd frontend
npm install recharts
```

### API Connection Failed

**Error:** `Failed to fetch portfolio overview`

**Solution:**
1. Check backend is running: `curl http://localhost:8001/health`
2. Verify CORS settings in backend
3. Check API_BASE URL in code

### Type Errors

**Error:** TypeScript type mismatches

**Solution:**
1. Check API response matches interface
2. Add proper type guards
3. Use `unknown` and type narrowing if needed

---

## ✅ Testing Checklist

- [ ] Overview cards display correctly
- [ ] Store selector works
- [ ] Platform filter filters table
- [ ] Rankings table sorts correctly
- [ ] Chart renders with data
- [ ] Quick actions navigate properly
- [ ] Loading state shows spinner
- [ ] Error state shows message
- [ ] Responsive on mobile
- [ ] Responsive on tablet
- [ ] Responsive on desktop
- [ ] Best performer badge shows
- [ ] Platform badges color-coded
- [ ] Rank changes display correctly
- [ ] Hover effects work
- [ ] All icons render

---

## 📸 Screenshot Checklist

When implementing, verify these visual elements:

- ✅ Dark theme with blue accents
- ✅ Cards have shadows and borders
- ✅ Gradients on buttons and titles
- ✅ Smooth hover animations
- ✅ Color-coded trend indicators
- ✅ Platform badges with correct colors
- ✅ Chart with multiple colored lines
- ✅ Responsive grid layouts
- ✅ Professional, modern look

---

## 📚 Related Files

### Backend
- `/ospra_os/dashboard/routes_multi_store.py` - API routes
- `/ospra_os/database/multi_store_models.py` - Database models

### Documentation
- `/MULTI_STORE_SYSTEM_COMPLETE.md` - System overview
- `/ospra_os/dashboard/MULTI_STORE_API.md` - API reference

---

**Built with React + TypeScript + Tailwind CSS + Recharts**
**Part of OspraOS Multi-Store System**
