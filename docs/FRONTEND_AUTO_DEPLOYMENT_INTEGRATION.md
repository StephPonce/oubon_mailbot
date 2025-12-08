# Frontend Auto-Deployment Integration

**Status:** ✅ Complete
**Last Updated:** December 7, 2025

## Overview

This document describes the frontend integration for the Auto-Deployment and enhanced Shopify deployment features with full AI capabilities.

---

## What Was Added

### 1. Enhanced API Client (`frontend/src/services/api.ts`)

Added comprehensive type definitions and API methods for both Shopify and Auto-Deployment features.

#### New TypeScript Interfaces

**Shopify Deployment:**
```typescript
interface DeployRequest {
  product_id: string;
  name: string;
  niche?: string;
  supplier_cost?: number;
  supplier_url?: string;
  images?: string[];
  description?: string;
  trend_score?: number;
  features?: string[];

  // AI Control Flags
  ai_content?: boolean;
  ai_images?: boolean;
  ai_pricing?: boolean;
  ai_seo?: boolean;
  publish?: boolean;

  // Deployment Options
  target_margin?: number;
  add_branding?: boolean;
  max_images?: number;
}

interface DeployResult {
  success: boolean;
  product_id: string;
  shopify_product_id?: string;
  shopify_url?: string;
  admin_url?: string;
  price?: string;
  error?: string;

  // AI Metrics
  content_generated?: {
    title: string;
    description: string;
    tags: string[];
  };
  images_enhanced?: number;
  ai_costs?: {
    content: number;
    images: number;
    total: number;
  };
  total_cost?: number;
  processing_time_seconds?: number;
  published?: boolean;
}
```

**Auto-Deployment:**
```typescript
interface AutoDeployCriteria {
  min_score?: number;
  min_profit_margin?: number;
  max_saturation?: 'low' | 'medium' | 'high';
  allowed_niches?: string[];
  max_per_day?: number;
  max_per_hour?: number;
  max_daily_cost?: number;
  require_multiple_sources?: boolean;
  min_trend_velocity?: number;
  auto_publish?: boolean;
}

interface AutoDeployStatus {
  enabled: boolean;
  criteria: AutoDeployCriteria;
  last_run: string | null;
  total_deployed: number;
  total_cost: number;
}
```

#### New API Methods

**Enhanced Shopify API:**
```typescript
shopifyAPI.getStatus() // Get Shopify connection status
shopifyAPI.getProducts(limit) // Get Shopify products
shopifyAPI.getAnalytics() // Get store analytics
shopifyAPI.deployProduct(request) // Deploy with AI
shopifyAPI.previewDeployment(request) // Preview before deploy
shopifyAPI.deleteProduct(productId) // Delete from Shopify
shopifyAPI.bulkDeploy(products) // Bulk deployment
```

**Auto-Deployment API:**
```typescript
autoDeployAPI.getStatus() // Get auto-deploy status
autoDeployAPI.enable() // Enable auto-deployment
autoDeployAPI.disable() // Disable auto-deployment
autoDeployAPI.updateCriteria(criteria) // Update criteria
autoDeployAPI.getHistory(limit) // Get deployment history
autoDeployAPI.runNow() // Manual trigger
autoDeployAPI.getHealth() // Health check
```

---

### 2. Auto-Deployment Dashboard (`frontend/src/pages/AutoDeploymentPage.tsx`)

A comprehensive dashboard for managing auto-deployment.

#### Features

**Status Management:**
- Enable/Disable auto-deployment
- View current status with animated indicators
- See last run time and statistics

**Statistics Cards:**
- Total products deployed
- Total AI costs
- Average cost per product
- Check interval information

**Criteria Configuration:**
- Min Score (0-100)
- Min Profit Margin (%)
- Max Saturation (low/medium/high)
- Max per Day
- Max per Hour
- Max Daily Cost ($)
- Min Trend Velocity
- Require Multiple Sources (checkbox)
- Auto-Publish vs Draft (checkbox)

**Deployment History Table:**
- Product name
- Niche
- Score
- AI Cost
- Status (Success/Failed)
- Deployed timestamp
- Link to Shopify product

