# Platform Badges & Brand Logos - Frontend Implementation Guide

## 📦 Badge Structure

Each product now includes `platform_badges` array with logo information:

```json
{
  "platform": "tiktok",
  "label": "Hot on TikTok",
  "level": "hot",
  "emoji": "🔥",
  "color": "#FF0050",
  "logo": {
    "cdn": "https://cdn.simpleicons.org/tiktok/FF0050",
    "local": "/assets/logos/tiktok.svg",
    "icon_library": "FaTiktok",
    "brand_color": "#000000"
  },
  "metric": "8,250 sales",
  "sources": ["tiktok_shop", "amazon_bestsellers"]  // Only for multi-source badges
}
```

---

## 🎨 Option 1: Use CDN URLs (Easiest - No Setup Required)

### Simple Icons CDN
Brand logos from [simpleicons.org](https://simpleicons.org) - **Free, instant, customizable color**

```jsx
// React/Next.js Component
function PlatformBadge({ badge }) {
  return (
    <div
      className="badge"
      style={{
        backgroundColor: badge.color,
        padding: '4px 12px',
        borderRadius: '6px',
        display: 'inline-flex',
        alignItems: 'center',
        gap: '6px'
      }}
    >
      {/* Use CDN logo */}
      <img
        src={badge.logo.cdn}
        alt={badge.platform}
        width={16}
        height={16}
        style={{ filter: 'brightness(0) invert(1)' }} // Make white
      />
      <span style={{ color: 'white', fontSize: '12px', fontWeight: '600' }}>
        {badge.label}
      </span>
      <span style={{ color: 'white', fontSize: '10px', opacity: 0.9 }}>
        {badge.metric}
      </span>
    </div>
  );
}

// Usage
{product.platform_badges.map((badge, idx) => (
  <PlatformBadge key={idx} badge={badge} />
))}
```

### Available CDN URLs:
- TikTok: `https://cdn.simpleicons.org/tiktok/{COLOR}`
- Amazon: `https://cdn.simpleicons.org/amazon/{COLOR}`
- Shopify: `https://cdn.simpleicons.org/shopify/{COLOR}`
- Google: `https://cdn.simpleicons.org/google/{COLOR}`
- Instagram: `https://cdn.simpleicons.org/instagram/{COLOR}`

Replace `{COLOR}` with hex code (no #): `FF0050`, `4285F4`, etc.

---

## 🎨 Option 2: Use Icon Libraries (Most Flexible)

### React Icons (Recommended)
```bash
npm install react-icons
# or
yarn add react-icons
```

```jsx
import {
  FaTiktok,
  FaAmazon,
  FaShopify,
  FaGoogle,
  FaCheckDouble,
  FaCheck
} from 'react-icons/fa';

const iconMap = {
  FaTiktok: FaTiktok,
  FaAmazon: FaAmazon,
  FaShopify: FaShopify,
  FaGoogle: FaGoogle,
  FaCheckDouble: FaCheckDouble,
  FaCheck: FaCheck,
};

function PlatformBadge({ badge }) {
  const IconComponent = iconMap[badge.logo.icon_library];

  return (
    <div
      className="badge"
      style={{
        backgroundColor: badge.color,
        padding: '6px 12px',
        borderRadius: '8px',
        display: 'inline-flex',
        alignItems: 'center',
        gap: '8px',
        boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
      }}
    >
      {IconComponent && (
        <IconComponent
          size={18}
          color="white"
        />
      )}
      <span style={{ color: 'white', fontSize: '13px', fontWeight: '600' }}>
        {badge.label}
      </span>
      <span style={{
        color: 'white',
        fontSize: '11px',
        opacity: 0.9,
        background: 'rgba(255,255,255,0.2)',
        padding: '2px 6px',
        borderRadius: '4px'
      }}>
        {badge.metric}
      </span>
    </div>
  );
}
```

---

## 🎨 Option 3: Use Local SVG Assets (Best for Production)

### 1. Download Brand Logos

Download official brand logos:
- **TikTok**: https://www.tiktok.com/about/brand-guidelines
- **Amazon**: https://developer.amazon.com/support/legal/tuabg
- **Shopify**: https://www.shopify.com/brand-assets
- **Google**: https://about.google/brand-resource-center/

Or use Simple Icons:
```bash
npm install simple-icons
```

### 2. Save to `/public/assets/logos/`

```
public/
└── assets/
    └── logos/
        ├── tiktok.svg
        ├── amazon.svg
        ├── shopify.svg
        ├── google.svg
        └── multi-source.svg
```

### 3. Use in Component

```jsx
function PlatformBadge({ badge }) {
  return (
    <div className="badge" style={{ backgroundColor: badge.color }}>
      <img
        src={badge.logo.local}  // Uses /assets/logos/tiktok.svg
        alt={badge.platform}
        width={18}
        height={18}
      />
      <span>{badge.label}</span>
      <span className="metric">{badge.metric}</span>
    </div>
  );
}
```

---

## 🎯 Complete Product Card Example

```jsx
import { FaTiktok, FaAmazon, FaShopify, FaGoogle } from 'react-icons/fa';

function ProductCard({ product }) {
  const iconMap = {
    FaTiktok, FaAmazon, FaShopify, FaGoogle
  };

  return (
    <div className="product-card">
      {/* Product Image */}
      <img src={product.image_url} alt={product.name} />

      {/* Multi-Source Badge (Priority) */}
      {product.source_count > 1 && (
        <div className="multi-source-badge">
          🎯 Found in {product.source_count} sources!
        </div>
      )}

      {/* Product Name & Score */}
      <h3>{product.name}</h3>
      <div className="score-bar">
        <div
          className="score-fill"
          style={{
            width: `${product.final_score}%`,
            backgroundColor: getScoreColor(product.final_score)
          }}
        />
        <span>{product.final_score.toFixed(1)}%</span>
      </div>

      {/* Platform Badges */}
      <div className="badges-container">
        {product.platform_badges.map((badge, idx) => {
          const Icon = iconMap[badge.logo.icon_library];

          return (
            <div
              key={idx}
              className="badge"
              style={{ backgroundColor: badge.color }}
              title={badge.metric}  // Tooltip
            >
              {/* Use CDN or Icon Library */}
              {Icon ? (
                <Icon size={16} color="white" />
              ) : (
                <img src={badge.logo.cdn} width={16} height={16} />
              )}
              <span>{badge.label}</span>
              <small>{badge.metric}</small>
            </div>
          );
        })}
      </div>

      {/* Platform Scores Breakdown */}
      <div className="platform-scores">
        <h4>Platform Breakdown</h4>
        {Object.entries(product.platform_scores).map(([platform, score]) => (
          <div key={platform} className="score-row">
            <span>{formatPlatformName(platform)}</span>
            <div className="score-bar-mini">
              <div style={{ width: `${score}%` }} />
            </div>
            <span>{score}%</span>
          </div>
        ))}
      </div>

      {/* Action Buttons */}
      <div className="actions">
        <button className="btn-primary">
          {product.recommendation}
        </button>
        {product.aliexpress_url && (
          <a href={product.aliexpress_url} target="_blank">
            View on AliExpress
          </a>
        )}
      </div>
    </div>
  );
}

function getScoreColor(score) {
  if (score >= 85) return '#10B981'; // Green
  if (score >= 70) return '#F59E0B'; // Orange
  return '#EF4444'; // Red
}

function formatPlatformName(platform) {
  return platform
    .replace(/_/g, ' ')
    .replace(/score/g, '')
    .trim()
    .split(' ')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}
```

---

## 🎨 CSS Styling

```css
.badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 600;
  color: white;
  white-space: nowrap;
  transition: transform 0.2s;
}

.badge:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.badge img, .badge svg {
  filter: brightness(0) invert(1); /* Make white */
}

.badges-container {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 12px 0;
}

.multi-source-badge {
  position: absolute;
  top: 12px;
  right: 12px;
  background: linear-gradient(135deg, #FFD700 0%, #FFA500 100%);
  color: white;
  padding: 8px 16px;
  border-radius: 12px;
  font-weight: 700;
  font-size: 13px;
  box-shadow: 0 4px 12px rgba(255, 215, 0, 0.4);
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.05); }
}

.platform-scores {
  margin-top: 16px;
  padding: 12px;
  background: #F9FAFB;
  border-radius: 8px;
}

.score-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 8px 0;
}

.score-bar-mini {
  flex: 1;
  height: 6px;
  background: #E5E7EB;
  border-radius: 3px;
  overflow: hidden;
}

.score-bar-mini > div {
  height: 100%;
  background: linear-gradient(90deg, #3B82F6 0%, #8B5CF6 100%);
  transition: width 0.3s;
}
```

---

## 🔥 Advanced: Animated Badge Component

```jsx
import { motion } from 'framer-motion';

function AnimatedBadge({ badge, index }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.1 }}
      className="badge"
      style={{ backgroundColor: badge.color }}
      whileHover={{ scale: 1.05 }}
      whileTap={{ scale: 0.95 }}
    >
      <img
        src={badge.logo.cdn}
        width={18}
        height={18}
        alt={badge.platform}
      />
      <span>{badge.label}</span>
      {badge.metric && (
        <motion.span
          initial={{ width: 0 }}
          animate={{ width: 'auto' }}
          className="metric"
        >
          {badge.metric}
        </motion.span>
      )}
    </motion.div>
  );
}
```

---

## 🎯 Badge Priority Display Order

Badges are returned in priority order:

1. **Multi-Source Badge** (if 2+ sources) - ALWAYS FIRST
2. **TikTok Badge** (if sales data exists)
3. **Amazon Badge** (if bestseller)
4. **Shopify Badge** (if in competitor stores)
5. **Google Badge** (if trending/rising)

This ensures the most important information is always visible first!

---

## 📱 Mobile Responsive

```css
@media (max-width: 640px) {
  .badge {
    font-size: 10px;
    padding: 4px 8px;
    gap: 4px;
  }

  .badge img, .badge svg {
    width: 14px;
    height: 14px;
  }

  .badge .metric {
    display: none; /* Hide metrics on mobile */
  }
}
```

---

## 🎨 Dark Mode Support

```jsx
function PlatformBadge({ badge, darkMode }) {
  return (
    <div
      className="badge"
      style={{
        backgroundColor: darkMode ? `${badge.color}20` : badge.color,
        border: darkMode ? `1px solid ${badge.color}` : 'none',
        color: darkMode ? badge.color : 'white'
      }}
    >
      <img
        src={badge.logo.cdn}
        style={{
          filter: darkMode ? 'none' : 'brightness(0) invert(1)'
        }}
      />
      {badge.label}
    </div>
  );
}
```

---

## ✅ Summary

You now have **3 options** for displaying brand logos:

1. **CDN** - Zero setup, instant logos (simpleicons.org)
2. **Icon Libraries** - Flexible, customizable (react-icons)
3. **Local Assets** - Best performance, full control

Choose based on your needs:
- **Quick prototype?** → Use CDN
- **React app?** → Use Icon Libraries
- **Production app?** → Use Local Assets

All logo URLs/references are included in the API response! 🎯
