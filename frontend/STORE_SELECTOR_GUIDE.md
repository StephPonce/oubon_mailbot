# Store Selector Component - Usage Guide

**Location:** `/frontend/src/components/StoreSelector.tsx`

A comprehensive component for switching between stores in the multi-store dashboard.

---

## 🎯 Features

### 1. Store Dropdown
- **All Stores Option** - View portfolio of all stores
- **Individual Stores** - List of all connected stores
- **Platform Badges** - Color-coded platform indicators
- **Store Stats** - Revenue and product count preview
- **Search Functionality** - Filter stores by name
- **Active Indicator** - Green dot for active stores

### 2. Platform Filter Buttons
- **All Platforms** - Show all stores (default)
- **Shopify Only** - Filter to Shopify stores
- **Amazon Only** - Filter to Amazon stores
- **WooCommerce Only** - Filter to WooCommerce stores
- **Store Count Badges** - Shows number of stores per platform

### 3. Add Store Button
- **Prominent CTA** - Gradient blue-to-purple button
- **Hover Effects** - Scale and shadow on hover
- **Callback Handler** - Triggers onAddStore function

### 4. Current Store Stats Panel
- **Monthly Revenue** - Current month revenue
- **Active Products** - Active/total product count
- **Conversion Rate** - Current conversion percentage
- **Total Revenue** - All-time revenue
- **Only shown when a store is selected**

---

## 📦 Props Interface

```typescript
interface Store {
  id: number;
  store_name: string;
  platform: string;
  monthly_revenue: number;
  total_revenue: number;
  product_count: number;
  active_products: number;
  conversion_rate: number;
  status: 'active' | 'inactive';
}

interface StoreSelectorProps {
  stores: Store[];              // Array of all stores
  activeStore: Store | null;    // Currently selected store (null = all stores)
  onSwitch: (store: Store | null) => void;  // Callback when switching stores
  onAddStore: () => void;       // Callback for add store button
}
```

---

## 🚀 Basic Usage

### Import and Use

```tsx
import StoreSelector from '../components/StoreSelector';

function Dashboard() {
  const [stores, setStores] = useState<Store[]>([]);
  const [activeStore, setActiveStore] = useState<Store | null>(null);

  // Fetch stores from API
  useEffect(() => {
    fetch('http://localhost:8001/api/portfolio/rankings')
      .then(res => res.json())
      .then(data => setStores(data));
  }, []);

  // Handle store switch
  const handleSwitch = (store: Store | null) => {
    setActiveStore(store);
    console.log('Switched to:', store ? store.store_name : 'All Stores');
  };

  // Handle add store
  const handleAddStore = () => {
    console.log('Open add store modal');
    // Open your add store modal here
  };

  return (
    <div>
      <StoreSelector
        stores={stores}
        activeStore={activeStore}
        onSwitch={handleSwitch}
        onAddStore={handleAddStore}
      />

      {/* Rest of your dashboard */}
      <div className="p-6">
        {activeStore ? (
          <h2>Viewing: {activeStore.store_name}</h2>
        ) : (
          <h2>Viewing: All Stores</h2>
        )}
      </div>
    </div>
  );
}
```

---

## 🎨 Styling

### Theme
- **Sticky Header** - Stays at top when scrolling (`sticky top-0`)
- **Backdrop Blur** - Frosted glass effect (`backdrop-blur-sm`)
- **Dark Background** - `bg-gray-900/95` with transparency
- **Electric Blue Accents** - Highlights and buttons

### Platform Colors

```typescript
shopify:     Purple (#8B5CF6)
amazon:      Orange (#F97316)
woocommerce: Blue   (#3B82F6)
etsy:        Pink   (#EC4899)
ebay:        Yellow (#EAB308)
```

### Responsive Design
- **Mobile**: Stacked layout
- **Tablet**: Side-by-side on large screens
- **Desktop**: Full horizontal layout

---

## 🔧 Advanced Usage

### With Router Navigation

```tsx
import { useNavigate } from 'react-router-dom';

function Dashboard() {
  const navigate = useNavigate();

  const handleSwitch = (store: Store | null) => {
    if (store) {
      navigate(`/store/${store.id}`);
    } else {
      navigate('/portfolio');
    }
  };

  return (
    <StoreSelector
      stores={stores}
      activeStore={activeStore}
      onSwitch={handleSwitch}
      onAddStore={() => navigate('/add-store')}
    />
  );
}
```

### With Modal Integration

```tsx
import { useState } from 'react';
import AddStoreModal from './AddStoreModal';

function Dashboard() {
  const [showAddModal, setShowAddModal] = useState(false);

  return (
    <>
      <StoreSelector
        stores={stores}
        activeStore={activeStore}
        onSwitch={setActiveStore}
        onAddStore={() => setShowAddModal(true)}
      />

      {showAddModal && (
        <AddStoreModal
          onClose={() => setShowAddModal(false)}
          onSuccess={(newStore) => {
            setStores([...stores, newStore]);
            setShowAddModal(false);
          }}
        />
      )}
    </>
  );
}
```

### With URL Query Params