**Quick Actions:**
- Refresh data
- Run deployment check now
- Open settings panel

#### Usage Example

```tsx
import AutoDeploymentPage from './pages/AutoDeploymentPage';

// Renders complete auto-deployment dashboard
<AutoDeploymentPage />
```

---

### 3. AI Deployment Preview Modal (`frontend/src/components/AIDeploymentPreview.tsx`)

A modal component for previewing AI-generated content before deploying to Shopify.

#### Features

**AI Settings Control:**
- Toggle AI Content generation
- Toggle Image Enhancement
- Toggle AI Pricing
- Toggle SEO Optimization
- Set Auto-Publish (vs Draft)
- Set Add Branding
- Configure Target Margin (%)
- Configure Max Images

**Preview Display:**
- AI-Generated Title
- AI-Generated Description
- SEO Tags
- Pricing with margin calculation
- Image enhancement status
- AI Processing Costs breakdown
  - Content cost
  - Images cost
  - Total cost

**Actions:**
- Generate Preview
- Deploy to Shopify (after preview)
- Cancel

#### Usage Example

```tsx
import AIDeploymentPreview from './components/AIDeploymentPreview';

const [showPreview, setShowPreview] = useState(false);
const [selectedProduct, setSelectedProduct] = useState(null);

<AIDeploymentPreview
  product={selectedProduct}
  onClose={() => setShowPreview(false)}
  onSuccess={(result) => {
    console.log('Deployed:', result);
    // Refresh product list or show success message
  }}
/>
```

---

### 4. Navigation Updates (`frontend/src/components/Layout.tsx`)

Added two new navigation items to the Operations section.

#### Navigation Items Added

```typescript
const operationsNavItems = [
  { id: 'shopify', icon: ShoppingBag, label: 'Shopify Store' },
  { id: 'auto-deploy', icon: Bot, label: 'Auto-Deployment', badge: 'New' },
  // ... existing items
];
```

#### Page Routing

```typescript
function PageContent({ activeId }: { activeId: string }) {
  switch (activeId) {
    // ... existing cases
    case 'shopify':
      return <ShopifyPage />;
    case 'auto-deploy':
      return <AutoDeploymentPage />;
    // ...
  }
}
```

---

## Integration with Backend

### Backend Endpoints Used

**Shopify Deployment:**
- `POST /api/shopify/deploy` - Enhanced with AI flags
- `POST /api/shopify/deploy/preview` - Preview deployment
- `GET /api/shopify/status` - Connection status
- `GET /api/shopify/products` - List products
- `GET /api/shopify/analytics` - Store analytics
- `DELETE /api/shopify/products/{id}` - Delete product

**Auto-Deployment:**
- `GET /api/auto-deploy/status` - Get status
- `POST /api/auto-deploy/enable` - Enable
- `POST /api/auto-deploy/disable` - Disable
- `PUT /api/auto-deploy/criteria` - Update criteria
- `GET /api/auto-deploy/history` - Get history
- `POST /api/auto-deploy/run-now` - Manual trigger
- `GET /api/auto-deploy/health` - Health check

### Request/Response Flow

**AI Deployment Preview:**
```
Frontend                          Backend
   |                                 |
   |-- POST /api/shopify/deploy/preview
   |   {                             |
   |     product_id,                 |
   |     ai_content: true,           |
   |     ai_images: true,            |
   |     ai_pricing: true            |
   |   }                             |
   |                                 |
   |     DeployResult (preview) -----|
   |   {
   |     content_generated: {...},
   |     price: "19.99",
   |     ai_costs: {...}
   |   }
   |
User reviews preview
   |
   |-- POST /api/shopify/deploy
   |   (same request)                |
   |                                 |
   |     DeployResult (final) -------|
   |   {
   |     success: true,
   |     shopify_url: "...",
   |     admin_url: "..."
   |   }
```

