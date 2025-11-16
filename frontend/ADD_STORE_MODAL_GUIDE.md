# Add Store Modal Component - Complete Guide

**Location:** `/frontend/src/components/AddStoreModal.tsx`

A comprehensive 3-step modal for adding new stores to the multi-store portfolio.

---

## 🎯 Features Overview

### Multi-Step Process
1. **Platform Selection** - Choose Shopify, Amazon, or WooCommerce
2. **Store Details** - Basic information (name, niche, market, currency)
3. **Credentials** - Platform-specific API credentials with connection testing

### Key Capabilities
- ✅ Platform-specific credential forms
- ✅ Connection testing before submission
- ✅ Real-time validation
- ✅ Inline error messages
- ✅ Progress indicator
- ✅ Responsive design
- ✅ Dark theme styling

---

## 📦 Props Interface

```typescript
interface AddStoreModalProps {
  onClose: () => void;           // Called when modal closes
  onSuccess: (store: any) => void;  // Called when store added successfully
}
```

---

## 🚀 Basic Usage

### Import and Use

```tsx
import { useState } from 'react';
import AddStoreModal from './components/AddStoreModal';

function Dashboard() {
  const [showAddModal, setShowAddModal] = useState(false);
  const [stores, setStores] = useState([]);

  const handleStoreAdded = (newStore) => {
    console.log('New store added:', newStore);
    setStores([...stores, newStore]);
    // Optionally refresh data or navigate
  };

  return (
    <>
      <button onClick={() => setShowAddModal(true)}>
        Add Store
      </button>

      {showAddModal && (
        <AddStoreModal
          onClose={() => setShowAddModal(false)}
          onSuccess={handleStoreAdded}
        />
      )}
    </>
  );
}
```

---

## 📋 Step-by-Step Breakdown

### Step 1: Platform Selection

**Purpose:** Choose the e-commerce platform

**Options:**
- 🛍️ **Shopify** - "Connect your Shopify store with Admin API credentials"
- 📦 **Amazon** - "Link your Amazon Seller Central account"
- 🔌 **WooCommerce** - "Connect your WordPress/WooCommerce site"

**Features:**
- Large clickable cards
- Platform icons and descriptions
- Visual selection indicator
- Required field validation

**Validation:**
- Platform must be selected before proceeding

---

### Step 2: Store Details

**Purpose:** Collect basic store information

**Fields:**

1. **Store Name** (Required)
   - Text input
   - Example: "My Awesome Store"
   - Icon: Store

2. **Store URL** (Optional)
   - URL input
   - Example: "https://mystore.com"
   - Icon: Globe

3. **Niche** (Required)
   - Dropdown select
   - Options:
     - Smart Home
     - Pet Products
     - Fitness & Sports
     - Fashion & Apparel
     - Kitchen & Dining
     - Beauty & Personal Care
     - Electronics
     - Home & Garden
     - Baby & Kids
     - Automotive

4. **Target Market** (Required)
   - Dropdown select
   - Options: US, CA, UK, EU, AU
   - Default: US

5. **Currency** (Required)
   - Dropdown select
   - Options: USD, CAD, GBP, EUR, AUD
   - Default: USD
   - Shows currency symbol

**Validation:**
- Store name cannot be empty
- Niche must be selected
- Market and currency have defaults

---

### Step 3: Platform-Specific Credentials

#### Shopify Credentials

**Fields:**

1. **Store Domain** (Required)
   ```
   Format: mystore.myshopify.com
   Example: oubon-shop.myshopify.com
   ```
   - Validates `.myshopify.com` format
   - Error: "Domain should be in format: store.myshopify.com"

2. **Admin API Token** (Required)
   ```
   Format: shpat_xxxxxxxxxxxxxxxxxx
   Type: Password field (hidden)
   ```
   - Link to setup guide provided
   - Password field for security

3. **API Version** (Optional)
   ```
   Default: 2024-01
   Format: YYYY-MM
   ```

**Help Link:**
- "How to get API token" → Shopify custom apps documentation

---

#### Amazon Credentials

**Fields:**

1. **Marketplace** (Required)
   - Dropdown: US, CA, UK, DE, FR
   - Default: US

2. **Seller ID** (Required)
   ```
   Format: A1XXXXXXXXX
   Example: A1ZJFEXAMPLE
   ```

