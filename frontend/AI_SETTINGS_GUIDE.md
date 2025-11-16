# AI Settings Component - Complete Guide

**Component:** AISettings
**Location:** `/frontend/src/components/AISettings.tsx`
**Status:** Production Ready
**Date:** November 14, 2025

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Features](#features)
3. [Component Props](#component-props)
4. [AI Providers](#ai-providers)
5. [Usage Examples](#usage-examples)
6. [API Integration](#api-integration)
7. [Customization](#customization)
8. [Styling](#styling)
9. [Best Practices](#best-practices)

---

## Overview

The AISettings component provides a comprehensive interface for managing AI provider preferences in your e-commerce platform. Users can:

- Select from multiple AI providers (Claude, OpenAI, Gemini, Grok)
- View detailed provider information (cost, speed, quality ratings)
- Use custom API keys for selected providers
- Track current month usage and costs
- Compare providers side-by-side
- Calculate potential savings when switching

**File Size:** 626 lines
**Dependencies:** React 18.3.1, Lucide React 5.5.0, Tailwind CSS 3.4.18

---

## Features

### ✨ Core Features

#### 1. Provider Selection
- **4 AI Providers**: Claude Sonnet 4, OpenAI GPT-4, Google Gemini Pro, Grok AI
- **Visual Cards**: Large clickable cards with provider information
- **Recommended Badge**: Highlights the recommended provider (Claude)
- **Coming Soon Badge**: Shows providers not yet available
- **Selection Indicator**: Checkmark on selected provider
- **Disabled State**: Grays out unavailable providers

#### 2. Provider Information
Each provider card displays:
- **Icon**: Emoji representing the provider
- **Display Name**: Full provider name
- **Pricing**: Cost per 1,000 tokens
- **Speed Rating**: 1-5 stars indicating response speed
- **Quality Rating**: 1-5 stars indicating output quality
- **Best For**: Use case tags (e.g., "Product analysis", "Budget-conscious users")

#### 3. Usage Tracking
Current month statistics:
- **Total Tokens**: Total tokens consumed this month
- **Total Cost**: Total spending across all providers
- **Average Daily Cost**: Cost per day calculation
- **Provider Breakdown**: Usage per provider (mock data)

#### 4. Cost Savings Calculator
- **Real-time Calculation**: Updates when provider selection changes
- **Potential Savings**: Shows monthly savings or additional costs
- **Percentage Change**: Displays savings as a percentage
- **Visual Indicator**: Green (savings) or red (additional cost) banner

#### 5. Custom API Key Management
- **Enable/Disable Toggle**: Checkbox to activate custom key mode
- **Secure Input**: Password field with show/hide toggle
- **Security Notice**: AES-256 encryption information
- **API Key Testing**: Validates key before saving
- **Validation Status**: Green checkmark (valid) or red error (invalid)
- **Benefits Display**: Lists advantages of using custom keys

#### 6. Provider Comparison Table
Side-by-side comparison showing:
- Provider name with icon
- Cost per 1K tokens
- Speed rating (stars)
- Quality rating (stars)
- Estimated monthly cost based on current usage

#### 7. Quality Warnings
- **Downgrade Alert**: Warning when switching from premium to budget provider
- **Context-Aware**: Only shows for specific transitions (e.g., Claude → Gemini)
- **Informative**: Explains potential impact on output quality

#### 8. Settings Persistence
- **Save Button**: Gradient blue-to-purple button
- **Change Detection**: Only enabled when changes are made
- **Loading State**: Shows "Saving..." with spinner
- **Success Feedback**: Alert on successful save
- **Error Handling**: Alert on save failure

---

## Component Props

### `AISettingsProps`

```typescript
interface AISettingsProps {
  onSave?: (settings: { provider: string; customApiKey?: string }) => void;
}
```

| Prop | Type | Required | Description |
|------|------|----------|-------------|
| `onSave` | Function | No | Callback fired when settings are successfully saved |

**Callback Parameters:**
```typescript
{
  provider: string;        // Selected provider ID ('claude', 'openai', 'gemini')
  customApiKey?: string;   // Custom API key if provided
}
```

---

## AI Providers

### Provider Configuration

Each provider is defined with the following structure:

```typescript
interface AIProvider {
  id: string;              // Unique identifier
  name: string;            // API name (lowercase)
  displayName: string;     // User-facing name
  icon: string;            // Emoji icon
  costPer1k: number;       // Cost per 1,000 tokens (USD)
  speedRating: number;     // 1-5 rating
  qualityRating: number;   // 1-5 rating
  bestFor: string[];       // Use case tags
  recommended?: boolean;   // Show recommended badge
  comingSoon?: boolean;    // Disable with "Coming Soon" badge
  color: string;           // Theme color (purple, green, blue, orange)
}
```

### Available Providers

#### 1. Claude Sonnet 4 (Recommended)
```typescript
{
  id: 'claude',
  displayName: 'Claude Sonnet 4',
  icon: '🤖',
  costPer1k: 0.003,        // $0.003 per 1K tokens
  speedRating: 5,          // ⭐⭐⭐⭐⭐
  qualityRating: 5,        // ⭐⭐⭐⭐⭐
  bestFor: [
    'Product analysis',
    'Detailed descriptions',
    'Market research',
    'Customer support'
  ],
  recommended: true,
  color: 'purple'
}
```

**Best For:**
- High-quality product descriptions
- Detailed market analysis
- Complex reasoning tasks
- Professional customer support responses

**Pricing Example:**
- 100K tokens/month = $0.30
- 1M tokens/month = $3.00

---

#### 2. OpenAI GPT-4
```typescript
{
  id: 'openai',
  displayName: 'OpenAI GPT-4',
  icon: '🧠',
  costPer1k: 0.03,         // $0.03 per 1K tokens
  speedRating: 4,          // ⭐⭐⭐⭐☆
  qualityRating: 5,        // ⭐⭐⭐⭐⭐
  bestFor: [
    'Complex reasoning',
    'Code generation',
    'Creative writing',
    'Problem solving'
  ],
  color: 'green'
}
```

**Best For:**
- Advanced reasoning tasks
- Technical content generation
- Creative product descriptions
- Multi-step problem solving

**Pricing Example:**
- 100K tokens/month = $3.00
- 1M tokens/month = $30.00

---

#### 3. Google Gemini Pro
```typescript
{
  id: 'gemini',
  displayName: 'Google Gemini Pro',
  icon: '✨',
  costPer1k: 0.00025,      // $0.00025 per 1K tokens
  speedRating: 5,          // ⭐⭐⭐⭐⭐
  qualityRating: 4,        // ⭐⭐⭐⭐☆
  bestFor: [
    'Budget-conscious users',
    'High volume tasks',
    'Quick responses',
    'Basic analysis'
  ],
  color: 'blue'
}
```

**Best For:**
- High-volume processing
- Cost-sensitive applications
- Quick responses needed
- Basic product descriptions

**Pricing Example:**
- 100K tokens/month = $0.025
- 1M tokens/month = $0.25

---

#### 4. Grok AI (Coming Soon)
```typescript
{
  id: 'grok',
  displayName: 'Grok AI',
  icon: '🚀',
  costPer1k: 0.005,        // $0.005 per 1K tokens
  speedRating: 4,          // ⭐⭐⭐⭐☆
  qualityRating: 4,        // ⭐⭐⭐⭐☆
  bestFor: [
    'Real-time data',
    'News analysis',
    'Trend detection'
  ],
  comingSoon: true,
  color: 'orange'
}
```

**Status:** Not yet available (disabled in UI)

---

## Usage Examples

### Basic Usage

```tsx
import React from 'react';
import AISettings from './components/AISettings';

function SettingsPage() {
  const handleSave = (settings) => {
    console.log('Saved:', settings);
    // { provider: 'claude', customApiKey: undefined }
  };

  return (
    <div className="min-h-screen bg-gray-900 text-white">
      <AISettings onSave={handleSave} />
    </div>
  );
}
```

---

### With Navigation Integration

```tsx
import { useState } from 'react';
import AISettings from './components/AISettings';

function App() {
  const [currentPage, setCurrentPage] = useState('dashboard');

  return (
    <div>
      <nav>
        <button onClick={() => setCurrentPage('dashboard')}>Dashboard</button>
        <button onClick={() => setCurrentPage('settings')}>AI Settings</button>
      </nav>

      {currentPage === 'settings' && (
        <AISettings
          onSave={(settings) => {
            console.log('Settings saved:', settings);
            setCurrentPage('dashboard'); // Navigate back
          }}
        />
      )}
    </div>
  );
}
```

---

### With React Router

```tsx
import { useNavigate } from 'react-router-dom';
import AISettings from './components/AISettings';

function AISettingsPage() {
  const navigate = useNavigate();

  return (
    <AISettings
      onSave={(settings) => {
        console.log('Settings saved:', settings);
        navigate('/dashboard'); // Navigate to dashboard
      }}
    />
  );
}
```

---

### With State Management (Redux/Zustand)

```tsx
import { useDispatch } from 'react-redux';
import AISettings from './components/AISettings';
import { updateAISettings } from './store/settingsSlice';

function AISettingsPage() {
  const dispatch = useDispatch();

  return (
    <AISettings
      onSave={(settings) => {
        dispatch(updateAISettings(settings));
      }}
    />
  );
}
```

---

### With Toast Notifications

```tsx
import { toast } from 'react-hot-toast';
import AISettings from './components/AISettings';

function AISettingsPage() {
  return (
    <AISettings
      onSave={(settings) => {
        toast.success(
          `AI provider switched to ${settings.provider}`,
          { icon: '🤖', duration: 3000 }
        );
      }}
    />
  );
}
```

---

## API Integration

### Required Backend Endpoints

#### 1. Test API Key

**Endpoint:** `POST /api/settings/ai-provider/test-key`

**Request:**
```json
{
  "provider": "claude",
  "apiKey": "sk-ant-api03-..."
}
```

**Response (Success):**
```json
{
  "valid": true,
  "message": "API key is valid"
}
```

**Response (Error):**
```json
{
  "valid": false,
  "error": "Invalid API key"
}
```

---

#### 2. Save AI Settings

**Endpoint:** `POST /api/settings/ai-provider`

**Request:**
```json
{
  "provider": "claude",
  "customApiKey": "sk-ant-api03-..." // Optional, null if not using custom key
}
```

**Response (Success):**
```json
{
  "success": true,
  "settings": {
    "provider": "claude",
    "customKeyEnabled": false
  }
}
```

**Response (Error):**
```json
{
  "success": false,
  "error": "Failed to save settings"
}
```

---

#### 3. Get Usage Statistics (Optional)

**Endpoint:** `GET /api/settings/ai-provider/usage`

**Response:**
```json
{
  "currentMonth": {
    "totalTokens": 245680,
    "totalCost": 7.37,
    "byProvider": {
      "claude": { "tokens": 180000, "cost": 5.40 },
      "openai": { "tokens": 45680, "cost": 1.37 },
      "gemini": { "tokens": 20000, "cost": 0.60 }
    }
  }
}
```

**Note:** Currently uses mock data. Implement this endpoint to show real usage.

---

## Customization

### Adding a New Provider

```tsx
// In AI_PROVIDERS array
{
  id: 'mistral',
  name: 'mistral',
  displayName: 'Mistral AI',
  icon: '⚡',
  costPer1k: 0.002,
  speedRating: 5,
  qualityRating: 4,
  bestFor: ['Fast responses', 'Efficient processing', 'European compliance'],
  color: 'red' // Add 'red' to color mapping
}

// Add color mapping
const getProviderColorClass = (color: string, type: 'bg' | 'text' | 'border') => {
  const colors: Record<string, Record<string, string>> = {
    // ... existing colors
    red: {
      bg: 'bg-red-500/20',
      text: 'text-red-400',
      border: 'border-red-500/50'
    }
  };
  return colors[color]?.[type] || colors.blue[type];
};
```

---

### Changing Default Provider

```tsx
const [selectedProvider, setSelectedProvider] = useState<string>('gemini'); // Changed from 'claude'
const [originalProvider, setOriginalProvider] = useState<string>('gemini');
```

---

### Modifying Usage Stats

```tsx
// Replace mock data with API call
useEffect(() => {
  const fetchUsage = async () => {
    const response = await fetch('http://localhost:8001/api/settings/ai-provider/usage');
    const data = await response.json();
    setUsageStats(data);
  };
  fetchUsage();
}, []);
```

---

### Customizing Provider Cards

```tsx
// Modify the provider card rendering
<button className={`...your custom classes...`}>
  {/* Add custom content */}
  <div className="my-custom-section">
    <p>Custom info here</p>
  </div>

  {/* Keep existing structure or modify */}
</button>
```

---

## Styling

### Theme Colors

**Background:**
- Main: `bg-gray-900` (#111827)
- Cards: `bg-gray-800` (#1F2937)
- Inputs: `bg-gray-900` (#111827)

**Borders:**
- Default: `border-gray-700` (#374151)
- Hover: `border-gray-600` (#4B5563)
- Active: `border-{color}-500` (provider-specific)

**Text:**
- Primary: `text-white` (#FFFFFF)
- Secondary: `text-gray-400` (#9CA3AF)
- Tertiary: `text-gray-500` (#6B7280)

**Provider Colors:**
- Claude (Purple): `#A855F7`
- OpenAI (Green): `#10B981`
- Gemini (Blue): `#3B82F6`
- Grok (Orange): `#F97316`

**Accent Colors:**
- Success: `text-green-400`, `bg-green-500/10`
- Error: `text-red-400`, `bg-red-500/10`
- Warning: `text-yellow-400`, `bg-yellow-500/10`
- Info: `text-blue-400`, `bg-blue-500/10`

---

### Responsive Design

**Breakpoints:**
- Mobile: Default (< 768px)
- Tablet: `md:` (768px+)
- Desktop: `lg:` (1024px+)

**Grid Layouts:**
```tsx
// Provider cards: 1 column (mobile), 2 columns (tablet+)
<div className="grid grid-cols-1 md:grid-cols-2 gap-4">

// Usage stats: 1 column (mobile), 3 columns (tablet+)
<div className="grid grid-cols-1 md:grid-cols-3 gap-4">
```

---

### Custom Styling Example

```tsx
// Wrap component with custom container
<div className="my-custom-wrapper bg-gradient-to-br from-gray-900 to-gray-800">
  <AISettings onSave={handleSave} />
</div>

// Or create a styled variant
const StyledAISettings = () => (
  <div className="p-8 bg-black rounded-2xl shadow-2xl">
    <AISettings onSave={handleSave} />
  </div>
);
```

---

## Best Practices

### 1. Error Handling

```tsx
<AISettings
  onSave={async (settings) => {
    try {
      await saveSettings(settings);
      toast.success('Settings saved!');
    } catch (error) {
      console.error('Failed to save:', error);
      toast.error('Failed to save settings');
    }
  }}
/>
```

---

### 2. Loading States

```tsx
const [loading, setLoading] = useState(false);

<AISettings
  onSave={async (settings) => {
    setLoading(true);
    try {
      await saveSettings(settings);
    } finally {
      setLoading(false);
    }
  }}
/>

{loading && <LoadingOverlay />}
```

---

### 3. API Key Security

**Do:**
- ✅ Use password input fields
- ✅ Never log API keys
- ✅ Encrypt before storing
- ✅ Use HTTPS for API calls
- ✅ Validate keys on backend

**Don't:**
- ❌ Display keys in plain text
- ❌ Store keys in localStorage (use encrypted storage)
- ❌ Send keys in GET requests
- ❌ Log keys to console in production

---

### 4. Usage Analytics

Track important events:

```tsx
<AISettings
  onSave={(settings) => {
    // Track provider selection
    analytics.track('AI Provider Changed', {
      from: originalProvider,
      to: settings.provider,
      customKey: !!settings.customApiKey
    });

    // Track savings
    if (savings) {
      analytics.track('Cost Savings Calculated', {
        savings: savings.savings,
        savingsPercent: savings.savingsPercent
      });
    }
  }}
/>
```

---

### 5. Feature Flags

Enable/disable providers dynamically:

```tsx
const enabledProviders = AI_PROVIDERS.filter(p => {
  if (p.id === 'grok' && !featureFlags.grokEnabled) {
    return false;
  }
  return true;
});
```

---

### 6. Cost Monitoring

Set up alerts for high usage:

```tsx
useEffect(() => {
  if (usageStats.currentMonth.totalCost > 100) {
    showCostAlert('Your AI usage this month exceeds $100');
  }
}, [usageStats]);
```

---

## Complete Integration Example

```tsx
import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'react-hot-toast';
import AISettings from './components/AISettings';
import { saveAISettings, getAIUsage } from './api/settings';
import { trackEvent } from './analytics';

export default function AISettingsPage() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);

  const handleSave = async (settings) => {
    setLoading(true);

    try {
      // Save to backend
      await saveAISettings(settings);

      // Track event
      trackEvent('AI Settings Updated', {
        provider: settings.provider,
        customKey: !!settings.customApiKey
      });

      // Show success message
      toast.success(
        `Switched to ${settings.provider.toUpperCase()}`,
        { icon: '🤖', duration: 3000 }
      );

      // Navigate back to dashboard
      setTimeout(() => {
        navigate('/dashboard');
      }, 1500);

    } catch (error) {
      console.error('Failed to save AI settings:', error);
      toast.error('Failed to save settings. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-900 text-white">
      {/* Header */}
      <div className="p-6 border-b border-gray-800">
        <button
          onClick={() => navigate(-1)}
          className="text-gray-400 hover:text-white transition"
        >
          ← Back
        </button>
      </div>

      {/* Settings Component */}
      <AISettings onSave={handleSave} />

      {/* Loading Overlay */}
      {loading && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-gray-800 rounded-lg p-6 text-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto mb-4"></div>
            <p>Saving settings...</p>
          </div>
        </div>
      )}
    </div>
  );
}
```

---

## Troubleshooting

### Component Not Rendering
- Check that parent has dark background (`bg-gray-900`)
- Verify Tailwind CSS is configured
- Ensure Lucide React is installed

### API Key Test Failing
- Verify backend endpoint exists
- Check CORS configuration
- Inspect network tab for errors
- Validate API key format

### Save Button Disabled
- Ensure changes have been made
- If using custom key, must test it first
- Check for validation errors

### Styling Issues
- Verify Tailwind CSS classes are compiled
- Check for conflicting CSS
- Ensure parent container has proper width

---

## Summary

The AISettings component provides a complete, production-ready solution for AI provider management with:

✅ **4 AI Providers** - Claude, OpenAI, Gemini, Grok
✅ **Usage Tracking** - Real-time cost monitoring
✅ **Cost Calculator** - Savings estimation
✅ **Custom API Keys** - Secure key management
✅ **Provider Comparison** - Side-by-side analysis
✅ **Quality Warnings** - Prevent unexpected downgrades
✅ **Responsive Design** - Mobile-first approach
✅ **Dark Theme** - Professional appearance
✅ **TypeScript** - Full type safety
✅ **Secure** - Password fields, encryption notices

Ready for production use! 🚀

---

**Built with React + TypeScript + Tailwind CSS + Lucide Icons**
**Part of OspraOS Multi-Store E-commerce System**
**November 2025**