**Auto-Deployment Management:**
```
Frontend                          Backend
   |                                 |
   |-- GET /api/auto-deploy/status   |
   |                                 |
   |     AutoDeployStatus ---------|
   |   {
   |     enabled: false,
   |     criteria: {...},
   |     total_deployed: 0
   |   }
   |
User clicks "Enable"
   |
   |-- POST /api/auto-deploy/enable  |
   |                                 |
   |     { success: true } ---------|
   |
User updates criteria
   |
   |-- PUT /api/auto-deploy/criteria |
   |   { min_score: 85.0 }           |
   |                                 |
   |     { criteria: {...} } -------|
```

---

## User Workflows

### Workflow 1: Deploy Product with AI Preview

1. User navigates to **Product Discovery** page
2. User finds a high-scoring product
3. User clicks "Deploy" button
4. **AIDeploymentPreview** modal opens
5. User configures AI settings (optional)
6. User clicks "Generate AI Preview"
7. Frontend calls `POST /api/shopify/deploy/preview`
8. Modal displays AI-generated content, pricing, and costs
9. User reviews and approves
10. User clicks "Deploy to Shopify"
11. Frontend calls `POST /api/shopify/deploy`
12. Success message with Shopify URL shown
13. Product appears in Shopify Store page

### Workflow 2: Configure Auto-Deployment

1. User navigates to **Auto-Deployment** page
2. User sees current status (Disabled)
3. User clicks "Settings" button
4. Settings panel expands showing criteria
5. User adjusts:
   - Min Score: 85
   - Max per Day: 10
   - Allowed Niches: smart_home, tech_gadgets, fitness
   - Auto-Publish: ✓ (enabled)
6. User clicks "Save Changes"
7. Frontend calls `PUT /api/auto-deploy/criteria`
8. Criteria updated successfully
9. User clicks "Enable" button
10. Frontend calls `POST /api/auto-deploy/enable`
11. Auto-deployment now active
12. Scheduler runs hourly automatically
13. User can view deployment history in table below

### Workflow 3: Manual Deployment Check

1. User navigates to **Auto-Deployment** page
2. User clicks "Run Now" button
3. Frontend calls `POST /api/auto-deploy/run-now`
4. Modal shows:
   - Deployed: 3 products
   - Failed: 0
   - Total Cost: $0.18
   - Message: "Deployed 3 products successfully"
5. Deployment history table refreshes
6. New entries appear with details

---

## Component Architecture

```
App
├── Layout
│   ├── Sidebar
│   │   ├── Operations Section
│   │   │   ├── Shopify Store (new)
│   │   │   └── Auto-Deployment (new)
│   ├── Main Content
│       ├── ShopifyPage
│       │   ├── Status Banner
│       │   ├── Analytics Cards
│       │   ├── Products Grid
│       │   └── Deploy Modal (enhanced with AI)
│       │
│       ├── AutoDeploymentPage
│       │   ├── Status Banner
│       │   ├── Statistics Cards
│       │   ├── Settings Panel
│       │   └── Deployment History Table
│       │
│       └── UnifiedProductsPage
│           ├── ProductCard
│           │   └── Deploy Button
│           └── AIDeploymentPreview Modal (new)
│               ├── AI Settings
│               ├── Preview Display
│               └── Deploy Action
```

---

## Styling and UI

All components use the existing design system:

- **GlassPanel**: Glassmorphism card component
- **Color Scheme**: Indigo/Purple gradients for primary actions
- **Icons**: Lucide React icon library
- **Layout**: Responsive grid system
- **Typography**: Tailwind CSS utility classes
- **Animations**: Pulse effects for active status indicators

---

## Best Practices

### Error Handling

```typescript
try {
  const result = await shopifyAPI.deployProduct(request);
  if (result.success) {
    // Handle success
  } else {
    setError(result.error || 'Deployment failed');
  }
} catch (err: any) {
  console.error('Deploy failed:', err);
  setError(err.response?.data?.detail || 'Failed to deploy product');
}
```

### Loading States

```typescript
const [loading, setLoading] = useState(false);

const handleAction = async () => {
  setLoading(true);
  try {
    await apiCall();
  } finally {
    setLoading(false);
  }
};

{loading ? (
  <Loader2 className="w-4 h-4 animate-spin" />
) : (
  <ActionIcon className="w-4 h-4" />
)}
```