3. **MWS Auth Token** (Required)
   ```
   Format: amzn.mws.xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
   Type: Password field
   ```

4. **Access Key ID** (Required)
   ```
   Format: AKIAIOSFODNN7EXAMPLE
   ```

5. **Secret Access Key** (Required)
   ```
   Format: wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
   Type: Password field
   ```

---

#### WooCommerce Credentials

**Fields:**

1. **Store URL** (Required)
   ```
   Format: https://mystore.com
   Must start with http:// or https://
   ```

2. **Consumer Key** (Required)
   ```
   Format: ck_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   ```

3. **Consumer Secret** (Required)
   ```
   Format: cs_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   Type: Password field
   ```

**Help Link:**
- "How to generate API keys" → WooCommerce REST API documentation

---

## 🔧 Connection Testing

### Test Connection Flow

1. User fills in credentials
2. Clicks "Test Connection" button
3. Button shows loading spinner: "Testing Connection..."
4. API call to: `POST /api/portfolio/stores/test-connection`
5. Response handling:
   - **Success** → Green banner: "✅ Connection successful!"
   - **Error** → Red banner: "❌ Connection failed: {error message}"

### States

```typescript
type TestStatus = 'idle' | 'testing' | 'success' | 'error';
```

- **idle** - Initial state, no test performed
- **testing** - Connection test in progress
- **success** - Connection successful, can submit
- **error** - Connection failed, cannot submit

### Submit Button

- **Disabled** until connection test succeeds
- Shows: "Add Store" when ready
- Shows: "Adding Store..." when submitting
- Only enabled when `testStatus === 'success'`

---

## 🎨 UI/UX Features

### Progress Indicator

**Visual Progress Bar:**
```
[████████] [████████] [········]  // Step 2 of 3
  Platform    Details   Credentials
```

- Blue bars for completed steps
- Gray bars for incomplete steps
- Text labels below

### Navigation

**Back Button:**
- Disabled on Step 1
- Returns to previous step
- Resets connection test status

**Next Button:**
- Validates current step
- Shows inline errors if validation fails
- Progresses to next step on success

**Submit Button:**
- Only shown on Step 3
- Gradient blue-to-purple
- Disabled until connection tested
- Shows loading spinner while submitting

### Validation & Errors

**Inline Validation:**
- Red border on invalid fields
- Error message below field
- Icon indicators (AlertCircle)

**Examples:**
```
Store Name [    ] ← Red border
❌ Store name is required

Shopify Domain [store]
❌ Domain should be in format: store.myshopify.com
```

### Loading States

**Test Connection:**
```
[🔄 Testing Connection...]
```

**Adding Store:**
```
[🔄 Adding Store...]
```

### Success/Error Banners

**Success:**
```
┌───────────────────────────────────┐
│ ✅ Connection successful!         │
└───────────────────────────────────┘
```

**Error:**
```
┌───────────────────────────────────┐
│ ❌ Connection failed: Invalid token│
└───────────────────────────────────┘
```

---

## 📡 API Integration

### Endpoints

#### 1. Test Connection
```
POST /api/portfolio/stores/test-connection

Body:
{
  "platform": "shopify",
  "shopify_domain": "mystore.myshopify.com",
  "shopify_api_token": "shpat_xxx",
  "shopify_api_version": "2024-01"
}

Response (Success):
{
  "success": true,
  "message": "Connection successful!"
}

Response (Error):
{
  "success": false,
  "error": "Invalid API credentials"
}
```

#### 2. Add Store
```
POST /api/portfolio/stores/add

Body:
{
  "platform": "shopify",
  "store_name": "My Store",
  "niche": "smart_home",
  "target_market": "US",
  "currency": "USD",
  "shopify_domain": "mystore.myshopify.com",
  "shopify_api_token": "shpat_xxx",
  "shopify_api_version": "2024-01"
}

Response (Success):
{
  "store": {
    "id": 2,
    "store_name": "My Store",
    "platform": "shopify",
    // ... other fields
  }
}

Response (Error):
{
  "error": "Store already exists"
}
```

---

## 🎨 Styling

### Modal
- **Background:** Dark overlay with backdrop blur
- **Card:** Gray-900 with gray-800 border
- **Max Width:** 2xl (672px)
- **Max Height:** 90vh
- **Positioning:** Centered, fixed overlay