```tsx
import { useSearchParams } from 'react-router-dom';

function Dashboard() {
  const [searchParams, setSearchParams] = useSearchParams();
  const storeId = searchParams.get('store');

  const activeStore = stores.find(s => s.id === Number(storeId)) || null;

  const handleSwitch = (store: Store | null) => {
    if (store) {
      setSearchParams({ store: store.id.toString() });
    } else {
      setSearchParams({});
    }
  };

  return (
    <StoreSelector
      stores={stores}
      activeStore={activeStore}
      onSwitch={handleSwitch}
      onAddStore={() => setSearchParams({ action: 'add-store' })}
    />
  );
}
```

---

## 🎯 Features Breakdown

### Dropdown Features
- ✅ **Search stores** - Real-time filtering
- ✅ **Platform badges** - Visual platform identification
- ✅ **Store stats preview** - Revenue and products
- ✅ **Active indicators** - Green dot for active stores
- ✅ **All stores option** - Portfolio view
- ✅ **Keyboard navigation** - Arrow keys support
- ✅ **Click outside to close** - Automatic dropdown close

### Filter Features
- ✅ **Platform counts** - Show stores per platform
- ✅ **Active state** - Highlighted selected filter
- ✅ **Combined filtering** - Platform + search query
- ✅ **Smooth transitions** - Animated state changes

### Stats Panel Features (Active Store)
- ✅ **Monthly revenue** - Current month performance
- ✅ **Product metrics** - Active vs total products
- ✅ **Conversion rate** - Current conversion %
- ✅ **Total revenue** - All-time revenue
- ✅ **Icon badges** - Visual metric indicators
- ✅ **Responsive grid** - Adapts to screen size

---

## 📱 Mobile Optimization

### Responsive Breakpoints
```css
/* Mobile (< 768px) */
- Stacked layout
- Full-width buttons
- Collapsible stats

/* Tablet (768px - 1024px) */
- Side-by-side store selector and add button
- 2-column stats grid

/* Desktop (> 1024px) */
- Horizontal layout
- 4-column stats grid
- Full feature visibility
```

---

## 🎨 Customization

### Change Platform Colors

```tsx
// In StoreSelector.tsx, modify PLATFORM_COLORS
const PLATFORM_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  yourplatform: {
    bg: 'bg-color-500/20',
    text: 'text-color-400',
    border: 'border-color-500/50'
  }
};
```

### Add More Platforms

```tsx
// In StoreSelector.tsx, modify PLATFORMS
const PLATFORMS = [
  { id: 'all', name: 'All Platforms', color: 'blue' },
  { id: 'shopify', name: 'Shopify Only', color: 'purple' },
  { id: 'etsy', name: 'Etsy Only', color: 'pink' },  // Add new platform
] as const;
```

### Customize Stats Display

```tsx
// Add more stats to the panel
<div className="flex items-center gap-2">
  <div className="p-2 bg-indigo-500/10 rounded-lg">
    <YourIcon className="w-4 h-4 text-indigo-400" />
  </div>
  <div>
    <p className="text-xs text-gray-500">Your Metric</p>
    <p className="text-sm font-bold text-white">
      {activeStore.your_metric}
    </p>
  </div>
</div>
```

---

## 🐛 Troubleshooting

### Dropdown Not Closing
- Check if click outside handler is working
- Verify z-index values don't conflict

### Platform Filters Not Working
- Ensure platform names match exactly (case-insensitive)
- Check filteredStores useMemo logic

### Search Not Filtering
- Verify searchQuery state is updating
- Check toLowerCase() comparison

### Stats Not Showing
- Ensure activeStore is not null
- Verify Store interface matches data

---

## ✅ Testing Checklist

- [ ] Dropdown opens/closes correctly
- [ ] All Stores option switches to portfolio view
- [ ] Individual stores can be selected
- [ ] Search filters stores by name
- [ ] Platform filters work correctly
- [ ] Platform counts are accurate
- [ ] Add Store button triggers callback
- [ ] Stats panel shows when store selected
- [ ] Stats panel hides when "All Stores" selected
- [ ] Platform badges display correct colors
- [ ] Active indicators show for active stores
- [ ] Responsive on mobile
- [ ] Responsive on tablet
- [ ] Responsive on desktop
- [ ] Keyboard navigation works
- [ ] Click outside closes dropdown

---

## 📚 Related Components

### Works Well With
- **PortfolioDashboard** - Main dashboard page
- **StoreRankingsTable** - Table of stores
- **AddStoreModal** - Add new store dialog
- **StoreDetailsPage** - Individual store view

### Suggested Integration Flow
```
StoreSelector (header)
    ↓
User selects store
    ↓
onSwitch callback
    ↓
Update activeStore state
    ↓
Re-render dashboard with filtered data
```

---

## 🎯 Best Practices

1. **State Management**
   - Keep activeStore in parent component
   - Use callback pattern for state updates
   - Consider URL params for deep linking

2. **Performance**
   - Use useMemo for filtered stores
   - Debounce search input if many stores
   - Lazy load store stats

3. **Accessibility**
   - Add ARIA labels
   - Support keyboard navigation
   - Provide focus indicators

4. **User Experience**
   - Auto-focus search on dropdown open
   - Clear search on store selection
   - Show loading states when fetching

---

**Created:** November 14, 2025
**Status:** Production Ready
**Version:** 1.0.0
