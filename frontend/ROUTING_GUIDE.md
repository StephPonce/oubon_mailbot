# Ospra Frontend Routing Guide

**Current Implementation:** State-based navigation
**Date:** November 14, 2025

---

## 🎯 Current Routing Structure

### Navigation State

```tsx
type PageType = 'portfolio' | 'products' | 'orders' | 'analytics';
const [currentPage, setCurrentPage] = useState<PageType>('portfolio');
```

### Available Routes

| Route | Component | Description | Icon | Default |
|-------|-----------|-------------|------|---------|
| `portfolio` | PortfolioDashboard | Multi-store overview | 🏪 | ✅ Yes |
| `products` | ProductsView | Product discovery | 📦 | No |
| `orders` | OrdersPage | Order management | 🛒 | No |
| `analytics` | AnalyticsPage | Analytics dashboard | 📊 | No |

---

## 🏠 Homepage (Portfolio Dashboard)

**Default Route:** `portfolio`
**Component:** `PortfolioDashboard.tsx`

### Features:
- Multi-store overview
- Revenue metrics
- Store rankings
- Performance charts
- Quick actions

### When to Show:
- Initial app load
- User clicks "Portfolio" button
- User navigates back from other pages

---

## 🔄 Navigation Flow

### User Journey:

```
App Start
    ↓
Portfolio Dashboard (Default)
    ↓
┌────────────────┬────────────────┬────────────────┐
│                │                │                │
│  📦 Products   │  🛒 Orders     │  📊 Analytics  │
│  Discovery     │  Management    │  Reporting     │
│                │                │                │
└────────────────┴────────────────┴────────────────┘
    ↑                ↑                ↑
    └────────────────┴────────────────┘
           Back to Portfolio
```

---

## 📱 Navigation Component

### Location:
Lines 127-174 in `/frontend/src/App.tsx`

### Implementation:

```tsx
<div className="flex gap-2">
  {/* Portfolio - DEFAULT */}
  <button
    onClick={() => setCurrentPage('portfolio')}
    className={`px-4 py-2 rounded-lg font-semibold transition ${
      currentPage === 'portfolio'
        ? 'bg-blue-600 text-white'
        : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
    }`}
  >
    🏪 Portfolio
  </button>

  {/* Products */}
  <button onClick={() => setCurrentPage('products')}>
    📦 Products
  </button>

  {/* Orders */}
  <button onClick={() => setCurrentPage('orders')}>
    🛒 Orders
  </button>

  {/* Analytics */}
  <button onClick={() => setCurrentPage('analytics')}>
    📊 Analytics
  </button>
</div>
```

---

## 🎨 Active State Styling

**Active (Current Page):**
```tsx
className="bg-blue-600 text-white"
```

**Inactive:**
```tsx
className="bg-gray-200 text-gray-700 hover:bg-gray-300"
```

---

## 🔮 Suggested Improvements

### 1. Individual Store View

**Add new route for single store:**

```tsx
type PageType = 'portfolio' | 'products' | 'orders' | 'analytics' | 'store';

const [currentPage, setCurrentPage] = useState<PageType>('portfolio');
const [selectedStoreId, setSelectedStoreId] = useState<number | null>(null);

// Navigate to individual store
const navigateToStore = (storeId: number) => {
  setSelectedStoreId(storeId);
  setCurrentPage('store');
};

// Render
{currentPage === 'store' && selectedStoreId && (
  <StoreDashboard storeId={selectedStoreId} />
)}
```

---

### 2. Add Breadcrumbs

**Show current location:**

```tsx
<nav className="mb-4 text-sm text-gray-600">
  <span>Home</span>
  {currentPage !== 'portfolio' && (
    <>
      <span className="mx-2">/</span>
      <span className="text-gray-900 font-medium">
        {currentPage.charAt(0).toUpperCase() + currentPage.slice(1)}
      </span>
    </>
  )}
  {currentPage === 'store' && selectedStoreId && (
    <>
      <span className="mx-2">/</span>
      <span className="text-gray-900 font-medium">Store #{selectedStoreId}</span>
    </>
  )}
</nav>
```

---

### 3. URL-Based Routing (Future)

**Upgrade to React Router:**

```tsx
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Default: Portfolio */}
        <Route path="/" element={<PortfolioDashboard />} />

        {/* Other Pages */}
        <Route path="/products" element={<ProductsView />} />
        <Route path="/orders" element={<OrdersPage />} />
        <Route path="/analytics" element={<AnalyticsPage />} />

        {/* Individual Store */}
        <Route path="/store/:storeId" element={<StoreDashboard />} />

        {/* Redirect unknown to home */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
```