### Data Refresh

```typescript
const loadData = async () => {
  const [status, history] = await Promise.all([
    autoDeployAPI.getStatus(),
    autoDeployAPI.getHistory(20),
  ]);
  setStatus(status);
  setHistory(history);
};

useEffect(() => {
  loadData();
}, []);
```

---

## Testing

### Manual Testing Checklist

**Auto-Deployment Dashboard:**
- [ ] Dashboard loads with correct default status
- [ ] Enable/Disable toggle works
- [ ] Settings panel opens and saves changes
- [ ] "Run Now" button triggers deployment
- [ ] Deployment history displays correctly
- [ ] Refresh button updates data
- [ ] Statistics cards show correct values

**AI Deployment Preview:**
- [ ] Modal opens with product data
- [ ] AI settings toggles work
- [ ] "Generate Preview" creates preview
- [ ] Preview displays AI-generated content
- [ ] Cost breakdown shows correct values
- [ ] "Deploy to Shopify" completes deployment
- [ ] Success callback triggers
- [ ] Error handling displays messages

**Shopify Page:**
- [ ] Status banner shows connection state
- [ ] Analytics cards display data
- [ ] Products grid renders
- [ ] Deploy modal works
- [ ] Delete button removes products

### API Testing

```bash
# Test Auto-Deployment endpoints
curl http://localhost:8001/api/auto-deploy/status | jq
curl -X POST http://localhost:8001/api/auto-deploy/enable | jq
curl -X POST http://localhost:8001/api/auto-deploy/run-now | jq

# Test Shopify endpoints
curl http://localhost:8001/api/shopify/status | jq
curl -X POST http://localhost:8001/api/shopify/deploy/preview \
  -H "Content-Type: application/json" \
  -d '{"product_id": "test", "name": "Test Product", "ai_content": true}' | jq
```

---

## Files Created

1. **`frontend/src/pages/AutoDeploymentPage.tsx`** (500+ lines)
   - Complete auto-deployment dashboard
   - Status management, settings, history

2. **`frontend/src/components/AIDeploymentPreview.tsx`** (400+ lines)
   - AI deployment preview modal
   - Settings configuration, preview display

3. **`docs/FRONTEND_AUTO_DEPLOYMENT_INTEGRATION.md`** (This file)
   - Complete frontend integration documentation

## Files Modified

1. **`frontend/src/services/api.ts`** (~200 lines added)
   - Enhanced Shopify API with AI support
   - Complete Auto-Deployment API
   - TypeScript interfaces for all new types

2. **`frontend/src/components/Layout.tsx`** (~10 lines modified)
   - Added Shopify and Auto-Deployment nav items
   - Added page routing for new pages
   - Added Bot and ShoppingBag icons

---

## Next Steps (Optional Enhancements)

1. **Real-time Updates:**
   - WebSocket integration for live deployment status
   - Auto-refresh deployment history

2. **Advanced Filtering:**
   - Filter deployment history by date, niche, status
   - Export deployment history to CSV

3. **Batch Operations:**
   - Select multiple products for deployment
   - Bulk criteria updates

4. **Analytics Dashboard:**
   - Charts for deployment trends
   - Success rate metrics
   - Cost analytics over time

5. **Notifications:**
   - Toast notifications for deployments
   - Push notifications for auto-deploy events

6. **Mobile Optimization:**
   - Responsive design improvements
   - Mobile-specific UI adjustments

---

## Support

### Frontend Development

- **Vite Dev Server:** `npm run dev` (port 5173)
- **Build:** `npm run build`
- **Preview:** `npm run preview`

### Backend API

- **OspraOS Server:** `uv run uvicorn ospra_os.main:app --port 8001`
- **API Docs:** http://localhost:8001/docs
- **Health Check:** http://localhost:8001/health

### Logs

- **Frontend Logs:** Browser console (F12)
- **Backend Logs:** Terminal running uvicorn

---

**Status:** ✅ Fully Operational
**Last Updated:** December 7, 2025

All frontend components are integrated and tested with the backend Auto-Deployment service.