### Colors
- **Primary:** Blue-500
- **Secondary:** Purple-600
- **Success:** Green-400
- **Error:** Red-400
- **Text:** White, Gray-400

### Animations
- **Transitions:** All interactive elements
- **Loading:** Spin animation on loader icons
- **Hover:** Scale and color changes

---

## 🔧 Advanced Usage

### With State Management

```tsx
import { create } from 'zustand';

const useStoreManager = create((set) => ({
  stores: [],
  addStore: (store) => set((state) => ({
    stores: [...state.stores, store]
  })),
}));

function Dashboard() {
  const { stores, addStore } = useStoreManager();
  const [showModal, setShowModal] = useState(false);

  return (
    <>
      <button onClick={() => setShowModal(true)}>Add Store</button>

      {showModal && (
        <AddStoreModal
          onClose={() => setShowModal(false)}
          onSuccess={(store) => {
            addStore(store);
            setShowModal(false);
          }}
        />
      )}
    </>
  );
}
```

### With Router Navigation

```tsx
import { useNavigate } from 'react-router-dom';

function Dashboard() {
  const navigate = useNavigate();

  return (
    <AddStoreModal
      onClose={() => navigate('/portfolio')}
      onSuccess={(store) => {
        navigate(`/store/${store.id}`);
      }}
    />
  );
}
```

### With Notifications

```tsx
import { toast } from 'react-toastify';

function Dashboard() {
  return (
    <AddStoreModal
      onClose={() => console.log('Modal closed')}
      onSuccess={(store) => {
        toast.success(`${store.store_name} added successfully!`);
      }}
    />
  );
}
```

---

## 🐛 Troubleshooting

### Modal Not Showing
- Check that state is true when rendering
- Verify z-index (modal uses z-50)
- Check for CSS conflicts

### Validation Not Working
- Ensure all required fields have values
- Check error state in browser console
- Verify validation logic

### Connection Test Failing
- Check API endpoint is accessible
- Verify credentials are correct
- Check network tab for error details
- Ensure backend is running

### Submit Not Working
- Ensure connection test passed
- Check `testStatus === 'success'`
- Verify API endpoint exists
- Check backend logs

---

## ✅ Features Checklist

**Step 1: Platform Selection**
- [x] Shopify option with icon and description
- [x] Amazon option with icon and description
- [x] WooCommerce option with icon and description
- [x] Visual selection indicator
- [x] Required field validation

**Step 2: Store Details**
- [x] Store name input (required)
- [x] Store URL input (optional)
- [x] Niche dropdown (required)
- [x] Target market dropdown
- [x] Currency dropdown
- [x] Field validation
- [x] Icon decorations

**Step 3: Credentials**
- [x] Shopify credential fields
- [x] Amazon credential fields
- [x] WooCommerce credential fields
- [x] Platform-specific validation
- [x] Help links to documentation
- [x] Password fields for secrets

**Connection Testing**
- [x] Test connection button
- [x] Loading state during test
- [x] Success banner (green)
- [x] Error banner (red)
- [x] Prevents submit until tested

**UI/UX**
- [x] Progress bar (1/3, 2/3, 3/3)
- [x] Step labels
- [x] Back button (disabled on step 1)
- [x] Next button (validates step)
- [x] Submit button (requires test success)
- [x] Close button
- [x] Dark overlay
- [x] Centered modal
- [x] Responsive design
- [x] Loading spinners
- [x] Error messages
- [x] Success messages

**Validation**
- [x] Required field indicators (*)
- [x] Inline error messages
- [x] URL format validation
- [x] Domain format validation
- [x] All fields validated before submit

---

## 🎯 Best Practices

1. **Always Test Connection**
   - User must test connection before submitting
   - Prevents invalid credentials being saved
   - Provides immediate feedback

2. **Clear Error Messages**
   - Show specific errors
   - Guide user to fix issues
   - Provide help links

3. **Progressive Disclosure**
   - Multi-step approach reduces overwhelm
   - Only show relevant fields
   - Clear progress indication

4. **Security**
   - Password fields for secrets
   - No credentials in console logs
   - Secure API transmission

---

**Created:** November 14, 2025
**Status:** Production Ready
**Version:** 1.0.0