**Benefits:**
- Browser back/forward works
- Bookmarkable URLs
- Deep linking support
- URL parameters for state

---

### 4. Context-Based Navigation

**Create NavigationContext:**

```tsx
// contexts/NavigationContext.tsx
import { createContext, useContext, useState } from 'react';

interface NavigationContextType {
  currentPage: PageType;
  navigateTo: (page: PageType) => void;
  selectedStoreId: number | null;
  navigateToStore: (storeId: number) => void;
}

const NavigationContext = createContext<NavigationContextType | null>(null);

export function NavigationProvider({ children }) {
  const [currentPage, setCurrentPage] = useState<PageType>('portfolio');
  const [selectedStoreId, setSelectedStoreId] = useState<number | null>(null);

  const navigateTo = (page: PageType) => {
    setCurrentPage(page);
    if (page !== 'store') {
      setSelectedStoreId(null);
    }
  };

  const navigateToStore = (storeId: number) => {
    setSelectedStoreId(storeId);
    setCurrentPage('store');
  };

  return (
    <NavigationContext.Provider value={{
      currentPage,
      navigateTo,
      selectedStoreId,
      navigateToStore
    }}>
      {children}
    </NavigationContext.Provider>
  );
}

export const useNavigation = () => useContext(NavigationContext)!;
```

**Usage:**

```tsx
// In any component
const { navigateTo, navigateToStore } = useNavigation();

<button onClick={() => navigateTo('products')}>
  Go to Products
</button>

<button onClick={() => navigateToStore(5)}>
  View Store #5
</button>
```

---

## 📝 Current Implementation Details

### File: `/frontend/src/App.tsx`

**Lines 1-8:** Imports
- Portfolio Dashboard imported (line 7)

**Lines 28-40:** State
- `currentPage` state with 'portfolio' as default (line 29)
- Product-related state (lines 30-40)

**Lines 124-175:** Navigation UI
- Top navigation bar
- 4 navigation buttons
- Portfolio set as active by default

**Lines 177-314:** Route Rendering
- Conditional rendering based on `currentPage`
- Portfolio Dashboard rendered first (line 177-178)
- Products, Orders, Analytics follow

---

## 🎯 Integration Points

### With StoreSelector

The StoreSelector component can work with the current routing:

```tsx
// In PortfolioDashboard.tsx
import { useCallback } from 'react';

const PortfolioDashboard = () => {
  const handleStoreSwitch = useCallback((store: Store | null) => {
    if (store) {
      // Option 1: Filter dashboard to single store
      setActiveStore(store);

      // Option 2: Navigate to dedicated store page (future)
      // navigateToStore(store.id);
    } else {
      // Show all stores (portfolio view)
      setActiveStore(null);
    }
  }, []);

  return (
    <div>
      <StoreSelector
        stores={stores}
        activeStore={activeStore}
        onSwitch={handleStoreSwitch}
        onAddStore={() => setShowAddModal(true)}
      />

      {/* Dashboard content filtered by activeStore */}
    </div>
  );
};
```

---

## 🚀 Quick Reference

### Change Default Page

```tsx
// Set Products as default instead
const [currentPage, setCurrentPage] = useState<PageType>('products');
```

### Add New Page

```tsx
// 1. Add to type
type PageType = 'portfolio' | 'products' | 'orders' | 'analytics' | 'newpage';

// 2. Add navigation button
<button onClick={() => setCurrentPage('newpage')}>
  🆕 New Page
</button>

// 3. Add conditional render
{currentPage === 'newpage' ? (
  <NewPageComponent />
) : ...
```

### Navigate Programmatically

```tsx
// From within App component
setCurrentPage('products');

// From child component (pass function as prop)
<ChildComponent onNavigate={(page) => setCurrentPage(page)} />
```

---

## ✅ Current Status

**Implementation:** ✅ Complete
**Default Route:** ✅ Portfolio Dashboard
**Navigation:** ✅ Working
**Responsive:** ✅ Yes
**Active States:** ✅ Styled

**Future Enhancements:**
- [ ] React Router integration
- [ ] Individual store pages
- [ ] Breadcrumb navigation
- [ ] URL state management
- [ ] Navigation context

---

## 📚 Related Files

- `/frontend/src/App.tsx` - Main routing logic
- `/frontend/src/pages/PortfolioDashboard.tsx` - Default homepage
- `/frontend/src/pages/OrdersPage.tsx` - Orders page
- `/frontend/src/pages/AnalyticsPage.tsx` - Analytics page
- `/frontend/src/components/ProductCard.tsx` - Products page components

---

**Last Updated:** November 14, 2025
**Routing Type:** State-based (client-side)
**Default Route:** Portfolio Dashboard
