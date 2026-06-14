/**
 * OSPRA INTELLIGENCE - PRODUCT DISCOVERY
 * ======================================
 * v5 - Jan 2025: FIXED - Real scores, image toggle, auto-analysis
 * 
 * FIXES:
 * - Image toggle between AI generated and original supplier images
 * - Auto-generate AI analysis when opening product detail
 * - Fixed regenerate image button
 * - Shows "estimated" label when scores are defaults
 * - All images array shown in detail view
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Search, Package, TrendingUp, Rocket, BarChart3, Tag, Loader2, Filter,
  ArrowRight, Eye, AlertTriangle, AlertCircle, RefreshCw, X, ExternalLink, Brain,
  ShoppingCart, Copy, Check, ChevronRight, Star, Link2, Database,
  Zap, Target, Sparkles, DollarSign, Camera, Wand2, MessageSquare,
  ImageIcon, ToggleLeft, ToggleRight, Info, ChevronLeft
} from 'lucide-react';
import { useAuth } from '../hooks/useAuth';
import { useDashboardContext } from '../hooks/useDashboardContext';
import { useToast } from '../hooks/useToast';
import { api, API_BASE_URL } from '../services/api';
import { capture, EVENTS } from '../services/analytics';
import { PageLayout } from './Layout';
import { AIImageComparison } from './AIImageComparison';

// ============================================================================
// HELPER: Resolve image URLs to full URLs
// ============================================================================
// Enhanced images are served from backend at /static/images/enhanced/
// We need to prepend API_BASE_URL for these relative paths
function resolveImageUrl(url) {
  if (!url) return null;
  // If it's already a full URL (http/https) or data URL, return as-is
  if (url.startsWith('http://') || url.startsWith('https://') || url.startsWith('data:')) {
    return url;
  }
  // If it's a relative path from our backend (starts with /), prepend API_BASE_URL
  if (url.startsWith('/')) {
    return `${API_BASE_URL}${url}`;
  }
  return url;
}

// ============================================================================
// HELPER: Normalize product data from any API source
// ============================================================================
// Generate a stable hash from a string (for consistent product IDs)
function simpleHash(str) {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    const char = str.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash = hash & hash; // Convert to 32bit integer
  }
  return Math.abs(hash).toString(36);
}

function normalizeProduct(p, fallbackNiche = 'general') {
  const costPrice = parseFloat(p.cost_price || p.supplier_cost || p.targetSalePrice || p.price || 0);
  
  let suggestedPrice = parseFloat(p.suggested_price || 0);
  if (!suggestedPrice && costPrice > 0) {
    suggestedPrice = costPrice * 2.5;
  }
  
  let profit = parseFloat(p.profit || 0);
  if (!profit && suggestedPrice > 0 && costPrice > 0) {
    profit = suggestedPrice - costPrice;
  }
  
  // Collect ALL image URLs from backend
  const mainImage = p.image_url || p.imageUrl || p.image || p.main_image || p.productMainImageUrl || null;
  
  // PRIORITY: Use backend's all_images if available (from product_discovery.py V3)
  let allImages = [];
  if (p.all_images && Array.isArray(p.all_images) && p.all_images.length > 0) {
    allImages = [...p.all_images];
  } else {
    // Fallback: build from various fields
    if (mainImage) allImages.push(mainImage);
    
    // Add additional images if available
    if (p.images && Array.isArray(p.images)) {
      p.images.forEach(img => {
        const url = typeof img === 'string' ? img : img.url;
        if (url && !allImages.includes(url)) allImages.push(url);
      });
    }
    if (p.additional_images && Array.isArray(p.additional_images)) {
      p.additional_images.forEach(img => {
        if (img && !allImages.includes(img)) allImages.push(img);
      });
    }
  }
  
  // Image count from backend or calculated
  const imageCount = p.image_count || allImages.length;
  
  // Oi Score - the single unified score
  const oiScore = Math.round(p.oi_score || p.score || p.final_score || p.productScore || p.opportunity_score || 50);
  
  // Supplier link - check flat fields AND nested data_sources.*.url.
  // Backend puts the real clickable URL in different places depending on the source:
  //   - AliExpress affiliate: data_sources.aliexpress.url (or .promotion_link)
  //   - CJ Dropshipping:       data_sources.cj_dropshipping.url
  //   - Some normalized paths: supplier_url / product_url / affiliate_url (flat)
  const ds = p.data_sources || {};
  const aliSrc = ds.aliexpress || {};
  const cjSrc = ds.cj_dropshipping || ds.cj || {};
  const supplierUrl =
    // Flat fields (legacy / normalized)
    p.affiliate_url || p.affiliateUrl || p.affiliate_link || p.affiliateLink ||
    p.promotionLink || p.promotion_link ||
    p.supplier_url || p.supplierUrl ||
    p.product_url  || p.productUrl ||
    // Nested per-source URLs (what the backend actually produces today)
    aliSrc.url || aliSrc.promotion_link || aliSrc.affiliate_url || aliSrc.product_url ||
    cjSrc.url  || cjSrc.product_url ||
    // Last-ditch fallbacks
    p.url || p.source_url || null;
  
  // 2026-04-25 honest scoring rewrite: backend now sends ``null`` for any
  // component without real signal (demand, trend, sentiment) instead of the
  // 50/55 baseline it used to fall back to. Preserve those nulls — using
  // ``|| 50`` here would silently re-fabricate the default we just killed
  // backend-side. The "unavailable" rendering branch below uses these
  // nulls to draw the striped "no data" bar.
  const hasRealDemandScore = p.demand_score !== undefined && p.demand_score !== null;
  const hasRealTrendScore = p.trend_score !== undefined && p.trend_score !== null;
  const hasRealSentimentScore = p.sentiment_score !== undefined && p.sentiment_score !== null;
  const hasAnyRealScores = hasRealDemandScore || hasRealTrendScore || hasRealSentimentScore || (p.sales_count > 0);

  // Preserve nulls verbatim. Don't coerce.
  const demandScore = p.demand_score !== undefined ? p.demand_score
    : (p.demandScore !== undefined ? p.demandScore : null);
  const trendScore = p.trend_score !== undefined ? p.trend_score
    : (p.trendScore !== undefined ? p.trendScore : null);
  // CRITICAL: preserve null sentiment_score from backend. Using `||` would
  // silently coerce null → 50, reintroducing the fake default we just killed.
  const sentimentScore =
    p.sentiment_score !== undefined
      ? p.sentiment_score   // may be number OR null (null = "we searched, found nothing")
      : (p.sentimentScore !== undefined ? p.sentimentScore : null);
  const sentimentWeightRedistributed = p.sentiment_weight_redistributed === true;
  const viralScore = p.viral_score || p.viralScore || 50;
  const profitMargin = (suggestedPrice > 0 && costPrice > 0) ? Math.round((profit / suggestedPrice) * 100) : 50;
  const profitScore = p.profit_score || p.profitScore || Math.min(100, profitMargin * 1.5);
  
  // Generate a STABLE product ID based on title + main image (for cache consistency)
  const title = p.title || p.name || p.product_title || 'Untitled Product';
  const stableId = p.id || p.product_id || `prod_${simpleHash(title + (mainImage || ''))}`;

  // Supplier/warehouse fields for badges + filter chips (Option A)
  //   - available_on: ['aliexpress'], ['cj_dropshipping'], or both (cross-referenced)
  //   - cross_referenced: true when the same product was found on both suppliers
  //   - cj_warehouse / us_warehouse / eu_warehouse: raw CJ warehouse info
  // Backend shape (ProductDiscovery._cross_reference_suppliers):
  //   product.available_on = ['aliexpress'] | ['cj_dropshipping'] | ['aliexpress', 'cj_dropshipping']
  //   product.cross_referenced = bool
  //   product.data_sources.cj_dropshipping.us_warehouse / eu_warehouse / warehouse
  const cjData = (p.data_sources && (p.data_sources.cj_dropshipping || p.data_sources.cj)) || {};
  const availableOn = Array.isArray(p.available_on) && p.available_on.length > 0
    ? p.available_on
    : (p.source ? [p.source] : []);
  const crossReferenced = p.cross_referenced === true || availableOn.length >= 2;
  const usWarehouse = !!(cjData.us_warehouse || p.us_warehouse);
  const euWarehouse = !!(cjData.eu_warehouse || p.eu_warehouse);
  const cjWarehouse = cjData.warehouse || p.cj_warehouse || null;
  const onCj = availableOn.includes('cj_dropshipping') || p.source === 'cj_dropshipping';
  const onAli = availableOn.includes('aliexpress') || p.source === 'aliexpress';

  return {
    id: stableId,
    title: title,
    image_url: mainImage,
    ai_image_url: p.ai_image_url || null,
    all_images: allImages,
    image_count: imageCount,
    cost_price: parseFloat(costPrice.toFixed(2)),
    suggested_price: parseFloat(suggestedPrice.toFixed(2)),
    profit: parseFloat(profit.toFixed(2)),
    oi_score: oiScore,
    niche: p.niche || p.category || fallbackNiche,
    tags: p.tags || [p.niche || p.category || 'trending'],
    source: p.source || 'aliexpress',
    is_mock: p.is_mock || p.source === 'mock_data',
    supplier_url: supplierUrl,
    // Supplier / warehouse metadata (Option A badges + filter chips)
    available_on: availableOn,
    cross_referenced: crossReferenced,
    on_aliexpress: onAli,
    on_cj: onCj,
    us_warehouse: usWarehouse,
    eu_warehouse: euWarehouse,
    cj_warehouse: cjWarehouse,
    sales_count: p.sales_count || p.salesCount || p.productSalesCount || 0,
    rating: p.rating || null,
    // Score breakdown with estimation flag
    demand_score: demandScore,
    trend_score: trendScore,
    sentiment_score: sentimentScore,
    sentiment_weight_redistributed: sentimentWeightRedistributed,
    viral_score: viralScore,
    profit_score: profitScore,
    scores_estimated: !hasAnyRealScores,
    // Honest-scoring fields (backend rewrite 2026-04-25):
    //   tier === 'INSUFFICIENT_DATA' → don't claim a buy verdict
    //   data_confidence_pct → 0–100 fraction of design weight backed by real signal
    //   missing_components → which components had no real data
    tier: p.tier || null,
    data_confidence_pct: p.data_confidence_pct ?? null,
    data_confidence: p.data_confidence ?? null,
    active_components: Array.isArray(p.active_components) ? p.active_components : [],
    missing_components: Array.isArray(p.missing_components) ? p.missing_components : [],
    commission_rate: p.commission_rate || p.commissionRate || null,
    recommendation: p.recommendation || null,
    reasons: p.reasons || [],
    risks: p.risks || [],
    data_sources: p.data_sources || {},
    // Social evidence trail (post-Fix #15) - real tweets/posts we can show to the user
    twitter_evidence: p.twitter_evidence || null,
    reddit_evidence: p.reddit_evidence || null,
    // Amazon evidence (Task #18) - niche-level Amazon search matched to this product
    amazon_evidence: p.amazon_evidence || null,
    amazon_buzz: typeof p.amazon_buzz === 'number' ? p.amazon_buzz : null,
    amazon_rating: typeof p.amazon_rating === 'number' ? p.amazon_rating : null,
    amazon_review_count: typeof p.amazon_review_count === 'number' ? p.amazon_review_count : null,
    // #56: opportunity/competition + lifecycle + proof-age signals consumed by
    // OpportunityBadges. Without these in the whitelist the badges never render
    // even though the backend sends saturation_score on every product.
    saturation_score: p.saturation_score ?? null,
    opportunity_score: p.opportunity_score ?? null,
    velocity_phase: p.velocity_phase || p.lifecycle_phase || null,
    days_of_proof: p.days_of_proof ?? null,
    times_seen: p.times_seen ?? null,
    raw_data: p,
  };
}

// ============================================================================
// HELPER: Score colors
// ============================================================================
function getScoreColor(score) {
  if (score >= 80) return 'text-green-400';
  if (score >= 60) return 'text-cyan-400';
  if (score >= 40) return 'text-yellow-400';
  return 'text-red-400';
}

function getScoreBgColor(score) {
  if (score >= 80) return 'from-green-500/20 to-green-600/10 border-green-500/30';
  if (score >= 60) return 'from-cyan-500/20 to-cyan-600/10 border-cyan-500/30';
  if (score >= 40) return 'from-yellow-500/20 to-yellow-600/10 border-yellow-500/30';
  return 'from-red-500/20 to-red-600/10 border-red-500/30';
}

// ============================================================================
// COMPONENT: SupplierBadges - small pills showing where the product ships from
// ============================================================================
// Shown in the lower-left of each product image. Honest to real backend data:
//   - US pill      → CJ product in a US warehouse (2–5 day shipping)
//   - EU pill      → CJ product in an EU warehouse
//   - ⚡ Cross-ref → Same product found on BOTH AliExpress and CJ
//   - CJ pill     → CJ-only product (no AliExpress match)
// AliExpress-only products get no badge (the default case — no visual noise).
function SupplierBadges({ product }) {
  const badges = [];

  if (product.cross_referenced) {
    badges.push(
      <span
        key="cross"
        title="Same product found on AliExpress AND CJ Dropshipping — more reliable sourcing"
        className="px-1.5 py-0.5 rounded-md bg-purple-500/80 text-white text-[10px] font-semibold flex items-center gap-0.5 backdrop-blur-sm"
      >
        <Zap className="w-2.5 h-2.5" />
        Cross-ref
      </span>
    );
  }

  if (product.us_warehouse) {
    badges.push(
      <span
        key="us"
        title="Ships from US warehouse (2–5 day delivery)"
        className="px-1.5 py-0.5 rounded-md bg-green-500/80 text-white text-[10px] font-semibold backdrop-blur-sm"
      >
        🇺🇸 US
      </span>
    );
  } else if (product.eu_warehouse) {
    badges.push(
      <span
        key="eu"
        title="Ships from EU warehouse (3–7 day delivery)"
        className="px-1.5 py-0.5 rounded-md bg-blue-500/80 text-white text-[10px] font-semibold backdrop-blur-sm"
      >
        🇪🇺 EU
      </span>
    );
  }

  // CJ-only pill: only show when we have CJ but NOT AliExpress (and no cross-ref pill).
  // Cross-referenced products already signal "on CJ" via the lightning bolt.
  if (product.on_cj && !product.on_aliexpress && !product.cross_referenced) {
    badges.push(
      <span
        key="cj"
        title="Only found on CJ Dropshipping — fewer competitors listing this on Shopify"
        className="px-1.5 py-0.5 rounded-md bg-orange-500/80 text-white text-[10px] font-semibold backdrop-blur-sm"
      >
        CJ only
      </span>
    );
  }

  if (badges.length === 0) return null;

  return (
    <div className="absolute bottom-3 left-3 flex flex-wrap gap-1 max-w-[60%]">
      {badges}
    </div>
  );
}

// ============================================================================
// COMPONENT: OpportunityBadges (#56) — competition, lifecycle phase, proof-age
// ============================================================================
// Renders ONLY when the backing fields exist, so on-demand /quick results and
// persistent catalog results both degrade gracefully (older cached cards just
// show nothing extra). This is what surfaces "caught early / low competition /
// N days of proof" — the trust + non-saturation signals.
const _PHASE_BADGE = {
  discovery:   { label: '🔥 Just Caught', cls: 'bg-pink-500/20 text-pink-300 border-pink-500/30' },
  early_spike: { label: '🔥 Just Caught', cls: 'bg-pink-500/20 text-pink-300 border-pink-500/30' },
  growth:      { label: '📈 Growing',     cls: 'bg-cyan-500/20 text-cyan-300 border-cyan-500/30' },
  maturity:    { label: '✅ Proven',      cls: 'bg-green-500/20 text-green-300 border-green-500/30' },
  decline:     { label: '↓ Fading',       cls: 'bg-white/10 text-white/50 border-white/10' },
};

function OpportunityBadges({ product }) {
  const badges = [];

  const phase = product.velocity_phase;
  if (phase && _PHASE_BADGE[phase]) {
    const p = _PHASE_BADGE[phase];
    badges.push(
      <span key="phase" title="How early we caught this product in its lifecycle"
            className={`px-2 py-0.5 rounded-full text-[10px] font-medium border ${p.cls}`}>{p.label}</span>
    );
  }

  // Competition from opportunity_score, falling back to saturation_score
  // (which may be 0-1 or 0-100). Higher opportunity = lower competition.
  let opp = product.opportunity_score;
  if (opp == null && product.saturation_score != null) {
    const s = product.saturation_score;
    opp = 100 - (s <= 1 ? s * 100 : s);
  }
  if (opp != null) {
    const comp = opp >= 65
      ? { label: 'Low competition', cls: 'bg-green-500/20 text-green-300 border-green-500/30' }
      : opp >= 40
        ? { label: 'Medium competition', cls: 'bg-amber-500/20 text-amber-300 border-amber-500/30' }
        : { label: 'High competition', cls: 'bg-red-500/20 text-red-300 border-red-500/30' };
    badges.push(
      <span key="comp" title={`Opportunity ${Math.round(opp)}/100 — higher means less saturated`}
            className={`px-2 py-0.5 rounded-full text-[10px] font-medium border ${comp.cls}`}>{comp.label}</span>
    );
  }

  const d = product.days_of_proof;
  if (d != null) {
    const label = d <= 0 ? 'Caught today' : `Caught ${d}d ago`;
    const seen = product.times_seen > 1 ? ` · seen ${product.times_seen}×` : '';
    badges.push(
      <span key="proof" title="Days since we first detected this product — its track record"
            className="px-2 py-0.5 rounded-full text-[10px] font-medium border bg-white/10 text-white/60 border-white/10">{label}{seen}</span>
    );
  }

  if (badges.length === 0) return null;
  return <div className="flex flex-wrap items-center gap-1.5 mt-2">{badges}</div>;
}

// ============================================================================
// COMPONENT: Product Card - CLICKABLE, Oi Score + supplier badges
// ============================================================================
// Task #35: ProductCard is rendered up to 20-50× per discovery result.
// Every parent re-render (filter change, modal toggle, image enhancement
// progress tick) used to rebuild every card from scratch. Wrapping in
// React.memo with a referential equality check on `product` means cards
// only re-render when their backing product object actually changes —
// the dominant interaction perf win for this page.
const ProductCard = React.memo(function ProductCard({ product, onClick }) {
  const [imageError, setImageError] = useState(false);
  const displayImage = product.ai_image_url || product.image_url;
  const hasAiImage = !!product.ai_image_url;

  return (
    <div
      onClick={onClick}
      className="backdrop-blur-xl bg-white/5 rounded-2xl border border-white/10 overflow-hidden hover:border-purple-500/40 hover:scale-[1.02] transition-all cursor-pointer group"
    >
      {/* Image */}
      <div className="aspect-square bg-gradient-to-br from-purple-500/10 to-cyan-500/10 relative overflow-hidden">
        {displayImage && !imageError ? (
          <img
            src={resolveImageUrl(displayImage)}
            alt={product.title}
            // Task #35: lazy-load below-the-fold cards so initial paint
            // doesn't block on 20+ AE CDN image fetches. decoding="async"
            // also lets the browser do JPEG decode off the main thread.
            loading="lazy"
            decoding="async"
            className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
            onError={() => setImageError(true)}
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <Package className="w-12 h-12 text-white/20" />
          </div>
        )}
        
        {/* AI Image Badge */}
        {hasAiImage && (
          <div className="absolute bottom-3 right-3 px-2 py-1 rounded-full bg-purple-500/80 text-white text-xs font-medium flex items-center gap-1">
            <Sparkles className="w-3 h-3" />
            AI
          </div>
        )}
        
        {/* Multi-Image Badge - shows when product has multiple source images */}
        {!hasAiImage && product.image_count > 1 && (
          <div className="absolute bottom-3 right-3 px-2 py-1 rounded-full bg-cyan-500/80 text-white text-xs font-medium flex items-center gap-1">
            <ImageIcon className="w-3 h-3" />
            {product.image_count}
          </div>
        )}
        
        {/* Estimated Score Warning */}
        {product.scores_estimated && (
          <div className="absolute top-3 left-3 px-2 py-1 rounded-full bg-yellow-500/80 text-black text-xs font-medium flex items-center gap-1" title="Scores are estimated - limited data available">
            <Info className="w-3 h-3" />
            Est.
          </div>
        )}

        {/* Supplier / warehouse badges (Option A) */}
        <SupplierBadges product={product} />
        
        {/* Oi Score Badge - THE ONLY BADGE ON CARDS */}
        <div className={`absolute top-3 right-3 px-3 py-2 rounded-xl bg-gradient-to-br ${getScoreBgColor(product.oi_score)} border backdrop-blur-sm`}>
          <div className="flex items-center gap-1.5">
            <Brain className="w-4 h-4 text-purple-400" />
            <span className={`text-lg font-bold ${getScoreColor(product.oi_score)}`}>{product.oi_score}</span>
          </div>
        </div>

        {/* Hover Overlay */}
        <div className="absolute inset-0 bg-purple-500/0 group-hover:bg-purple-500/10 transition-colors flex items-center justify-center opacity-0 group-hover:opacity-100">
          <div className="px-4 py-2 rounded-xl bg-black/80 backdrop-blur-sm text-white text-sm font-medium flex items-center gap-2">
            <Eye className="w-4 h-4" />
            View Details
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="p-4">
        <h3 className="text-white font-semibold mb-2 line-clamp-2 group-hover:text-purple-300 transition-colors text-sm">
          {product.title}
        </h3>
        
        {/* Pricing */}
        <div className="flex items-center gap-2 mb-2">
          <span className="text-white/50 text-sm line-through">${product.cost_price.toFixed(2)}</span>
          <span className="text-green-400 font-medium">${product.suggested_price.toFixed(2)}</span>
          <span className="text-purple-400 font-bold ml-auto">+${product.profit.toFixed(2)}</span>
        </div>

        {/* Quick Stats */}
        <div className="flex items-center gap-3 text-xs text-white/50">
          {product.sales_count > 0 && (
            <span
              className="flex items-center gap-1"
              title="AliExpress 'lastest_volume' field — recent orders (rolling ~30-day window). NOT lifetime cumulative sales (which AE shows as '5,000+ sold' on listings)."
            >
              <ShoppingCart className="w-3 h-3" />
              {product.sales_count.toLocaleString()} <span className="text-white/40">recent</span>
            </span>
          )}
          {product.rating && (
            <span className="flex items-center gap-1">
              <Star className="w-3 h-3 text-yellow-400" />
              {product.rating.toFixed(1)}
            </span>
          )}
          {product.commission_rate && product.source === 'aliexpress' && (
            <span
              className="flex items-center gap-1 text-green-400/80"
              title="AliExpress Standard Affiliate Program: flat 7% across all products in the standard product feed. To unlock variable commissions (10-30%), Ospra would need to query the AE Dropshipping API top-sellers feed instead — tracked as a follow-up. Until then, this number is constant and shouldn't drive product selection."
            >
              {product.commission_rate}% AE std
            </span>
          )}
          {product.commission_rate && product.source !== 'aliexpress' && (
            <span
              className="flex items-center gap-1 text-green-400"
              title="Supplier commission rate."
            >
              {product.commission_rate}% comm
            </span>
          )}
        </div>

        {/* #56: competition / early-caught / days-of-proof badges */}
        <OpportunityBadges product={product} />
      </div>
    </div>
  );
});

// ============================================================================
// COMPONENT: Image Gallery with Toggle - Shows ALL enhanced images
// ============================================================================
function ImageGallery({ product, aiImageUrl, enhancedImages, onRegenerateAi, regenerating }) {
  // Get all enhanced images (array) or fall back to single aiImageUrl
  const allEnhancedImages = enhancedImages && enhancedImages.length > 0
    ? enhancedImages
    : (aiImageUrl ? [aiImageUrl] : []);

  const hasEnhancedImages = allEnhancedImages.length > 0;
  const [showAiImage, setShowAiImage] = useState(hasEnhancedImages);
  const [selectedOriginalIndex, setSelectedOriginalIndex] = useState(0);
  const [selectedEnhancedIndex, setSelectedEnhancedIndex] = useState(0);
  const [imageError, setImageError] = useState(false);

  const allOriginalImages = product.all_images || [product.image_url].filter(Boolean);
  const currentOriginalImage = allOriginalImages[selectedOriginalIndex] || product.image_url;
  const currentEnhancedImage = allEnhancedImages[selectedEnhancedIndex] || null;
  const displayImage = showAiImage && currentEnhancedImage ? currentEnhancedImage : currentOriginalImage;

  // Reset image error when switching images
  useEffect(() => {
    setImageError(false);
  }, [displayImage]);

  return (
    <div className="backdrop-blur-xl bg-white/5 rounded-2xl border border-white/10 p-4">
      <div className="flex items-center justify-between mb-3">
        <h4 className="text-white font-semibold flex items-center gap-2">
          <Camera className="w-4 h-4 text-purple-400" />
          Product Images
          {/* Show count of enhanced images */}
          {hasEnhancedImages && (
            <span className="text-xs text-purple-300 bg-purple-500/20 px-2 py-0.5 rounded-full">
              {allEnhancedImages.length} enhanced
            </span>
          )}
        </h4>

        <div className="flex items-center gap-2">
          {/* Image Type Toggle */}
          <button
            onClick={() => setShowAiImage(!showAiImage)}
            disabled={!hasEnhancedImages}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium flex items-center gap-2 transition-all ${
              showAiImage && hasEnhancedImages
                ? 'bg-purple-500/20 border border-purple-500/30 text-purple-300'
                : 'bg-white/5 border border-white/10 text-white/60'
            } ${!hasEnhancedImages ? 'opacity-50 cursor-not-allowed' : ''}`}
          >
            {showAiImage ? <ToggleRight className="w-4 h-4" /> : <ToggleLeft className="w-4 h-4" />}
            {showAiImage && hasEnhancedImages ? 'Enhanced' : 'Original'}
          </button>

          {/* Enhance Button */}
          <button
            onClick={() => onRegenerateAi()}
            disabled={regenerating}
            className="px-3 py-1.5 rounded-lg bg-gradient-to-r from-purple-600 to-cyan-600 text-white text-xs font-medium hover:opacity-90 disabled:opacity-50 flex items-center gap-1"
          >
            {regenerating ? (
              <>
                <Loader2 className="w-3 h-3 animate-spin" />
                Enhancing...
              </>
            ) : (
              <>
                <Wand2 className="w-3 h-3" />
                {hasEnhancedImages ? 'Re-enhance' : 'Enhance'}
              </>
            )}
          </button>
        </div>
      </div>

      {/* Main Image Display */}
      <div className="relative aspect-video rounded-xl overflow-hidden bg-gradient-to-br from-purple-500/10 to-cyan-500/10 mb-3">
        {displayImage && !imageError ? (
          <img
            src={resolveImageUrl(displayImage)}
            alt={product.title}
            className="w-full h-full object-contain"
            onError={() => setImageError(true)}
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center flex-col gap-3">
            <Package className="w-16 h-16 text-white/20" />
            <p className="text-white/40 text-sm">No image available</p>
          </div>
        )}

        {/* Image Type Badge */}
        <div className={`absolute top-3 left-3 px-2 py-1 rounded-full text-xs font-medium flex items-center gap-1 ${
          showAiImage && hasEnhancedImages
            ? 'bg-purple-500/80 text-white'
            : 'bg-white/20 text-white/80'
        }`}>
          {showAiImage && hasEnhancedImages ? (
            <><Sparkles className="w-3 h-3" /> Enhanced {allEnhancedImages.length > 1 ? `(${selectedEnhancedIndex + 1}/${allEnhancedImages.length})` : ''}</>
          ) : (
            <><ImageIcon className="w-3 h-3" /> Original {allOriginalImages.length > 1 ? `(${selectedOriginalIndex + 1}/${allOriginalImages.length})` : ''}</>
          )}
        </div>
      </div>

      {/* Thumbnail Strip - Shows ENHANCED images when in AI mode */}
      {showAiImage && allEnhancedImages.length > 1 && (
        <div className="flex gap-2 overflow-x-auto pb-2">
          {allEnhancedImages.map((img, idx) => (
            <button
              key={idx}
              onClick={() => setSelectedEnhancedIndex(idx)}
              className={`flex-shrink-0 w-16 h-16 rounded-lg overflow-hidden border-2 transition-all ${
                selectedEnhancedIndex === idx
                  ? 'border-purple-500'
                  : 'border-transparent opacity-60 hover:opacity-100'
              }`}
            >
              <img src={resolveImageUrl(img)} alt={`Enhanced ${idx + 1}`} className="w-full h-full object-cover" />
            </button>
          ))}
        </div>
      )}

      {/* Thumbnail Strip - Shows ORIGINAL images when in original mode */}
      {!showAiImage && allOriginalImages.length > 1 && (
        <div className="flex gap-2 overflow-x-auto pb-2">
          {allOriginalImages.map((img, idx) => (
            <button
              key={idx}
              onClick={() => setSelectedOriginalIndex(idx)}
              className={`flex-shrink-0 w-16 h-16 rounded-lg overflow-hidden border-2 transition-all ${
                selectedOriginalIndex === idx
                  ? 'border-cyan-500'
                  : 'border-transparent opacity-60 hover:opacity-100'
              }`}
            >
              <img src={resolveImageUrl(img)} alt={`Original ${idx + 1}`} className="w-full h-full object-cover" />
            </button>
          ))}
        </div>
      )}

      {/* AI Image Notice */}
      {!hasEnhancedImages && (
        <p className="text-white/40 text-xs mt-2 text-center">
          Click "Enhance" to remove backgrounds (~$0.06/image)
          {allOriginalImages.length > 1 && (
            <span className="block text-cyan-400 mt-1">
              {allOriginalImages.length} images available - use "All" button to enhance all at once
            </span>
          )}
        </p>
      )}

      {/* Comparison Note */}
      {hasEnhancedImages && (
        <p className="text-white/40 text-xs mt-2 text-center">
          {allEnhancedImages.length > 1
            ? `${allEnhancedImages.length} enhanced images ready! Toggle to compare with originals.`
            : 'Toggle between Enhanced and Original to compare.'}
        </p>
      )}
    </div>
  );
}

// ============================================================================
// COMPONENT: Social Evidence Panel (Fix #15d)
// ============================================================================
// Renders the actual twitter/reddit evidence trail persisted by the backend.
// Three states per source:
//   1. Real matches  → show sample tweets / clickable Reddit posts
//   2. Searched, no matches (backend: available=false, reason=no_matching_posts
//      OR found_real_tweets=false) → labeled honest empty state
//   3. No evidence object present at all (backend never ran enrichment) →
//      show a muted "Not yet checked" line instead of silence
//
// This replaces the old "trust the aggregate number" pattern. Users can now
// click through to real Reddit posts and read paraphrased Grok tweets.
// ============================================================================
function SocialEvidencePanel({ product, twitterEvidence, redditEvidence, amazonEvidence, dataSources }) {
  // ── PHASE K: ON-DEMAND AMAZON REVIEW TEXT FETCH ──────────────────────────
  // The bulk-at-discovery fetch was killed for cost reasons (~$45-90/mo).
  // Verbatim Amazon review prose is now a click-to-load action: user
  // explicitly opts in per product. The server caches by ASIN for 24h so
  // repeated clicks on the same listing within a day reuse one Apify
  // call (free re-render).
  const [amzText, setAmzText] = useState(null);          // result payload
  const [amzTextLoading, setAmzTextLoading] = useState(false);
  const [amzTextError, setAmzTextError] = useState(null);

  const handleFetchAmazonText = useCallback(async () => {
    if (!product || amzTextLoading) return;
    setAmzTextLoading(true);
    setAmzTextError(null);
    // Track the click — answers "is this on-demand fetch button
    // actually being used, and how often is the response cached?"
    capture(EVENTS.AMAZON_REVIEWS_FETCH_REQUESTED, {
      product_title: product?.title?.slice(0, 80),
      niche: product?.niche,
    });
    try {
      const result = await api.fetchAmazonReviewText(product, 15);
      if (!result || result.success === false) {
        setAmzTextError(result?.error || 'Fetch failed');
        capture(EVENTS.AMAZON_REVIEWS_FETCH_FAILED, {
          error: result?.error || 'unknown',
        });
      } else if (!result.available) {
        // Clean "no data" state — surface the reason but not as an error
        setAmzText({ ...result, _empty: true });
        capture(EVENTS.AMAZON_REVIEWS_FETCH_NO_DATA, {
          reason: result?.reason || 'unknown',
        });
      } else {
        setAmzText(result);
        capture(EVENTS.AMAZON_REVIEWS_FETCH_SUCCEEDED, {
          review_count: result.review_count_returned,
          cached: !!result.cached,
          verified_share: result.verified_share,
        });
      }
    } catch (err) {
      setAmzTextError(err.message || 'Fetch failed');
      capture(EVENTS.AMAZON_REVIEWS_FETCH_FAILED, {
        error: err?.message || 'exception',
      });
    } finally {
      setAmzTextLoading(false);
    }
  }, [product, amzTextLoading]);

  // ── AMAZON STATE DETECTION (Task #18 - primary social signal) ────────────
  // amazon_evidence can be:
  //   { found_matches: true, top_matches: [...], buzz_score, ... }  → show data
  //   { found_matches: false, reason: '...', ... }                   → show empty state
  //   null/undefined                                                 → not checked
  const amazon = amazonEvidence || null;
  const amazonChecked = amazon !== null || dataSources?.amazon_reviews !== undefined;
  const amazonHasRealData = amazon?.found_matches === true &&
    Array.isArray(amazon?.top_matches) && amazon.top_matches.length > 0;
  const amazonNicheSearched = amazon?.niche_searched || dataSources?.amazon_reviews?.niche_searched;

  // ── TWITTER STATE DETECTION ──────────────────────────────────────────────
  // twitter_evidence can be:
  //   { found_real_tweets: true, sample_tweets: [...], ... }   → show data
  //   { found_real_tweets: false, ... }                         → show empty state
  //   { error: "...", found_real_tweets: false }                → show error state
  //   null/undefined                                            → not checked
  const twitter = twitterEvidence || null;
  const twitterChecked = twitter !== null;
  const twitterHasRealData = twitter?.found_real_tweets === true &&
    Array.isArray(twitter?.sample_tweets) && twitter.sample_tweets.length > 0;
  const twitterHadError = twitterChecked && !!twitter?.error;

  // ── REDDIT STATE DETECTION ───────────────────────────────────────────────
  const reddit = Array.isArray(redditEvidence) ? redditEvidence : null;
  const redditChecked = reddit !== null || dataSources?.reddit !== undefined;
  const redditHasRealData = Array.isArray(reddit) && reddit.length > 0;
  const redditSubsSearched = dataSources?.reddit?.subreddits_searched || [];

  // ── HELPERS ──────────────────────────────────────────────────────────────
  const formatRelative = (iso) => {
    if (!iso) return '';
    try {
      const then = new Date(iso).getTime();
      const diffMin = Math.round((Date.now() - then) / 60000);
      if (diffMin < 1) return 'just now';
      if (diffMin < 60) return `${diffMin}m ago`;
      const diffHr = Math.round(diffMin / 60);
      if (diffHr < 24) return `${diffHr}h ago`;
      return `${Math.round(diffHr / 24)}d ago`;
    } catch { return ''; }
  };

  const formatRedditDate = (utc) => {
    if (!utc) return '';
    return formatRelative(new Date(utc * 1000).toISOString());
  };

  return (
    <div className="backdrop-blur-xl bg-white/5 rounded-2xl border border-white/10 p-4 space-y-5">
      <div className="flex items-center justify-between">
        <h4 className="text-white font-semibold flex items-center gap-2">
          <MessageSquare className="w-4 h-4 text-cyan-400" />
          Social Evidence
        </h4>
        <span
          className="text-[10px] text-white/40 italic"
          title="Sentiment signals from live social platforms. Twitter data is paraphrased from Grok (not live scraped). Amazon shows fuzzy-matched listings and per-product review text when available."
        >
          What we actually found
        </span>
      </div>

      {/* ── AMAZON SUB-SECTION (Task #18 - primary signal) ──────────────── */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-md bg-[#FF9900]/90 flex items-center justify-center text-[10px] font-bold text-black">
              A
            </div>
            <span className="text-white/80 text-sm font-medium">Amazon</span>
            <span
              className="text-[10px] px-1.5 py-0.5 rounded bg-green-500/10 text-green-300/80 border border-green-500/20"
              title="Real Amazon listings fuzzy-matched to this product. Rating and review counts reflect actual purchase behavior."
            >
              purchase signal
            </span>
            <span
              className="text-[10px] px-1.5 py-0.5 rounded bg-cyan-500/10 text-cyan-300/80 border border-cyan-500/20"
              title="Primary sentiment source: aggregate rating × review count is the strongest validation of real market demand."
            >
              primary
            </span>
          </div>
          {amazon?.fetched_at && (
            <span className="text-[10px] text-white/30">
              {formatRelative(amazon.fetched_at)}
            </span>
          )}
        </div>

        {!amazonChecked && (
          <p className="text-white/40 text-xs italic pl-8">Not yet checked.</p>
        )}

        {amazonChecked && !amazonHasRealData && (
          <div className="ml-8 text-xs text-white/50 bg-white/5 border border-white/10 rounded-lg px-3 py-2">
            <span className="font-medium">No matching Amazon listings found.</span>
            <span className="block text-[10px] text-white/40 mt-0.5">
              {amazonNicheSearched
                ? `Searched the "${amazonNicheSearched}" niche — this product didn't fuzzy-match any listings in the pool.`
                : 'This product didn\'t fuzzy-match any listings in the niche pool.'}
              {amazon?.reason === 'outside_enrichment_cap' &&
                ' (Only the top 15 products get Amazon enrichment per discovery.)'}
            </span>
          </div>
        )}

        {amazonHasRealData && (
          <div className="ml-8 space-y-2">
            {/* Summary stats: aggregate rating + review count + buzz score */}
            <div className="flex flex-wrap gap-2 text-[11px]">
              {typeof amazon.aggregate_rating === 'number' && (
                <span className="px-2 py-0.5 rounded bg-yellow-500/10 border border-yellow-500/30 text-yellow-300">
                  ★ {amazon.aggregate_rating.toFixed(2)} avg
                </span>
              )}
              {typeof amazon.total_reviews === 'number' && amazon.total_reviews > 0 && (
                <span className="px-2 py-0.5 rounded bg-white/5 border border-white/10 text-white/70">
                  {amazon.total_reviews.toLocaleString()} reviews
                </span>
              )}
              {typeof amazon.buzz_score === 'number' && (
                <span
                  className={`px-2 py-0.5 rounded border ${
                    amazon.buzz_score >= 75 ? 'bg-green-500/10 border-green-500/30 text-green-300' :
                    amazon.buzz_score >= 50 ? 'bg-cyan-500/10 border-cyan-500/30 text-cyan-300' :
                    'bg-white/5 border-white/10 text-white/60'
                  }`}
                  title="Buzz score blends rating and review count (log-saturated so giants don't pin at 100)"
                >
                  buzz: {Math.round(amazon.buzz_score)}
                </span>
              )}
              {typeof amazon.match_count === 'number' && amazon.match_count > 0 && (
                <span className="px-2 py-0.5 rounded bg-purple-500/10 border border-purple-500/30 text-purple-300/90">
                  {amazon.match_count} match{amazon.match_count === 1 ? '' : 'es'} in pool
                </span>
              )}
            </div>

            {/* Top matching Amazon listings - clickable */}
            <div className="space-y-1.5">
              {amazon.top_matches.slice(0, 3).map((match, i) => (
                <a
                  key={match.asin || i}
                  href={match.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block bg-white/5 hover:bg-white/10 border border-[#FF9900]/20 hover:border-[#FF9900]/50 rounded-lg px-3 py-2.5 transition-all group"
                >
                  <div className="flex items-start justify-between gap-2 mb-1">
                    <div className="flex-1 min-w-0">
                      <span className="text-sm text-white/90 group-hover:text-yellow-200 leading-snug line-clamp-2">
                        {match.title}
                      </span>
                    </div>
                    <ExternalLink className="w-3.5 h-3.5 text-white/30 group-hover:text-yellow-300 flex-shrink-0 mt-0.5" />
                  </div>

                  <div className="flex flex-wrap items-center gap-3 text-[10px] text-white/50">
                    {typeof match.rating === 'number' && match.rating > 0 && (
                      <span className="text-yellow-300/90">★ {match.rating.toFixed(1)}</span>
                    )}
                    {typeof match.reviews_count === 'number' && match.reviews_count > 0 && (
                      <span>{match.reviews_count.toLocaleString()} reviews</span>
                    )}
                    {typeof match.price === 'number' && match.price > 0 && (
                      <span className="text-green-300/80">${match.price.toFixed(2)}</span>
                    )}
                    {typeof match.match_score === 'number' && (
                      <span
                        className="text-cyan-300/70"
                        title="Title similarity to your product (0-1). Higher = more confident match."
                      >
                        match: {(match.match_score * 100).toFixed(0)}%
                      </span>
                    )}
                    {match.bestseller_rank > 0 && (
                      <span className="text-purple-300/80">#{match.bestseller_rank} BSR</span>
                    )}
                  </div>
                </a>
              ))}
            </div>

            {/* ── PHASE K: ON-DEMAND VERBATIM REVIEWS ────────────────────── */}
            {/* Click-to-load. Server caches 24h per ASIN, so a second click  */}
            {/* on the same listing within 24h is a free re-render.           */}
            {!amzText && !amzTextLoading && !amzTextError && (
              <button
                type="button"
                onClick={handleFetchAmazonText}
                className="text-[11px] px-3 py-1.5 rounded-md bg-[#FF9900]/10 hover:bg-[#FF9900]/20 border border-[#FF9900]/30 hover:border-[#FF9900]/60 text-yellow-300 transition-all"
                title="Pulls verbatim Amazon reviews via Apify — server caches 24h per ASIN, so re-clicks within a day don't re-bill."
              >
                Fetch real Amazon reviews →
              </button>
            )}

            {amzTextLoading && (
              <div className="text-[11px] text-white/50 px-3 py-1.5">
                Fetching Amazon review text…
              </div>
            )}

            {amzTextError && (
              <div className="text-[11px] text-red-300/80 px-3 py-1.5 bg-red-500/5 border border-red-500/20 rounded-md">
                Couldn't fetch reviews: {amzTextError}
              </div>
            )}

            {amzText?._empty && (
              <div className="text-[11px] text-white/40 px-3 py-1.5">
                No verbatim Amazon reviews available
                {amzText.reason ? ` (${amzText.reason})` : '.'}
              </div>
            )}

            {amzText && !amzText._empty && Array.isArray(amzText.reviews) && amzText.reviews.length > 0 && (
              <div className="mt-2 space-y-1.5">
                <div className="flex items-center gap-2 text-[11px] text-white/60">
                  <span className="text-yellow-300/90">
                    {amzText.review_count_returned} review{amzText.review_count_returned === 1 ? '' : 's'}
                  </span>
                  {typeof amzText.average_rating === 'number' && (
                    <span className="text-yellow-300/70">avg ★ {amzText.average_rating.toFixed(2)}</span>
                  )}
                  {typeof amzText.verified_share === 'number' && (
                    <span className="text-green-300/70">
                      {Math.round(amzText.verified_share * 100)}% verified
                    </span>
                  )}
                  {amzText.cached && (
                    <span className="text-cyan-300/60" title="Served from 24h ASIN cache (no Apify charge)">
                      cached
                    </span>
                  )}
                </div>
                <div className="space-y-1">
                  {amzText.reviews.slice(0, 5).map((r, i) => (
                    <div
                      key={i}
                      className="text-[11px] bg-white/5 border border-white/10 rounded px-2.5 py-1.5"
                    >
                      <div className="flex items-center gap-2 text-[10px] text-white/50 mb-0.5">
                        {typeof r.rating === 'number' && (
                          <span className="text-yellow-300/90">★ {r.rating}</span>
                        )}
                        {r.verified && <span className="text-green-300/80">✓ verified</span>}
                        {r.title && <span className="text-white/70 italic">"{r.title}"</span>}
                      </div>
                      <p className="text-white/80 leading-snug">{r.text}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Divider */}
      <div className="border-t border-white/10" />

      {/* ── TWITTER SUB-SECTION ─────────────────────────────────────────── */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-md bg-black/40 flex items-center justify-center text-[10px] font-bold text-white border border-white/10">
              X
            </div>
            <span className="text-white/80 text-sm font-medium">Twitter / X</span>
            {twitter?.source_type === 'grok_live_search' && Array.isArray(twitter?.citations) && twitter.citations.length > 0 ? (
              <span
                className="text-[10px] px-1.5 py-0.5 rounded bg-green-500/10 text-green-300/80 border border-green-500/20"
                title={`xAI live search returned ${twitter.citations.length} real tweet citations.`}
              >
                live · {twitter.citations.length} citation{twitter.citations.length === 1 ? '' : 's'}
              </span>
            ) : (
              <span
                className="text-[10px] px-1.5 py-0.5 rounded bg-yellow-500/10 text-yellow-300/80 border border-yellow-500/20"
                title="Grok paraphrased these from its X knowledge — no live citations were returned for this product."
              >
                paraphrased
              </span>
            )}
          </div>
          {twitterChecked && twitter?.fetched_at && (
            <span className="text-[10px] text-white/30">
              {formatRelative(twitter.fetched_at)}
            </span>
          )}
        </div>

        {!twitterChecked && (
          <p className="text-white/40 text-xs italic pl-8">Not yet checked.</p>
        )}

        {twitterChecked && twitterHadError && (
          <div className="ml-8 text-xs text-red-300/80 bg-red-500/5 border border-red-500/20 rounded-lg px-3 py-2">
            Twitter data unavailable for this product.
            <span className="block text-[10px] text-red-300/60 mt-0.5">
              {String(twitter.error).slice(0, 120)}
            </span>
          </div>
        )}

        {twitterChecked && !twitterHadError && !twitterHasRealData && (
          <div className="ml-8 text-xs text-white/50 bg-white/5 border border-white/10 rounded-lg px-3 py-2">
            <span className="font-medium">No tweets found at product or category level.</span>
            <span className="block text-[10px] text-white/40 mt-0.5">
              Common for unbranded or generic products.
              {twitter?.recommendation === 'INSUFFICIENT_DATA' && ' Grok honestly returned no data rather than fabricating.'}
            </span>
          </div>
        )}

        {twitterHasRealData && (
          <div className="ml-8 space-y-2">
            {/* Search level indicator (product-specific vs category-level) */}
            {twitter.search_level === 'category' && (
              <div className="text-[11px] bg-blue-500/10 border border-blue-500/30 rounded-lg px-2.5 py-1.5 text-blue-300">
                <span className="font-medium">Category-level signal:</span>{' '}
                <span className="text-blue-200/90">
                  {twitter.category_searched ? `"${twitter.category_searched}"` : 'product type'}
                </span>
                <span className="block text-[10px] text-blue-300/60 mt-0.5">
                  No product-specific tweets found, so showing tweets about the category.
                </span>
              </div>
            )}
            {twitter.search_level === 'product' && (
              <div className="text-[11px] text-green-300/80">
                <span className="px-1.5 py-0.5 rounded bg-green-500/10 border border-green-500/30">
                  Product-specific
                </span>
              </div>
            )}

            {/* Summary row */}
            <div className="flex flex-wrap gap-2 text-[11px]">
              {typeof twitter.tweet_count === 'number' && twitter.tweet_count > 0 && (
                <span className="px-2 py-0.5 rounded bg-white/5 border border-white/10 text-white/70">
                  ~{twitter.tweet_count.toLocaleString()} tweets
                </span>
              )}
              {twitter.sentiment_label && (
                <span className={`px-2 py-0.5 rounded border ${
                  twitter.sentiment_label === 'positive' ? 'bg-green-500/10 border-green-500/30 text-green-300' :
                  twitter.sentiment_label === 'negative' ? 'bg-red-500/10 border-red-500/30 text-red-300' :
                  twitter.sentiment_label === 'mixed' ? 'bg-yellow-500/10 border-yellow-500/30 text-yellow-300' :
                  'bg-white/5 border-white/10 text-white/70'
                }`}>
                  {twitter.sentiment_label}
                </span>
              )}
              {typeof twitter.sentiment_score === 'number' && (
                <span className="px-2 py-0.5 rounded bg-cyan-500/10 border border-cyan-500/30 text-cyan-300">
                  score: {twitter.sentiment_score.toFixed(2)}
                </span>
              )}
              {twitter.buzz_level && (
                <span className="px-2 py-0.5 rounded bg-purple-500/10 border border-purple-500/30 text-purple-300">
                  buzz: {twitter.buzz_level}
                </span>
              )}
            </div>

            {/* Sample tweets — paraphrased OR (Phase F) backed by real
                X citations from xAI live search. When citations are
                present, render each tweet's row as a clickable link. */}
            <div className="space-y-1.5">
              {twitter.sample_tweets.slice(0, 5).map((t, i) => {
                const url = Array.isArray(twitter.citations) ? twitter.citations[i] : null;
                if (url) {
                  return (
                    <a
                      key={i}
                      href={url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="block text-xs text-white/80 bg-white/5 hover:bg-white/10 border border-white/10 hover:border-cyan-500/30 rounded-lg px-3 py-2 leading-relaxed transition-colors"
                      title="Open the real tweet on X"
                    >
                      <span className="text-cyan-300 mr-1">›</span>{t}
                      <span className="block text-[10px] text-cyan-300/70 mt-1 truncate">{url}</span>
                    </a>
                  );
                }
                return (
                  <div key={i} className="text-xs text-white/75 bg-white/5 border border-white/10 rounded-lg px-3 py-2 leading-relaxed">
                    <span className="text-white/40 mr-1">›</span>{t}
                  </div>
                );
              })}
              {/* When the model returned more citations than paraphrased
                  samples, surface the extras as bare links so the user
                  sees we've actually pulled fresh sources. */}
              {Array.isArray(twitter.citations) &&
                twitter.citations.length > (twitter.sample_tweets?.length || 0) && (
                  <div className="text-[11px] text-white/50 mt-1">
                    <span className="text-white/40">More citations: </span>
                    {twitter.citations
                      .slice(twitter.sample_tweets?.length || 0, (twitter.sample_tweets?.length || 0) + 5)
                      .map((url, i) => (
                        <a
                          key={i}
                          href={url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-cyan-300/80 hover:text-cyan-200 underline mr-2 break-all"
                        >
                          {url.replace(/^https?:\/\//, '').slice(0, 32)}…
                        </a>
                      ))}
                  </div>
                )}
            </div>

            {/* Praise / complaints */}
            {(twitter.common_praise?.length > 0 || twitter.common_complaints?.length > 0) && (
              <div className="grid grid-cols-2 gap-2 text-[11px] mt-2">
                {twitter.common_praise?.length > 0 && (
                  <div className="bg-green-500/5 border border-green-500/20 rounded-lg px-2.5 py-2">
                    <p className="text-green-400/80 font-medium mb-1">Praise</p>
                    <ul className="text-white/70 space-y-0.5">
                      {twitter.common_praise.slice(0, 4).map((c, i) => <li key={i}>• {c}</li>)}
                    </ul>
                  </div>
                )}
                {twitter.common_complaints?.length > 0 && (
                  <div className="bg-red-500/5 border border-red-500/20 rounded-lg px-2.5 py-2">
                    <p className="text-red-400/80 font-medium mb-1">Complaints</p>
                    <ul className="text-white/70 space-y-0.5">
                      {twitter.common_complaints.slice(0, 4).map((c, i) => <li key={i}>• {c}</li>)}
                    </ul>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {/* ── ALIEXPRESS BUYER SIGNALS SUB-SECTION (Task #25) ─────────────────
          Surfaces the AE rating + recent_sales + buzz_score data that the
          sentiment scorer uses as a fallback when Western public-social is
          silent. Without this section, products with sentiment_score=70
          (from AE buyer fallback) looked "fake-high" because the Social
          Evidence panel showed empty Twitter/Amazon panes. Now the AE
          evidence is visible alongside Western evidence — the score has
          a visible backing. */}
      {(() => {
        // Read AE signals from product.data_sources or top-level fields.
        const dataSources = product?.data_sources || {};
        const aeSignals = dataSources.aliexpress_signals || dataSources.aliexpress || {};
        const rating = aeSignals.rating_stars || product.aliexpress_rating;
        const ratingPct = aeSignals.rating_pct;
        const recentSales = aeSignals.recent_sales || product.sales_count || aeSignals.orders;
        const buzz = aeSignals.buzz_score || product.aliexpress_buzz;
        const foundReal = aeSignals.found_real_rating || (rating && rating > 0);

        // Don't render the section if we have nothing to show.
        if (!rating && !recentSales && !buzz) return null;

        // Strength classifier matches the qualitative agent's logic.
        let strength = 'POOR';
        let strengthTone = 'red';
        if (rating >= 4.7 && recentSales >= 1000) { strength = 'STRONG'; strengthTone = 'emerald'; }
        else if (rating >= 4.5 && recentSales >= 200) { strength = 'MODERATE'; strengthTone = 'cyan'; }
        else if (rating >= 4.3) { strength = 'WEAK'; strengthTone = 'yellow'; }

        const toneClasses = {
          emerald: 'bg-emerald-500/10 text-emerald-300 border-emerald-500/30',
          cyan: 'bg-cyan-500/10 text-cyan-300 border-cyan-500/30',
          yellow: 'bg-yellow-500/10 text-yellow-300 border-yellow-500/30',
          red: 'bg-red-500/10 text-red-300 border-red-500/30',
        };

        return (
          <>
            <div className="border-t border-white/10" />
            <div>
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <div className="w-6 h-6 rounded-md bg-orange-500/30 flex items-center justify-center text-[10px] font-bold text-white">
                    A
                  </div>
                  <span className="text-white/80 text-sm font-medium">AliExpress Buyer Signals</span>
                  <span
                    className={`text-[10px] px-1.5 py-0.5 rounded font-medium border ${toneClasses[strengthTone]}`}
                    title="Strength of the AE buyer-side signal. STRONG = high rating + high recent sales. WEAK = numbers exist but below the 'real positive' bar."
                  >
                    {strength}
                  </span>
                </div>
              </div>
              <div className="grid grid-cols-3 gap-2 text-xs">
                <div className="bg-white/5 rounded-lg px-2.5 py-1.5">
                  <div className="text-white/40 text-[10px]">Rating</div>
                  <div className="text-white/90 font-semibold">
                    {rating ? `${Number(rating).toFixed(2)}★` : '—'}
                  </div>
                </div>
                <div className="bg-white/5 rounded-lg px-2.5 py-1.5">
                  <div className="text-white/40 text-[10px]">Recent sales</div>
                  <div className="text-white/90 font-semibold">
                    {recentSales ? Number(recentSales).toLocaleString() : '—'}
                  </div>
                </div>
                <div className="bg-white/5 rounded-lg px-2.5 py-1.5">
                  <div className="text-white/40 text-[10px]">Buzz score</div>
                  <div className="text-white/90 font-semibold">
                    {buzz ? `${Math.round(Number(buzz))}/100` : '—'}
                  </div>
                </div>
              </div>
              {ratingPct ? (
                <p className="text-white/40 text-[10px] mt-2 italic">
                  {Number(ratingPct).toFixed(1)}% of reviews are 4-5★.
                  {' '}AE platform-wide baseline is ~4.5★ — treat &lt;4.3★ as weak,
                  &gt;4.7★ as a real positive.
                </p>
              ) : (
                <p className="text-white/40 text-[10px] mt-2 italic">
                  Numeric buyer signal only (no verbatim review text in this view).
                </p>
              )}
            </div>
          </>
        );
      })()}

      {/* Reddit sub-section — REMOVED (May 2026 architecture pivot).
          Reddit was a lagging indicator that didn't fire on niche dropship
          products before they went viral. Replaced by Meta Ad Library +
          TikTok Shop bestsellers as leading indicators. The data shape is
          still propagated through the API for backwards compat with stored
          products, but we don't render it in the UI anymore. */}
      {false && (
      <>
      {/* Divider */}
      <div className="border-t border-white/10" />

      {/* ── REDDIT SUB-SECTION (LEGACY, HIDDEN) ─────────────────────────── */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-md bg-orange-600/80 flex items-center justify-center text-[10px] font-bold text-white">
              R
            </div>
            <span className="text-white/80 text-sm font-medium">Reddit</span>
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-green-500/10 text-green-300/80 border border-green-500/20" title="Real posts from Reddit's public search API. URLs are live and clickable.">
              verifiable
            </span>
          </div>
          {redditHasRealData && (
            <span className="text-[10px] text-white/40">
              {reddit.length} match{reddit.length === 1 ? '' : 'es'}
            </span>
          )}
        </div>

        {!redditChecked && (
          <p className="text-white/40 text-xs italic pl-8">Not yet checked.</p>
        )}

        {redditChecked && !redditHasRealData && (
          <div className="ml-8 text-xs text-white/50 bg-white/5 border border-white/10 rounded-lg px-3 py-2">
            <span className="font-medium">No Reddit matches found.</span>
            {redditSubsSearched.length > 0 && (
              <span className="block text-[10px] text-white/40 mt-0.5">
                Searched: {redditSubsSearched.map(s => `r/${s}`).join(', ')}
              </span>
            )}
          </div>
        )}

        {redditHasRealData && (
          <div className="ml-8 space-y-2">
            {/* Summary: how many product matches vs category matches */}
            {(() => {
              const productCount = reddit.filter(p => p.match_type === 'product').length;
              const categoryCount = reddit.length - productCount;
              if (productCount > 0 || categoryCount > 0) {
                return (
                  <div className="flex gap-1.5 text-[10px] mb-1">
                    {productCount > 0 && (
                      <span className="px-2 py-0.5 rounded bg-green-500/10 border border-green-500/30 text-green-300" title="Posts actually discussing this product type">
                        {productCount} product match{productCount === 1 ? '' : 'es'}
                      </span>
                    )}
                    {categoryCount > 0 && (
                      <span className="px-2 py-0.5 rounded bg-blue-500/10 border border-blue-500/30 text-blue-300" title="Posts about the category (capabilities/features), not this product specifically">
                        {categoryCount} category match{categoryCount === 1 ? '' : 'es'}
                      </span>
                    )}
                  </div>
                );
              }
              return null;
            })()}

            {reddit.slice(0, 5).map((post, i) => {
              const isProduct = post.match_type === 'product';
              const matchBorder = isProduct
                ? 'border-green-500/20 hover:border-green-500/50'
                : 'border-blue-500/20 hover:border-blue-500/40';
              return (
                <a
                  key={i}
                  href={post.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={`block bg-white/5 hover:bg-white/10 border ${matchBorder} rounded-lg px-3 py-2.5 transition-all group`}
                >
                  <div className="flex items-start justify-between gap-2 mb-1">
                    <div className="flex-1 min-w-0">
                      {/* Match type chip - green for product-specific, blue for category */}
                      {post.match_type && (
                        <span
                          className={`inline-block text-[9px] px-1.5 py-0.5 rounded mr-1.5 mb-0.5 ${
                            isProduct
                              ? 'bg-green-500/15 text-green-300 border border-green-500/30'
                              : 'bg-blue-500/10 text-blue-300/90 border border-blue-500/30'
                          }`}
                          title={isProduct
                            ? 'Match on product-type keywords - likely a real product discussion'
                            : 'Match on capability/feature keywords only - likely category discussion'}
                        >
                          {isProduct ? 'product' : 'category'}
                        </span>
                      )}
                      <span className="text-sm text-white/90 group-hover:text-orange-200 leading-snug line-clamp-2">
                        {post.title}
                      </span>
                    </div>
                    <ExternalLink className="w-3.5 h-3.5 text-white/30 group-hover:text-orange-300 flex-shrink-0 mt-0.5" />
                  </div>

                  <div className="flex items-center gap-3 text-[10px] text-white/50">
                    <span className="font-medium text-orange-300/80">r/{post.subreddit}</span>
                    <span className="flex items-center gap-0.5">
                      <TrendingUp className="w-2.5 h-2.5" />
                      {(post.score ?? 0).toLocaleString()}
                    </span>
                    <span className="flex items-center gap-0.5">
                      <MessageSquare className="w-2.5 h-2.5" />
                      {(post.num_comments ?? 0).toLocaleString()}
                    </span>
                    {post.created_utc && (
                      <span>{formatRedditDate(post.created_utc)}</span>
                    )}
                  </div>

                  {Array.isArray(post.matched_on) && post.matched_on.length > 0 && (
                    <div className="mt-1.5 flex flex-wrap gap-1">
                      {post.matched_on.map((tok, idx) => (
                        <span key={idx} className="text-[9px] px-1.5 py-0.5 rounded bg-orange-500/10 text-orange-300/80 border border-orange-500/20">
                          {tok}
                        </span>
                      ))}
                    </div>
                  )}

                  {post.selftext_excerpt && (
                    <p className="text-[10px] text-white/50 mt-1.5 italic line-clamp-2">
                      "{post.selftext_excerpt}"
                    </p>
                  )}
                </a>
              );
            })}
          </div>
        )}
      </div>
      </>
      )}
    </div>
  );
}

// ============================================================================
// COMPONENT: Product Detail Panel - Auto-analysis, image toggle
// ============================================================================
function ProductDetailPanel({ product, onClose, onDeploy, onUpdateProduct, onEnhance }) {
  const toast = useToast();
  const [caption, setCaption] = useState('');
  const [deploying, setDeploying] = useState(false);
  const [copied, setCopied] = useState(false);
  const [generatingCaption, setGeneratingCaption] = useState(false);
  const [generatingAnalysis, setGeneratingAnalysis] = useState(false);
  const [generatingImage, setGeneratingImage] = useState(false);
  const [aiAnalysis, setAiAnalysis] = useState(null);
  const [currentAiImageUrl, setCurrentAiImageUrl] = useState(product.ai_image_url);
  const [enhancedImages, setEnhancedImages] = useState(product.enhanced_images || []);
  const [analysisError, setAnalysisError] = useState(null);
  // Task #34: track WHICH source produced the analysis + Claude error
  // details so the UI can show "Claude unavailable — try again" banners
  // instead of swallowing all failures behind a generic toast.
  const [analysisSource, setAnalysisSource] = useState(null);  // 'claude' | 'fallback' | null
  const [claudeError, setClaudeError] = useState(null);  // { kind, detail, retryable } | null

  // Task #38 — marketing angle generator state. Only relevant when the
  // product is saturated (score ≥ 0.6). `angles` is an array of dicts
  // with title/description/target_audience/pain_point/benefits/cta/etc.
  const [marketingAngles, setMarketingAngles] = useState([]);
  const [generatingAngles, setGeneratingAngles] = useState(false);
  const [anglesError, setAnglesError] = useState(null);

  // AUTO-GENERATE ANALYSIS ON MOUNT
  useEffect(() => {
    generateSEOCaption();
    generateAIAnalysis(); // Auto-generate analysis when panel opens
  }, [product.id]);

  // Task #38 — async handler for the "Generate Marketing Angles" button.
  // We only show the button when the product is saturated, so by the
  // time this runs we already know the backend will accept it (no need
  // to set force=true). The handler is local to the panel so error
  // state doesn't leak across product cards.
  const generateMarketingAngles = async ({ force = false } = {}) => {
    setGeneratingAngles(true);
    setAnglesError(null);
    try {
      const result = await api.generateMarketingAngles(product, {
        numAngles: 3,
        force,
      });
      if (result?.success && Array.isArray(result.angles)) {
        setMarketingAngles(result.angles);
      } else {
        setAnglesError(
          result?.message || result?.error || 'Could not generate marketing angles'
        );
        setMarketingAngles([]);
      }
    } catch (error) {
      console.error('[PRODUCT-DETAIL] marketing angles error:', error);
      setAnglesError(error?.message || 'Network error');
      setMarketingAngles([]);
    } finally {
      setGeneratingAngles(false);
    }
  };
  
  // Load cached images ONLY (no auto-enhancement to avoid spending money)
  useEffect(() => {
    const loadCachedImages = async () => {
      // Skip if we already have enhanced images
      if (enhancedImages.length > 0 || currentAiImageUrl) {
        // console.log('[PRODUCT-DETAIL] Already has enhanced images, skipping cache check');
        return;
      }

      // Skip if no product images
      const allImages = product.all_images || [product.image_url].filter(Boolean);
      if (allImages.length === 0) {
        return;
      }

      try {
        // Check cache for this product by product ID
        const cached = await api.getCachedEnhancedImages(product.id);
        if (cached.success && cached.cached && cached.enhanced_urls?.length > 0) {
          // console.log('[PRODUCT-DETAIL] ✅ Found cached images via product_id (FREE):', cached.enhanced_urls.length);
          setEnhancedImages(cached.enhanced_urls);
          setCurrentAiImageUrl(cached.primary_enhanced_url || cached.enhanced_urls[0]);
          if (onUpdateProduct) {
            onUpdateProduct({
              ...product,
              ai_image_url: cached.primary_enhanced_url || cached.enhanced_urls[0],
              enhanced_images: cached.enhanced_urls
            });
          }
          return;
        }

        // Check file-based cache by image URLs
        const cacheCheck = await api.checkImageCache(allImages);
        if (cacheCheck.cached_count > 0) {
          const cachedUrls = Object.values(cacheCheck.cached || {});
          // console.log('[PRODUCT-DETAIL] ✅ Found file-cached images (FREE):', cachedUrls.length);
          setEnhancedImages(cachedUrls);
          setCurrentAiImageUrl(cachedUrls[0]);
          if (onUpdateProduct) {
            onUpdateProduct({
              ...product,
              ai_image_url: cachedUrls[0],
              enhanced_images: cachedUrls
            });
          }
          return;
        }

        // Last resort: Try smart cache recovery (checks multiple hash variants)
        // console.log('[PRODUCT-DETAIL] 🔍 Trying smart cache recovery...');
        const recovery = await api.smartCacheRecovery(allImages, product.id);
        if (recovery.success && recovery.matches_found > 0) {
          const recoveredUrls = recovery.matches.map(m => m.enhanced_url);
          // console.log('[PRODUCT-DETAIL] ✅ Smart recovery found cached images (FREE):', recoveredUrls.length);
          setEnhancedImages(recoveredUrls);
          setCurrentAiImageUrl(recoveredUrls[0]);
          if (onUpdateProduct) {
            onUpdateProduct({
              ...product,
              ai_image_url: recoveredUrls[0],
              enhanced_images: recoveredUrls
            });
          }
          return;
        }

        // No cached images found - user can manually enhance if they want
        // console.log('[PRODUCT-DETAIL] ⚠️ No cached images found. Click "Enhance" to generate (~$0.06/image)');

      } catch (e) {
        // console.log('[PRODUCT-DETAIL] Cache check failed:', e.message);
      }
    };

    loadCachedImages();
  }, [product.id]);

  // Generate AI image using Stability AI background removal (AUTHENTICATED + CACHED)
  const generateAiImage = async (imageUrlOverride = null) => {
    setGeneratingImage(true);
    try {
      // Use the authenticated API method with product_id for caching
      const targetImageUrl = imageUrlOverride || product.image_url;
      const data = await api.enhanceImage(
        targetImageUrl,
        product.niche || 'smart_home',
        null, // backgroundStyle
        product.id // product_id for caching
      );

      if (data.success && data.enhanced_image_url) {
        setCurrentAiImageUrl(data.enhanced_image_url);
        // Add to enhanced images array (replace if re-enhancing same image)
        setEnhancedImages(prev => {
          if (prev.length === 0) return [data.enhanced_image_url];
          // Replace first image if re-enhancing main image
          return [data.enhanced_image_url, ...prev.slice(1)];
        });
        // Update parent if callback provided
        if (onUpdateProduct) {
          onUpdateProduct({
            ...product,
            ai_image_url: data.enhanced_image_url,
            enhanced_images: [data.enhanced_image_url, ...(product.enhanced_images || []).slice(1)]
          });
        }
        // Show if result was from cache (FREE)
        if (data.cached) {
          // console.log('Image was already enhanced (cached - FREE)');
        }
      } else {
        toast.error('Image enhancement failed. ' + (data.error || 'Check if STABILITY_API_KEY is configured.'));
      }
    } catch (error) {
      console.error('Image enhancement failed:', error);
      toast.error('Image enhancement failed: ' + (error.message || 'Unknown error'));
    } finally {
      setGeneratingImage(false);
    }
  };

  // Enhance ALL product images in batch
  const enhanceAllImages = async () => {
    if (!product.all_images || product.all_images.length === 0) {
      toast.info('No images available to enhance');
      return;
    }

    setGeneratingImage(true);
    try {
      const imagesToEnhance = product.all_images.map((url, idx) => ({
        url: url,
        id: `${product.id}_img_${idx}`,
        title: product.title,
        niche: product.niche
      }));

      const result = await api.enhanceBatchImages(imagesToEnhance, product.niche || 'smart_home');

      if (result.successful > 0) {
        // Get all successful enhanced image URLs
        const allEnhancedUrls = result.results
          .filter(r => r.success)
          .map(r => r.enhanced_image_url);

        // Update local state to show all enhanced images
        setEnhancedImages(allEnhancedUrls);
        setCurrentAiImageUrl(allEnhancedUrls[0]); // First one as main

        // Update parent with all enhanced images
        if (onUpdateProduct) {
          onUpdateProduct({
            ...product,
            ai_image_url: allEnhancedUrls[0],
            enhanced_images: allEnhancedUrls
          });
        }

        toast.success(`Enhanced ${result.successful} of ${result.total} images (~$${(result.successful * 0.06).toFixed(2)} cost)`);
      } else {
        toast.error('All image enhancements failed. ' + (result.results[0]?.error || 'Unknown error'));
      }
    } catch (error) {
      console.error('Batch enhancement failed:', error);
      toast.error('Batch enhancement failed: ' + (error.message || 'Unknown error'));
    } finally {
      setGeneratingImage(false);
    }
  };

  // STABLE score breakdown - computed once, memoized
  // Honest scoring (2026-04-25): demand_score, trend_score, AND sentiment_score
  // can ALL be null when the backend couldn't find real signal. Each gets the
  // "No data" striped bar treatment instead of a fake number.
  const scoreBreakdown = useMemo(() => [
    {
      key: 'demand_score',
      label: 'Demand',
      icon: TrendingUp,
      color: 'text-green-400',
      value: product.demand_score,
      unavailable: product.demand_score === null || product.demand_score === undefined,
      note: (product.demand_score === null || product.demand_score === undefined)
        ? 'No order, review, or engagement data yet.'
        : null,
    },
    {
      key: 'trend_score',
      label: 'Trend',
      icon: Zap,
      color: 'text-cyan-400',
      value: product.trend_score,
      unavailable: product.trend_score === null || product.trend_score === undefined,
      // Pass the source through so the renderer can show an AE badge.
      // trend_source is set by the backend in product_discovery.py when
      // AE-velocity fallback fires.
      source: product.trend_source,
      note: (() => {
        if (product.trend_score === null || product.trend_score === undefined) {
          return 'No Google Trends, TikTok, or viral indicator data.';
        }
        const src = product.trend_source;
        if (src === 'aliexpress_velocity_strong') {
          return 'Based on AliExpress velocity (high buzz + recent sales). No Western trend signal yet.';
        }
        if (src === 'aliexpress_velocity_weak') {
          return 'Based on AliExpress recent sales only. Weak signal — Western trend data absent.';
        }
        return null;
      })(),
    },
    {
      key: 'sentiment_score',
      label: 'Sentiment',
      icon: MessageSquare,
      color: 'text-blue-400',
      value: product.sentiment_score,
      estimated: false,
      unavailable: product.sentiment_score === null || product.sentiment_score === undefined,
      // sentiment_source is set by the backend's sentiment composite
      // (sentiment_composite.py) — currently only emitted as
      // primary_source name like 'aliexpress_buyer'. We map that to the
      // AE badge here so users see WHERE the sentiment score came from.
      source: (() => {
        const primary = product.sentiment_source;
        if (primary === 'aliexpress_buyer') return 'aliexpress_buyer_strong';
        return primary;
      })(),
      note: (() => {
        if (product.sentiment_score === null || product.sentiment_score === undefined) {
          return product.sentiment_weight_redistributed
            ? 'No social signal found. Weight redistributed.'
            : null;
        }
        if (product.sentiment_source === 'aliexpress_buyer') {
          return 'Based on AliExpress buyer rating + sales volume. No Western social signal found.';
        }
        return null;
      })(),
    },
    {
      key: 'viral_score',
      label: 'Viral Potential',
      icon: Sparkles,
      color: 'text-pink-400',
      value: product.viral_score,
      estimated: product.viral_score === 50,
      // Treat default 50 ("Est.") as effectively unavailable — show "No
      // TikTok / viral data yet" instead of a fake bar at 50. Was: bar
      // rendered at 50 with a tiny "(Est.)" tag that users missed.
      unavailable: product.viral_score === null || product.viral_score === undefined || product.viral_score === 50,
      note: (product.viral_score === 50 || product.viral_score === null || product.viral_score === undefined)
        ? 'No TikTok / Pinterest viral signal yet.'
        : null,
    },
    {
      key: 'profit_score',
      label: 'Profit Margin',
      icon: DollarSign,
      color: 'text-purple-400',
      value: product.profit_score,
      estimated: false,
      unavailable: product.profit_score === null || product.profit_score === undefined,
    },
  ], [
    product.demand_score,
    product.trend_score,
    product.trend_source,
    product.sentiment_score,
    product.sentiment_source,
    product.sentiment_weight_redistributed,
    product.viral_score,
    product.profit_score,
  ]);

  const generateSEOCaption = async () => {
    setGeneratingCaption(true);
    try {
      // Pass actual product tags so Claude has product-specific signals,
      // not just the category label. See api.generateCaption + the
      // anti-template prompt in product_analysis_routes.py.
      const response = await api.generateCaption(
        product.title,
        product.niche,
        product.suggested_price,
        product.tags
      );
      if (response.success && response.caption) {
        setCaption(response.caption);
      } else {
        setCaption(createProfessionalCaption(product));
      }
    } catch (error) {
      console.error('Caption generation failed:', error);
      setCaption(createProfessionalCaption(product));
    } finally {
      setGeneratingCaption(false);
    }
  };

  // PROFESSIONAL caption template - NO EMOJIS, NO HASHTAGS
  const createProfessionalCaption = (p) => {
    const cleanTitle = p.title
      .replace(/\b(hot sale|new|2024|2025|premium|quality|best|cheap)\b/gi, '')
      .replace(/\s+/g, ' ')
      .trim();
    const nicheFormatted = p.niche.replace(/_/g, ' ');
    
    return `${cleanTitle}

Transform your ${nicheFormatted} experience with this thoughtfully designed essential. Quality construction ensures reliability while the modern design complements any space.

Free shipping on orders over $50. 30-day hassle-free returns.`;
  };

  const generateAIAnalysis = async (forceRefresh = false) => {
    setGeneratingAnalysis(true);
    setAnalysisError(null);
    setClaudeError(null);

    try {
      // Routes through authService.post() so the JWT is attached.
      // Backend endpoint /api/oi/analyze-product requires auth (Depends(get_current_user)).
      // ``forceRefresh`` is True when the user explicitly clicked the
      // Refresh button — bypasses the 15-min server-side cache that was
      // making re-clicks return identical analysis.
      const data = await api.analyzeProduct(product, forceRefresh === true);

      if (!data || data.success === false) {
        throw new Error(data?.error || 'Analysis failed');
      }

      // Task #34: track source + Claude error context.
      // Backend now returns source='claude' (full AI) or source='fallback'
      // (rule-based) with optional claude_error{kind,detail,retryable} when
      // Claude was attempted and failed. UI surfaces this so user knows
      // whether retry is worth it.
      setAnalysisSource(data.source || null);
      setClaudeError(data.claude_error || null);

      if (data.success && data.analysis) {
        // Format the analysis nicely
        const a = data.analysis;
        const formatted = `VERDICT: ${a.verdict || 'N/A'} (${a.confidence || 0}% confidence)

SUMMARY
${a.summary || 'No summary available.'}

STRENGTHS
${(a.strengths || []).map(s => `• ${s}`).join('\n') || '• No specific strengths identified'}

RISKS
${(a.risks || []).map(r => `• ${r}`).join('\n') || '• Standard market risks apply'}

TARGET AUDIENCE
${a.target_audience || 'General consumers'}

MARKETING ANGLES
${(a.marketing_angles || []).map(m => `• ${m}`).join('\n') || '• Focus on product benefits'}

AD SPEND RECOMMENDATION
${a.ad_spend_recommendation || 'Start with $5-10/day'}

PRICE STRATEGY
${a.price_strategy || 'Current pricing appears competitive'}

COMPETITION
${a.competition_assessment || 'Moderate competition in this niche'}

SEASONAL FACTORS
${a.seasonal_factors || 'Year-round demand expected'}`;
        
        setAiAnalysis(formatted);
      } else {
        setAnalysisError('Analysis returned empty. API may not have Claude key configured.');
      }
    } catch (error) {
      console.error('AI Analysis failed:', error);
      setAnalysisError(`Analysis failed: ${error.message}. Check API connection.`);
    } finally {
      setGeneratingAnalysis(false);
    }
  };

  const copyCaption = () => {
    navigator.clipboard.writeText(caption);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDeploy = async () => {
    if (product.is_mock) {
      toast.info('Cannot deploy demo products. Connect APIs for real products.');
      return;
    }
    setDeploying(true);
    try {
      await onDeploy(product, caption);
      toast.success(`${product.title} deployed to Shopify!`);
      onClose();
    } catch (error) {
      toast.error('Deploy failed: ' + (error.message || 'Unknown error'));
    } finally {
      setDeploying(false);
    }
  };

  // Get data sources that are actually present
  const dataSources = product.data_sources || {};
  const activeSourceKeys = Object.keys(dataSources).filter(k => dataSources[k]?.available);

  return (
    <>
      {/* Backdrop */}
      <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40" onClick={onClose} />

      {/* Panel */}
      <div 
        className="fixed right-0 top-0 h-full w-full max-w-2xl bg-[#0a0a0f]/95 backdrop-blur-xl border-l border-white/10 z-50 overflow-y-auto"
        style={{ animation: 'slideIn 0.3s ease-out' }}
      >
        {/* Header */}
        <div className="sticky top-0 bg-[#0a0a0f]/90 backdrop-blur-xl border-b border-white/10 p-4 flex items-center justify-between z-10">
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <Package className="w-5 h-5 text-purple-400" />
            Product Details
          </h2>
          <button onClick={onClose} className="p-2 rounded-xl hover:bg-white/10 text-white/60 hover:text-white transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 space-y-6">
          {/* Image Gallery with Toggle */}
          <ImageGallery
            product={product}
            aiImageUrl={currentAiImageUrl}
            enhancedImages={enhancedImages}
            onRegenerateAi={() => generateAiImage()}
            regenerating={generatingImage}
          />
          
          {/* Enhance Image Buttons */}
          {product.image_url && (
            <div className="flex gap-3">
              {/* Single Image Enhancement */}
              <button
                onClick={() => generateAiImage()}
                disabled={generatingImage}
                className="flex-1 py-3 rounded-xl bg-gradient-to-r from-purple-500/20 to-cyan-500/20 border border-purple-500/30 text-white font-medium hover:from-purple-500/30 hover:to-cyan-500/30 flex items-center justify-center gap-2 transition-all disabled:opacity-50"
              >
                {generatingImage ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin" />
                    Enhancing...
                  </>
                ) : (
                  <>
                    <Wand2 className="w-5 h-5" />
                    Enhance Image
                    <span className="text-white/50 text-sm">(~$0.06)</span>
                  </>
                )}
              </button>

              {/* Batch Enhancement - show if multiple images available */}
              {product.all_images && product.all_images.length > 1 && (
                <button
                  onClick={enhanceAllImages}
                  disabled={generatingImage}
                  className="py-3 px-4 rounded-xl bg-cyan-500/20 border border-cyan-500/30 text-cyan-300 font-medium hover:bg-cyan-500/30 flex items-center justify-center gap-2 transition-all disabled:opacity-50"
                  title={`Enhance all ${product.all_images.length} images`}
                >
                  {generatingImage ? (
                    <Loader2 className="w-5 h-5 animate-spin" />
                  ) : (
                    <>
                      <ImageIcon className="w-5 h-5" />
                      All ({product.all_images.length})
                    </>
                  )}
                </button>
              )}
            </div>
          )}

          {/* Product Title + Oi Score */}
          <div className="backdrop-blur-xl bg-white/5 rounded-2xl border border-white/10 p-4">
            <h3 className="text-lg font-bold text-white mb-4">{product.title}</h3>
            
            {/* Estimated Scores Warning */}
            {product.scores_estimated && (
              <div className="mb-4 p-3 rounded-xl bg-yellow-500/10 border border-yellow-500/20 flex items-center gap-2">
                <Info className="w-4 h-4 text-yellow-400 flex-shrink-0" />
                <p className="text-yellow-200 text-sm">
                  Scores are estimated due to limited data. Connect more APIs for accurate metrics.
                </p>
              </div>
            )}
            
            {/* MAIN Oi Score */}
            <div className={`p-4 rounded-xl bg-gradient-to-br ${getScoreBgColor(product.oi_score)} border`}>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="p-3 rounded-xl bg-black/30">
                    <Brain className="w-6 h-6 text-purple-400" />
                  </div>
                  <div>
                    <p className="text-white/60 text-sm">Oi Score {product.scores_estimated && <span className="text-yellow-400">(Est.)</span>}</p>
                    <p className={`text-3xl font-bold ${getScoreColor(product.oi_score)}`}>{product.oi_score}</p>
                  </div>
                </div>
                <div className="text-right">
                  <p className="text-white/40 text-xs">out of 100</p>
                  <p className={`text-sm font-medium ${getScoreColor(product.oi_score)}`}>
                    {product.oi_score >= 80 ? 'Excellent' : product.oi_score >= 60 ? 'Good' : product.oi_score >= 40 ? 'Fair' : 'Poor'}
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* Oi Score Breakdown */}
          <div className="backdrop-blur-xl bg-white/5 rounded-2xl border border-white/10 p-4">
            <h4 className="text-white font-semibold mb-4 flex items-center gap-2">
              <Brain className="w-4 h-4 text-purple-400" />
              Score Breakdown
            </h4>
            
            <div className="space-y-3">
              {scoreBreakdown.map((item) => {
                const Icon = item.icon;

                // POST-FIX #15: honest "no data" state for sentiment when backend
                // couldn't find real social signal. Don't show a 0 bar - show
                // "No data" so the user knows we didn't fake a number.
                if (item.unavailable) {
                  return (
                    <div key={item.key} className="flex items-center gap-3 opacity-70">
                      <div className="p-2 rounded-lg bg-white/5">
                        <Icon className={`w-4 h-4 ${item.color}`} />
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-white/70 text-sm">
                            {item.label}
                            <span className="text-white/40 text-xs ml-2">(No social data yet)</span>
                          </span>
                          <span className="text-white/40 text-xs italic">N/A</span>
                        </div>
                        <div className="h-2 bg-white/10 rounded-full overflow-hidden">
                          {/* Striped "data unavailable" bar */}
                          <div
                            className="h-full w-full opacity-40"
                            style={{
                              background: 'repeating-linear-gradient(45deg, rgba(255,255,255,0.15) 0 6px, transparent 6px 12px)'
                            }}
                          />
                        </div>
                        {item.note && (
                          <p className="text-white/40 text-[10px] mt-1 italic">{item.note}</p>
                        )}
                      </div>
                    </div>
                  );
                }

                const value = Math.min(100, Math.max(0, item.value || 0));
                // Source badge for AE-fallback scores. Without this, scores
                // like Trend=72 or Sentiment=70 looked like they came from
                // Western signals (which were empty) — making users think
                // the scores were fake. The badge tells the truth: this
                // came from AE buyer data, weaker signal than Western.
                const aeBadge = (() => {
                  const src = item.source;
                  if (!src) return null;
                  if (src === 'aliexpress_velocity_strong' || src === 'aliexpress_buyer_strong') {
                    return { label: 'AE', tone: 'amber', tip: 'From AliExpress buyer behavior (strong)' };
                  }
                  if (src === 'aliexpress_velocity_weak' || src === 'aliexpress_buyer_weak') {
                    return { label: 'AE', tone: 'yellow', tip: 'From AliExpress buyer behavior (weak)' };
                  }
                  return null;
                })();
                return (
                  <div key={item.key} className="flex items-center gap-3">
                    <div className="p-2 rounded-lg bg-white/5">
                      <Icon className={`w-4 h-4 ${item.color}`} />
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-white/70 text-sm flex items-center gap-1.5">
                          {item.label}
                          {item.estimated && <span className="text-yellow-400 text-xs ml-1">(Est.)</span>}
                          {aeBadge && (
                            <span
                              className={`text-[9px] px-1.5 py-0.5 rounded font-semibold tracking-wider ${
                                aeBadge.tone === 'amber'
                                  ? 'bg-amber-500/15 text-amber-300/90 border border-amber-500/30'
                                  : 'bg-yellow-500/10 text-yellow-300/80 border border-yellow-500/20'
                              }`}
                              title={aeBadge.tip}
                            >
                              {aeBadge.label}
                            </span>
                          )}
                        </span>
                        <span className={`font-bold ${item.color}`}>{value}</span>
                      </div>
                      <div className="h-2 bg-white/10 rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full bg-gradient-to-r ${
                            value >= 80 ? 'from-green-500 to-green-400' :
                            value >= 60 ? 'from-cyan-500 to-cyan-400' :
                            value >= 40 ? 'from-yellow-500 to-yellow-400' :
                            'from-red-500 to-red-400'
                          }`}
                          style={{ width: `${value}%` }}
                        />
                      </div>
                      {/* Note now renders on the has-value branch too. Before,
                          the note was only shown when the score was null —
                          which meant "Based on AliExpress velocity..." text
                          never appeared because the score was always present
                          when the AE fallback fired. Bug #26. */}
                      {item.note && (
                        <p className="text-white/40 text-[10px] mt-1 italic">{item.note}</p>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Quick Recommendation — honest tier-aware variant */}
            {(() => {
              // Honest scoring: when the backend says INSUFFICIENT_DATA, we
              // surface that explicitly with a neutral tone. No green
              // "Strong buy" badges on products we couldn't validate.
              const tier = product.tier;
              const confPct = product.data_confidence_pct;
              const isInsufficient = tier === 'INSUFFICIENT_DATA';
              const isStrong = !isInsufficient && product.oi_score >= 70;
              const isMod = !isInsufficient && !isStrong && product.oi_score >= 50;

              const containerCls = isInsufficient
                ? 'bg-white/5 border border-white/10'
                : isStrong
                  ? 'bg-green-500/10 border border-green-500/20'
                  : isMod
                    ? 'bg-yellow-500/10 border border-yellow-500/20'
                    : 'bg-red-500/10 border border-red-500/20';
              const textCls = isInsufficient
                ? 'text-white/70'
                : isStrong
                  ? 'text-green-300'
                  : isMod
                    ? 'text-yellow-300'
                    : 'text-red-300';

              return (
                <div className={`mt-4 p-3 rounded-xl ${containerCls}`}>
                  {isInsufficient && (
                    <p className="text-white/50 text-[11px] uppercase tracking-wider mb-1">
                      Insufficient data — {confPct ?? 0}% data coverage
                    </p>
                  )}
                  <p className={`text-sm font-medium ${textCls}`}>
                    {product.recommendation || (
                      isStrong ? 'HIGH OPPORTUNITY: Strong buy signal based on demand and trend data' :
                      isMod    ? 'MODERATE: Worth testing with a small budget' :
                                 'LOW POTENTIAL: Consider skipping this product'
                    )}
                  </p>
                  {!isInsufficient && typeof confPct === 'number' && confPct < 100 && (
                    <p className="text-white/40 text-[11px] mt-1">
                      Data confidence: {confPct}%
                      {Array.isArray(product.missing_components) && product.missing_components.length > 0 && (
                        <> · Missing: {product.missing_components.join(', ')}</>
                      )}
                    </p>
                  )}
                </div>
              );
            })()}
          </div>

          {/* AI Analysis Section - AUTO-LOADED */}
          <div className="backdrop-blur-xl bg-white/5 rounded-2xl border border-white/10 p-4">
            <div className="flex items-center justify-between mb-3">
              <h4 className="text-white font-semibold flex items-center gap-2">
                <Brain className="w-4 h-4 text-purple-400" />
                AI Analysis
                {generatingAnalysis && <Loader2 className="w-4 h-4 animate-spin text-purple-400" />}
              </h4>
              <button
                onClick={() => generateAIAnalysis(true)}
                disabled={generatingAnalysis}
                className="px-4 py-2 rounded-xl bg-gradient-to-r from-purple-600 to-cyan-600 text-white text-sm font-medium hover:opacity-90 disabled:opacity-50 flex items-center gap-2"
              >
                {generatingAnalysis ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Analyzing...
                  </>
                ) : (
                  <>
                    <RefreshCw className="w-4 h-4" />
                    Refresh
                  </>
                )}
              </button>
            </div>
            
            {generatingAnalysis && !aiAnalysis ? (
              <div className="p-8 text-center">
                <Loader2 className="w-8 h-8 animate-spin text-purple-400 mx-auto mb-3" />
                <p className="text-white/60 text-sm">Generating AI analysis...</p>
              </div>
            ) : aiAnalysis ? (
              <div className="space-y-2">
                {/* Task #34: surface WHEN the analysis came from the rule-
                    based fallback instead of Claude, with a retry button
                    when the failure was transient. Was: silent fallback
                    that users couldn't distinguish from the real Claude
                    output. */}
                {analysisSource === 'fallback' && claudeError && (
                  <div className="p-3 rounded-xl bg-yellow-500/10 border border-yellow-500/30 flex items-start gap-3">
                    <AlertCircle className="w-4 h-4 text-yellow-400 flex-shrink-0 mt-0.5" />
                    <div className="flex-1 min-w-0">
                      <p className="text-yellow-200 text-sm font-medium">
                        Rule-based analysis (Claude unavailable)
                      </p>
                      <p className="text-yellow-200/70 text-xs mt-0.5">
                        {claudeError.kind === 'timeout' && 'Claude timed out. Network or service slowness.'}
                        {claudeError.kind === 'rate_limit' && 'Claude rate-limited. Wait ~1 min then retry.'}
                        {claudeError.kind === 'auth' && 'Claude auth failed. Check ANTHROPIC_API_KEY in .env.'}
                        {claudeError.kind === 'network' && 'Network error reaching Claude.'}
                        {claudeError.kind === 'no_api_key' && 'ANTHROPIC_API_KEY not configured on backend.'}
                        {claudeError.kind === 'unknown' && (claudeError.detail || 'Unexpected error.')}
                      </p>
                    </div>
                    {claudeError.retryable && (
                      <button
                        onClick={() => generateAIAnalysis(true)}
                        disabled={generatingAnalysis}
                        className="text-xs px-3 py-1.5 rounded-md bg-yellow-500/20 hover:bg-yellow-500/30 border border-yellow-500/40 text-yellow-100 font-medium disabled:opacity-50 flex-shrink-0"
                      >
                        Try Claude again
                      </button>
                    )}
                  </div>
                )}
                <div className="p-4 rounded-xl bg-white/5 border border-white/10">
                  <pre className="text-white/80 text-sm whitespace-pre-wrap font-sans">{aiAnalysis}</pre>
                </div>
              </div>
            ) : analysisError ? (
              <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/20 flex items-start gap-3">
                <AlertCircle className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />
                <div className="flex-1">
                  <p className="text-red-300 text-sm">{analysisError}</p>
                </div>
                <button
                  onClick={() => generateAIAnalysis(true)}
                  disabled={generatingAnalysis}
                  className="text-xs px-3 py-1.5 rounded-md bg-red-500/20 hover:bg-red-500/30 border border-red-500/40 text-red-100 font-medium disabled:opacity-50 flex-shrink-0"
                >
                  Retry
                </button>
              </div>
            ) : (
              <p className="text-white/40 text-sm text-center py-8">
                Analysis loading...
              </p>
            )}
          </div>

          {/* Data Sources */}
          <div className="backdrop-blur-xl bg-white/5 rounded-2xl border border-white/10 p-4">
            <h4 className="text-white font-semibold mb-3 flex items-center gap-2">
              <Database className="w-4 h-4 text-purple-400" />
              Data Sources
            </h4>
            <div className="flex flex-wrap gap-2">
              {/* Show actual data sources */}
              {dataSources.aliexpress?.available && (
                <div className="px-3 py-2 rounded-lg border bg-green-500/10 border-green-500/30 text-green-300 text-xs flex items-center gap-2">
                  AliExpress <Check className="w-3 h-3" />
                </div>
              )}
              {dataSources.cj_dropshipping?.available && (
                <div className="px-3 py-2 rounded-lg border bg-green-500/10 border-green-500/30 text-green-300 text-xs flex items-center gap-2">
                  CJ Dropshipping <Check className="w-3 h-3" />
                </div>
              )}
              {dataSources.google_trends?.available && (
                <div className="px-3 py-2 rounded-lg border bg-green-500/10 border-green-500/30 text-green-300 text-xs flex items-center gap-2">
                  Google Trends <Check className="w-3 h-3" />
                </div>
              )}
              {dataSources.tiktok?.available && (
                <div className="px-3 py-2 rounded-lg border bg-green-500/10 border-green-500/30 text-green-300 text-xs flex items-center gap-2">
                  TikTok <Check className="w-3 h-3" />
                </div>
              )}
              {dataSources.amazon?.available && (
                <div className="px-3 py-2 rounded-lg border bg-green-500/10 border-green-500/30 text-green-300 text-xs flex items-center gap-2">
                  Amazon <Check className="w-3 h-3" />
                </div>
              )}
              {dataSources.x_twitter?.available && (
                <div className="px-3 py-2 rounded-lg border bg-green-500/10 border-green-500/30 text-green-300 text-xs flex items-center gap-2">
                  X/Twitter <Check className="w-3 h-3" />
                </div>
              )}
              {/* Reddit chip removed per architecture pivot — see SocialEvidencePanel comment */}
              {/* Show source from product if no detailed data_sources */}
              {activeSourceKeys.length === 0 && product.source && (
                <div className="px-3 py-2 rounded-lg border bg-blue-500/10 border-blue-500/30 text-blue-300 text-xs flex items-center gap-2">
                  {product.source.replace(/_/g, ' ')} <Check className="w-3 h-3" />
                </div>
              )}
              {activeSourceKeys.length === 0 && !product.source && (
                <div className="px-3 py-2 rounded-lg border bg-yellow-500/10 border-yellow-500/30 text-yellow-300 text-xs flex items-center gap-2">
                  <AlertTriangle className="w-3 h-3" /> Limited data sources
                </div>
              )}
            </div>
          </div>

          {/* ==========================================================
              SOCIAL EVIDENCE PANEL (Fix #15d)
              Honest display of what we actually found on Twitter/Reddit.
              Distinguishes between:
              - Real evidence (clickable URLs, sample tweets) → show it
              - "Searched, found nothing" → labeled empty state
              - "Not searched yet" → no section (don't show anything)
              ========================================================== */}
          <SocialEvidencePanel
            product={product}
            twitterEvidence={product.twitter_evidence}
            redditEvidence={product.reddit_evidence}
            amazonEvidence={product.amazon_evidence}
            aliexpressBuzz={product.aliexpress_buzz}
            sentimentSource={product.sentiment_source}
            dataSources={dataSources}
          />

          {/* Pricing Cards */}
          <div className="grid grid-cols-3 gap-4">
            <div className="p-4 rounded-xl bg-white/5 text-center">
              <p className="text-white/40 text-xs mb-1">Supplier Cost</p>
              <p className="text-white font-bold text-xl">${product.cost_price.toFixed(2)}</p>
            </div>
            <div className="p-4 rounded-xl bg-green-500/10 text-center">
              <p className="text-green-300/60 text-xs mb-1">Sell Price</p>
              <p className="text-green-400 font-bold text-xl">${product.suggested_price.toFixed(2)}</p>
            </div>
            <div className="p-4 rounded-xl bg-purple-500/10 text-center">
              <p className="text-purple-300/60 text-xs mb-1">Profit</p>
              <p className="text-purple-400 font-bold text-xl">+${product.profit.toFixed(2)}</p>
            </div>
          </div>

          {/* Supplier Link */}
          <div className="backdrop-blur-xl bg-white/5 rounded-2xl border border-white/10 p-4">
            <h4 className="text-white font-semibold mb-3 flex items-center gap-2">
              <Link2 className="w-4 h-4 text-purple-400" />
              Supplier Link
            </h4>
            {product.supplier_url ? (
              <a 
                href={product.supplier_url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center justify-between p-3 rounded-xl bg-orange-500/10 border border-orange-500/20 hover:bg-orange-500/20 transition-colors group"
              >
                <span className="text-orange-300">
                  View on {product.source === 'cj_dropshipping' ? 'CJ Dropshipping' : 'AliExpress'} (Affiliate)
                </span>
                <ExternalLink className="w-4 h-4 text-orange-300 group-hover:translate-x-1 transition-transform" />
              </a>
            ) : (
              <div className="p-3 rounded-xl bg-white/5 text-white/40 text-sm text-center">
                {product.is_mock ? 'Demo product - no supplier link' : 'Supplier link not available'}
              </div>
            )}
          </div>

          {/* Deploy Section */}
          <div className="backdrop-blur-xl bg-white/5 rounded-2xl border border-white/10 p-4">
            <h4 className="text-white font-semibold mb-3 flex items-center gap-2">
              <Rocket className="w-4 h-4 text-purple-400" />
              Deploy to Shopify
            </h4>
            
            {/* Caption */}
            <div className="mb-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-white/60 text-sm">Product Caption</span>
                <button
                  onClick={generateSEOCaption}
                  disabled={generatingCaption}
                  className="px-3 py-1 rounded-lg bg-purple-500/20 text-purple-300 text-xs hover:bg-purple-500/30 flex items-center gap-1"
                >
                  {generatingCaption ? (
                    <Loader2 className="w-3 h-3 animate-spin" />
                  ) : (
                    <Wand2 className="w-3 h-3" />
                  )}
                  Regenerate
                </button>
              </div>
              <div className="relative">
                <textarea
                  value={caption}
                  onChange={(e) => setCaption(e.target.value)}
                  className="w-full h-40 p-3 rounded-xl bg-white/5 border border-white/10 text-white placeholder-white/30 resize-none focus:outline-none focus:border-purple-500/50 text-sm"
                  placeholder={generatingCaption ? 'Generating caption...' : 'Product caption...'}
                />
                <button
                  onClick={copyCaption}
                  className="absolute top-2 right-2 p-2 rounded-lg bg-white/10 hover:bg-white/20 text-white/60 hover:text-white"
                >
                  {copied ? <Check className="w-4 h-4 text-green-400" /> : <Copy className="w-4 h-4" />}
                </button>
              </div>
            </div>

            {/* Task #38 — Marketing Angles. Shown when the saturation
                model rates this product ≥ 0.6 (i.e. crowded enough that
                the obvious positioning has competitors). Hidden for
                low-saturation products since their natural angle wins.
                A small "Generate anyway" link is provided for users who
                want angles regardless. */}
            {(() => {
              const sat = typeof product.saturation_score === 'number'
                ? product.saturation_score
                : null;
              const isSaturated = sat !== null && sat >= 0.6;
              if (!isSaturated && marketingAngles.length === 0 && !anglesError && !generatingAngles) {
                // Low-sat products get a quiet override link, not a full panel
                return (
                  <button
                    onClick={() => generateMarketingAngles({ force: true })}
                    className="text-xs text-white/40 hover:text-purple-300 text-left"
                  >
                    Generate marketing angles anyway →
                  </button>
                );
              }
              return (
                <div className="rounded-xl border border-amber-500/30 bg-amber-500/5 p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <AlertCircle className="w-4 h-4 text-amber-400" />
                      <span className="font-semibold text-amber-200 text-sm">
                        {isSaturated
                          ? `Saturated market${sat !== null ? ` (${Math.round(sat * 100)}% crowded)` : ''}`
                          : 'Marketing Angles'}
                      </span>
                    </div>
                    {marketingAngles.length === 0 && !generatingAngles && (
                      <button
                        onClick={() => generateMarketingAngles({ force: !isSaturated })}
                        className="px-3 py-1 rounded-lg bg-amber-500/20 text-amber-200 text-xs hover:bg-amber-500/30 flex items-center gap-1 font-medium"
                      >
                        <Sparkles className="w-3 h-3" />
                        Generate Angles
                      </button>
                    )}
                    {marketingAngles.length > 0 && (
                      <button
                        onClick={() => generateMarketingAngles({ force: !isSaturated })}
                        disabled={generatingAngles}
                        className="px-3 py-1 rounded-lg bg-white/10 text-white/70 text-xs hover:bg-white/20 flex items-center gap-1"
                      >
                        {generatingAngles ? (
                          <Loader2 className="w-3 h-3 animate-spin" />
                        ) : (
                          <RefreshCw className="w-3 h-3" />
                        )}
                        Regenerate
                      </button>
                    )}
                  </div>

                  {isSaturated && marketingAngles.length === 0 && !generatingAngles && (
                    <p className="text-xs text-white/60">
                      Many other dropshippers are already selling this. Claude can
                      suggest alternative positioning so you don't compete head-on.
                    </p>
                  )}

                  {generatingAngles && (
                    <div className="flex items-center gap-2 text-amber-200/80 text-sm">
                      <Loader2 className="w-4 h-4 animate-spin" />
                      Generating differentiated angles...
                    </div>
                  )}

                  {anglesError && !generatingAngles && (
                    <div className="text-xs text-red-300/90 bg-red-500/10 border border-red-500/30 rounded-lg p-2">
                      {anglesError}
                    </div>
                  )}

                  {/* Render generated angles as horizontal cards. Each card
                      surfaces the angle name, headline, target audience,
                      pain-point, and CTA — enough to drive a campaign brief. */}
                  {marketingAngles.length > 0 && (
                    <div className="space-y-3">
                      {marketingAngles.map((a, idx) => (
                        <div
                          key={`${a.angle}-${idx}`}
                          className="rounded-lg bg-white/5 border border-white/10 p-3 space-y-2"
                        >
                          <div className="flex items-start justify-between gap-2">
                            <div className="flex-1 min-w-0">
                              <div className="text-[10px] uppercase tracking-wider text-amber-300/80 font-semibold">
                                {(a.angle || '').replace(/_/g, ' ')}
                              </div>
                              <div className="text-sm font-semibold text-white">
                                {a.title}
                              </div>
                            </div>
                          </div>

                          {a.target_audience && (
                            <div className="text-xs text-white/70">
                              <span className="text-white/50">Audience:</span>{' '}
                              {a.target_audience}
                            </div>
                          )}
                          {a.pain_point && (
                            <div className="text-xs text-white/70">
                              <span className="text-white/50">Pain point:</span>{' '}
                              {a.pain_point}
                            </div>
                          )}

                          {Array.isArray(a.benefits) && a.benefits.length > 0 && (
                            <ul className="text-xs text-white/70 list-disc pl-4 space-y-0.5">
                              {a.benefits.slice(0, 4).map((b, i) => (
                                <li key={i}>{b}</li>
                              ))}
                            </ul>
                          )}

                          {a.ad_copy && (
                            <div className="text-xs italic text-white/60 border-l-2 border-amber-500/40 pl-2">
                              "{a.ad_copy}"
                            </div>
                          )}

                          {a.cta && (
                            <div className="inline-block text-[10px] uppercase tracking-wider font-bold text-amber-300 bg-amber-500/10 border border-amber-500/30 rounded px-2 py-1">
                              CTA: {a.cta}
                            </div>
                          )}

                          {Array.isArray(a.hashtags) && a.hashtags.length > 0 && (
                            <div className="flex flex-wrap gap-1 pt-1">
                              {a.hashtags.slice(0, 6).map((h, i) => (
                                <span
                                  key={i}
                                  className="text-[10px] text-purple-300/80 bg-purple-500/10 rounded px-1.5 py-0.5"
                                >
                                  {h.startsWith('#') ? h : `#${h}`}
                                </span>
                              ))}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })()}

            {/* Deploy Button */}
            <button
              onClick={handleDeploy}
              disabled={product.is_mock || deploying}
              className="w-full py-4 rounded-xl bg-gradient-to-r from-purple-600 to-cyan-600 text-white font-bold hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-3"
            >
              {deploying ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : product.is_mock ? (
                <>
                  <AlertTriangle className="w-5 h-5" />
                  Cannot Deploy Demo Products
                </>
              ) : (
                <>
                  <Rocket className="w-5 h-5" />
                  Deploy to Shopify
                  <ChevronRight className="w-5 h-5" />
                </>
              )}
            </button>
          </div>

          {/* Tags */}
          {product.tags?.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {product.tags.map((tag, i) => (
                <span key={i} className="px-3 py-1 rounded-full bg-purple-500/20 text-purple-300 text-sm flex items-center gap-1">
                  <Tag className="w-3 h-3" />
                  {tag}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>

      <style>{`
        @keyframes slideIn {
          from { transform: translateX(100%); }
          to { transform: translateX(0); }
        }
      `}</style>
    </>
  );
}

// ============================================================================
// MAIN COMPONENT: Product Discovery
// ============================================================================
export function ProductDiscovery() {
  const toast = useToast();
  const { user, hasTier } = useAuth();
  const { 
    setVisibleProducts, 
    setSelectedProduct, 
    addRecentSearch, 
    setActiveFilters,
    trackInteraction,
    state: dashboardState 
  } = useDashboardContext();
  
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [filter, setFilter] = useState('trending');
  // Supplier/warehouse filter (Option A): 'all' | 'us' | 'eu' | 'cross' | 'cj_only'
  const [supplierFilter, setSupplierFilter] = useState('all');
  const [currentNiche, setCurrentNiche] = useState('smart_home');
  const [rateLimit, setRateLimit] = useState(null);
  const [selectedProduct, setSelectedProductState] = useState(null);
  const [hasMockData, setHasMockData] = useState(false);
  const [hasEstimatedScores, setHasEstimatedScores] = useState(false);
  // Populated when the discovery API returns a 503 / structured error.
  // Shape: { error, discovery_error, diagnostics, hint, status } or null.
  const [discoveryError, setDiscoveryError] = useState(null);
  // Populated when the backend clamped the requested product count to the
  // caller's tier ceiling. Shape:
  //   { tier, per_request_ceiling, requested, clamped } or null.
  // Surfaced by services/api.js as a non-enumerable property on the products
  // array — we copy it into state so the upgrade-nudge banner can dismiss
  // independently of the product list.
  const [tierNudge, setTierNudge] = useState(null);
  const [generatingImages, setGeneratingImages] = useState(false);
  const [showEnhancer, setShowEnhancer] = useState(false);
  const [enhancerProduct, setEnhancerProduct] = useState(null);
  // Auto-enhance OFF by default - user must opt-in (prevents accidental API costs)
  // Persist preference in localStorage
  const [autoEnhanceEnabled, setAutoEnhanceEnabled] = useState(() => {
    const saved = localStorage.getItem('ospra_auto_enhance');
    return saved === 'true'; // Default to false unless explicitly enabled
  });

  // Save preference when it changes
  useEffect(() => {
    localStorage.setItem('ospra_auto_enhance', autoEnhanceEnabled.toString());
  }, [autoEnhanceEnabled]);
  const [enhanceProgress, setEnhanceProgress] = useState({ current: 0, total: 0, enhancing: false });

  // Initial load
  useEffect(() => {
    loadProducts();
    loadRateLimit();
  }, []);

  // Re-sort when filter changes (no API call, just re-sort existing products)
  useEffect(() => {
    if (products.length === 0) return;

    let sortedProducts = [...products];

    if (filter === 'trending') {
      sortedProducts.sort((a, b) => {
        const aScore = (a.trend_score || 50) + (a.viral_score || 0);
        const bScore = (b.trend_score || 50) + (b.viral_score || 0);
        return bScore - aScore;
      });
    } else if (filter === 'recommended') {
      sortedProducts.sort((a, b) => (b.oi_score || 0) - (a.oi_score || 0));
    } else if (filter === 'high-profit') {
      sortedProducts.sort((a, b) => {
        const aMargin = a.cost_price > 0 ? ((a.suggested_price - a.cost_price) / a.cost_price) : 0;
        const bMargin = b.cost_price > 0 ? ((b.suggested_price - b.cost_price) / b.cost_price) : 0;
        return bMargin - aMargin;
      });
    }

    setProducts(sortedProducts);
  }, [filter]);

  useEffect(() => {
    if (products.length > 0) {
      const formattedProducts = products.map(p => ({
        id: p.id || '',
        name: p.title || p.name || '',
        price: p.suggested_price || p.price,
        supplier_cost: p.cost_price || p.supplier_cost,
        score: p.oi_score || 0,
        niche: p.niche || (p.tags?.[0]) || '',
        trend_score: p.trend_score,
        source: p.source || 'discovery',
      }));
      setVisibleProducts(formattedProducts);
    }
  }, [products, setVisibleProducts]);

  useEffect(() => {
    setActiveFilters({ filter, view: 'products' });
  }, [filter, setActiveFilters]);

  // Supplier/warehouse counts for the filter chip row (Option A).
  // Computed off the full `products` array so counts don't change when a
  // filter is active (that's the standard filter-chip UX).
  const supplierCounts = useMemo(() => ({
    all: products.length,
    us: products.filter(p => p.us_warehouse).length,
    eu: products.filter(p => p.eu_warehouse).length,
    cross: products.filter(p => p.cross_referenced).length,
    cj_only: products.filter(p => p.on_cj && !p.on_aliexpress).length,
  }), [products]);

  // Apply the active supplier filter. Sorting already happened in the
  // re-sort effect above, so we just need to filter here — preserve order.
  const filteredProducts = useMemo(() => {
    switch (supplierFilter) {
      case 'us':      return products.filter(p => p.us_warehouse);
      case 'eu':      return products.filter(p => p.eu_warehouse);
      case 'cross':   return products.filter(p => p.cross_referenced);
      case 'cj_only': return products.filter(p => p.on_cj && !p.on_aliexpress);
      case 'all':
      default:        return products;
    }
  }, [products, supplierFilter]);

  // Auto-enhance ALL products in background when they load
  // Optimized: Check disk cache first, only enhance non-cached images
  const autoEnhanceAllProducts = async (productsToEnhance) => {
    // Re-check autoEnhanceEnabled from localStorage (in case it changed)
    const isEnabled = localStorage.getItem('ospra_auto_enhance') === 'true';

    if (!isEnabled) {
      // console.log('[AUTO-ENHANCE] ⛔ DISABLED - skipping (turn ON to enable)');
      return;
    }

    if (productsToEnhance.length === 0) {
      // console.log('[AUTO-ENHANCE] No products to enhance');
      return;
    }

    // console.log('[AUTO-ENHANCE] 🚀 Starting with', productsToEnhance.length, 'products...');

    // Phase 1: Collect ALL image URLs and check cache in one request
    const allImageUrls = [];
    const urlToProductIndex = {}; // Map URL -> product index for quick lookup

    productsToEnhance.forEach((product, productIdx) => {
      // Skip if already has enhanced images in state
      if (product.enhanced_images?.length > 0 || product.ai_image_url) {
        // console.log(`[AUTO-ENHANCE] Skipping product ${productIdx} - already has enhanced images`);
        return;
      }

      const images = product.all_images || [product.image_url].filter(Boolean);
      images.forEach(url => {
        if (url && !allImageUrls.includes(url)) {
          allImageUrls.push(url);
          if (!urlToProductIndex[url]) urlToProductIndex[url] = [];
          urlToProductIndex[url].push(productIdx);
        }
      });
    });

    if (allImageUrls.length === 0) {
      // console.log('[AUTO-ENHANCE] ✅ All products already have enhanced images - nothing to do');
      return;
    }

    // console.log('[AUTO-ENHANCE] 🔍 Checking cache for', allImageUrls.length, 'images...');

    // Check which images are already cached on disk
    try {
      let cacheCheck = await api.checkImageCache(allImageUrls);
      let cachedCount = cacheCheck.cached_count || 0;
      let notCachedUrls = cacheCheck.not_cached || [];

      // console.log(`[AUTO-ENHANCE] 📦 Initial cache check: ${cachedCount} CACHED (FREE), ${notCachedUrls.length} not found`);

      // If many images weren't found, try smart cache recovery
      if (notCachedUrls.length > 0 && cachedCount < allImageUrls.length / 2) {
        // console.log('[AUTO-ENHANCE] 🔍 Trying smart cache recovery for', notCachedUrls.length, 'images...');
        const recovery = await api.smartCacheRecovery(notCachedUrls, null);
        if (recovery.success && recovery.matches_found > 0) {
          // console.log(`[AUTO-ENHANCE] ✅ Smart recovery found ${recovery.matches_found} additional cached images!`);
          // Merge recovered matches into cacheCheck
          recovery.matches.forEach(match => {
            // Find the original URL that was recovered
            const originalUrl = notCachedUrls.find(url =>
              url.includes(match.original_url.replace('...', '')) || match.original_url.includes(url.substring(0, 50))
            );
            if (originalUrl) {
              cacheCheck.cached = cacheCheck.cached || {};
              cacheCheck.cached[originalUrl] = match.enhanced_url;
            }
          });
          cachedCount = Object.keys(cacheCheck.cached || {}).length;
          notCachedUrls = notCachedUrls.filter(url => !cacheCheck.cached?.[url]);
        }
      }

      // console.log(`[AUTO-ENHANCE] 📦 Final cache result: ${cachedCount} CACHED (FREE), ${notCachedUrls.length} need enhancement`);

      // Phase 2: Apply cached images immediately (FREE - no API cost)
      const updatedProducts = [...productsToEnhance];
      const cachedMap = cacheCheck.cached || {};

      // Apply cached URLs to products
      let appliedCount = 0;
      Object.entries(cachedMap).forEach(([originalUrl, cachedUrl]) => {
        const productIndices = urlToProductIndex[originalUrl] || [];
        productIndices.forEach(idx => {
          const product = updatedProducts[idx];
          const enhancedImages = product.enhanced_images || [];
          if (!enhancedImages.includes(cachedUrl)) {
            updatedProducts[idx] = {
              ...product,
              ai_image_url: product.ai_image_url || cachedUrl,
              enhanced_images: [...enhancedImages, cachedUrl]
            };
            appliedCount++;
          }
        });
      });

      // Update UI with cached images immediately
      if (appliedCount > 0) {
        // console.log(`[AUTO-ENHANCE] ✅ Applied ${appliedCount} cached images (FREE - $0.00)`);
        setProducts([...updatedProducts]);
      }

      // Phase 3: Check if we need to enhance anything new
      if (notCachedUrls.length === 0) {
        // console.log('[AUTO-ENHANCE] 🎉 Complete! All images were cached (FREE)');
        return;
      }

      // STOP HERE if there are non-cached images - don't auto-spend money
      // console.log(`[AUTO-ENHANCE] ⚠️ ${notCachedUrls.length} images NOT cached - manual enhancement needed (~$${(notCachedUrls.length * 0.06).toFixed(2)})`);
      // console.log('[AUTO-ENHANCE] 💡 Click "Enhance All" button to enhance remaining images');

      // Don't automatically enhance non-cached images - let user decide
      return;

    } catch (error) {
      console.error('[AUTO-ENHANCE] ❌ Cache check failed:', error);
      return;
    }
  };

  const loadProducts = async (nicheOverride = null) => {
    setHasMockData(false);
    setHasEstimatedScores(false);
    setDiscoveryError(null);

    // Use override niche if provided (from niche chip click), else use current niche
    const niche = nicheOverride || currentNiche;
    if (nicheOverride) setCurrentNiche(nicheOverride);

    // Task #35 — render-while-revalidate. The discovery API takes 30-60s on
    // a cold call; previously the page sat on a skeleton the entire time.
    // Read the last successful response for this niche from localStorage and
    // paint immediately so the user has something to look at while the live
    // call is in flight. We still fire the fetch on every load — the cache
    // is purely a paint optimisation, not a freshness contract.
    const cacheKey = `ospra_products_v1:${niche}`;
    let usedCache = false;
    try {
      const raw = localStorage.getItem(cacheKey);
      if (raw) {
        const parsed = JSON.parse(raw);
        const age = Date.now() - (parsed.savedAt || 0);
        // Show cached data for up to 24h, but never paint anything older
        // than that — stale prices/scores feel like a bug.
        if (Array.isArray(parsed.products) && parsed.products.length > 0
            && age < 24 * 60 * 60 * 1000) {
          setProducts(parsed.products);
          setLoading(false);
          usedCache = true;
          console.log(
            `[ProductDiscovery] Painted ${parsed.products.length} cached `
            + `products for ${niche} (age: ${Math.round(age/1000)}s) — `
            + `refreshing in background`
          );
        }
      }
    } catch (e) {
      console.warn('[ProductDiscovery] cache read failed:', e);
    }
    // Only show skeleton when we didn't have a cache hit
    if (!usedCache) setLoading(true);

    try {
      console.log(`[ProductDiscovery] Loading products for niche: ${niche}`);

      // #56: prefer the PERSISTENT CATALOG — dozens of graded products with
      // proof-age + competition, populated by the catalog_warm cron. When the
      // catalog is empty (cron not yet run) we fall through to on-demand
      // discovery, so the page behaves exactly as before until it's warmed.
      try {
        const catalog = await api.getCatalog({ niche, sort: 'score', limit: 60 });
        if (Array.isArray(catalog) && catalog.length > 0) {
          const normalized = catalog.map(p => ({
            ...normalizeProduct(p, p.niche || niche),
            // Re-attach catalog-only signals so OpportunityBadges can render
            // them (normalizeProduct may not carry these through).
            velocity_phase: p.velocity_phase,
            saturation_score: p.saturation_score,
            opportunity_score: p.opportunity_score,
            days_of_proof: p.days_of_proof,
            times_seen: p.times_seen,
          }));
          console.log(`[ProductDiscovery] Catalog hit: ${normalized.length} products for ${niche}`);
          setProducts(normalized);
          setDiscoveryError(null);
          try {
            localStorage.setItem(cacheKey, JSON.stringify({ products: normalized, savedAt: Date.now() }));
          } catch (_) { /* localStorage full/unavailable — non-fatal */ }
          setLoading(false);
          return;
        }
        console.log(`[ProductDiscovery] Catalog empty for ${niche} — falling back to on-demand discovery`);
      } catch (e) {
        console.warn('[ProductDiscovery] catalog fetch failed, using on-demand discovery', e);
      }

      // Fetch products (same niche for all filter types).
      // Initial load fetches 20 to stay under Safari's ~60s fetch timeout.
      // User can click "Load more" to fetch additional pages up to their
      // tier ceiling (NEST=10, FLIGHT=25, SOAR=50, STRATOSPHERE=100).
      // AI image generation is MANUAL CLICK ONLY (Stability ~$0.06/img,
      // per CLAUDE.md standing rule) — defaults to OFF in api layer.
      const response = await api.discoverProducts({ niche, count: 20 });
      console.log('[ProductDiscovery] API Response:', response);

      // Structured error from backend (503 with diagnostics) — surface it to the user.
      if (response && response.__error) {
        console.error('[ProductDiscovery] Discovery error:', response);
        // Coerce any object-shaped error fields to strings up front. The
        // backend can send these as objects like {code, message}; rendering an
        // object as a React child crashes the whole page ("Objects are not
        // valid as a React child"). Normalizing here makes every downstream
        // render safe regardless of the backend's error shape.
        const asText = (v) =>
          v == null
            ? v
            : typeof v === 'string'
              ? v
              : (v.message || v.detail || v.error || JSON.stringify(v));
        setDiscoveryError({
          status: response.status,
          error: asText(response.error),
          discovery_error: asText(response.discovery_error),
          diagnostics: response.diagnostics,
          hint: asText(response.hint),
        });
        setProducts([]);
        return;
      }

      let loadedProducts = Array.isArray(response) ? response : (response.products || response.data || []);
      console.log(`[ProductDiscovery] Loaded ${loadedProducts.length} products from API`);

      // Surface tier-clamp event as an upgrade-nudge banner. The API layer
      // attaches tier_meta non-enumerably; we read it here and push it into
      // state so the banner can be dismissed without re-clearing the product
      // list.
      const tierMeta = response?.tier_meta;
      if (tierMeta?.clamped) {
        setTierNudge(tierMeta);
      } else {
        setTierNudge(null);
      }

      // If still no products, log warning
      if (!loadedProducts || loadedProducts.length === 0) {
        console.warn('[ProductDiscovery] API returned 0 products - server may need restart');
      }

      let normalizedProducts = loadedProducts.map(p => normalizeProduct(p, niche));

      // Sort based on selected filter
      if (filter === 'trending') {
        // Sort by trend score + viral score (higher = more trending)
        normalizedProducts.sort((a, b) => {
          const aScore = (a.trend_score || 50) + (a.viral_score || 0);
          const bScore = (b.trend_score || 50) + (b.viral_score || 0);
          return bScore - aScore;
        });
      } else if (filter === 'recommended') {
        // Sort by OI score (balanced recommendation)
        normalizedProducts.sort((a, b) => (b.oi_score || 0) - (a.oi_score || 0));
      } else if (filter === 'high-profit') {
        // Sort by profit margin
        normalizedProducts.sort((a, b) => {
          const aMargin = a.cost_price > 0 ? ((a.suggested_price - a.cost_price) / a.cost_price) : 0;
          const bMargin = b.cost_price > 0 ? ((b.suggested_price - b.cost_price) / b.cost_price) : 0;
          return bMargin - aMargin;
        });
      }

      // Limit to 20 products after sorting
      normalizedProducts = normalizedProducts.slice(0, 20);

      const mockCount = normalizedProducts.filter(p => p.is_mock).length;
      const estimatedCount = normalizedProducts.filter(p => p.scores_estimated).length;
      setHasMockData(mockCount > 0);
      setHasEstimatedScores(estimatedCount > normalizedProducts.length / 2);
      setProducts(normalizedProducts);

      // Task #35 — persist for the next visit's render-while-revalidate.
      // Only cache when we got real data (not mock/empty), so cold-load
      // failures don't poison the cache and keep painting bad data.
      if (normalizedProducts.length > 0 && mockCount === 0) {
        try {
          localStorage.setItem(cacheKey, JSON.stringify({
            savedAt: Date.now(),
            niche,
            products: normalizedProducts,
          }));
        } catch (e) {
          // Quota exceeded or storage disabled — non-fatal
          console.warn('[ProductDiscovery] cache write failed:', e);
        }
      }

      trackInteraction('filter', { filter, niche, result_count: normalizedProducts.length, mock_count: mockCount });

      // console.log(`[ProductDiscovery] Set ${normalizedProducts.length} products to state`);

      // Auto-enhance all products in background (if enabled)
      if (autoEnhanceEnabled && normalizedProducts.length > 0) {
        setTimeout(() => autoEnhanceAllProducts(normalizedProducts), 500);
      }
    } catch (error) {
      console.error('[ProductDiscovery] Failed to load products:', error);
      setProducts([]);
    } finally {
      setLoading(false);
    }
  };
  
  // Enhance images using background removal
  const enhanceProductImages = async () => {
    if (products.length === 0) return;
    setGeneratingImages(true);
    
    try {
      const apiBase = import.meta.env.VITE_API_URL || 'http://localhost:8000';
      
      // Prepare batch request
      const imagesToEnhance = products.slice(0, 5).map(p => ({
        url: p.image_url,
        id: p.id,
        title: p.title,
        niche: p.niche || 'smart_home'
      }));
      
      const response = await fetch(`${apiBase}/api/images/enhance/batch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          images: imagesToEnhance,
          niche: 'smart_home',
          max_concurrent: 3
        })
      });
      
      const data = await response.json();
      
      if (data.results) {
        // Update products with enhanced images
        const updatedProducts = products.map(p => {
          const result = data.results.find(r => r.id === p.id);
          if (result?.success && result.enhanced_image_url) {
            return { ...p, ai_image_url: result.enhanced_image_url };
          }
          return p;
        });
        
        setProducts(updatedProducts);
        trackInteraction('enhance_images', {
          total: data.total,
          successful: data.successful,
          cost: data.estimated_cost
        });
      }
    } catch (error) {
      console.error('Image enhancement failed:', error);
      toast.error('Enhancement failed: ' + (error.message || 'Unknown error'));
    } finally {
      setGeneratingImages(false);
    }
  };

  // Legacy: Generate AI images for current products (kept for compatibility)
  const generateAiImages = async () => {
    if (products.length === 0) return;
    setGeneratingImages(true);
    try {
      // Send raw product data for enhancement
      const rawProducts = products.map(p => ({
        title: p.title,
        niche: p.niche,
        image_url: p.image_url,
        tags: p.tags,
      }));
      const enhanced = await api.enhanceProductsWithAiImages(rawProducts, 5);
      // Update products with AI images
      const updatedProducts = products.map((p, idx) => ({
        ...p,
        ai_image_url: enhanced[idx]?.ai_image_url || p.ai_image_url,
        image_source: enhanced[idx]?.image_source || p.image_source,
      }));
      setProducts(updatedProducts);
      trackInteraction('generate_ai_images', { count: updatedProducts.filter(p => p.ai_image_url).length });
    } catch (error) {
      console.error('Failed to generate AI images:', error);
    } finally {
      setGeneratingImages(false);
    }
  };

  const loadRateLimit = async () => {
    try {
      const response = await api.getRateLimitStatus();
      setRateLimit(response);
    } catch (error) {
      setRateLimit({ daily_remaining: '∞', daily_limit: '∞' });
    }
  };

  const handleSearch = async (nicheQuery = null) => {
    const query = nicheQuery || searchQuery.trim();
    if (!query) return;

    // Update current niche and searchQuery
    const normalizedNiche = query.toLowerCase().replace(/\s+/g, '_');
    setCurrentNiche(normalizedNiche);
    if (!nicheQuery) addRecentSearch(query);

    // Load products with new niche
    await loadProducts(normalizedNiche);
    trackInteraction('search', { query, result_count: products.length });
  };

  // Handler for niche chip clicks
  const handleNicheClick = (nicheKey) => {
    setSearchQuery(nicheKey.replace('_', ' '));
    handleSearch(nicheKey);
  };

  const handleProductSelect = useCallback((product) => {
    setSelectedProductState(product);
    setSelectedProduct({
      id: product.id,
      name: product.title,
      price: product.suggested_price,
      supplier_cost: product.cost_price,
      score: product.oi_score,
      niche: product.niche,
      trend_score: product.trend_score,
      source: product.source,
    });
    trackInteraction('product_view', {
      product_id: product.id,
      product_name: product.title,
      niche: product.niche,
      score: product.oi_score,
      price: product.suggested_price,
    });
  }, [setSelectedProduct, trackInteraction]);

  const handleDeploy = async (product, caption) => {
    if (product.is_mock) return;
    // Task #21: send the full product object — the backend schema requires
    // title/price/images, not just an ID. Works for AliExpress AND CJ.
    await api.deployProduct(product, { caption });
    trackInteraction('product_deploy', {
      product_id: product.id,
      product_name: product.title,
      niche: product.niche,
      price: product.suggested_price,
      source: product.source,
    });
  };

  const getSubtitle = () => {
    if (rateLimit?.daily_remaining !== undefined && rateLimit?.daily_limit !== undefined) {
      return `${rateLimit.daily_remaining}/${rateLimit.daily_limit} discoveries today`;
    }
    return `${products.length} products loaded`;
  };

  return (
    <PageLayout title="Product Discovery" subtitle={getSubtitle()}>
      {/* Mock Data Warning */}
      {hasMockData && (
        <div className="mb-6 p-4 rounded-xl bg-yellow-500/10 border border-yellow-500/30 flex items-center gap-3">
          <AlertTriangle className="w-5 h-5 text-yellow-400 flex-shrink-0" />
          <div>
            <p className="text-yellow-200 font-medium">Showing Demo Products</p>
            <p className="text-yellow-200/70 text-sm">APIs returned empty data. Check backend logs for connection issues.</p>
          </div>
        </div>
      )}
      
      {/* Estimated Scores Warning */}
      {hasEstimatedScores && !hasMockData && (
        <div className="mb-6 p-4 rounded-xl bg-blue-500/10 border border-blue-500/30 flex items-center gap-3">
          <Info className="w-5 h-5 text-blue-400 flex-shrink-0" />
          <div>
            <p className="text-blue-200 font-medium">Limited Data Available</p>
            <p className="text-blue-200/70 text-sm">Scores marked "Est." are estimates. Connect Google Trends, TikTok, and sentiment APIs for accurate metrics.</p>
          </div>
        </div>
      )}

      {/* Tier clamp nudge — shown when the backend capped the requested
          product count at the caller's per-request ceiling (see
          ospra_os/core/tiers.py::get_products_per_request_ceiling). */}
      {tierNudge && (
        <div className="mb-6 p-4 rounded-xl bg-purple-500/10 border border-purple-500/30 flex items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <Info className="w-5 h-5 text-purple-300 flex-shrink-0" />
            <div>
              <p className="text-purple-100 font-medium">
                Showing {tierNudge.per_request_ceiling} of {tierNudge.requested} requested products
              </p>
              <p className="text-purple-200/70 text-sm">
                Your {tierNudge.tier} tier caps per-request discovery at {tierNudge.per_request_ceiling}.
                {' '}Upgrade for more results per run.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <a
              href="/settings?tab=billing"
              className="px-3 py-1.5 rounded-lg text-sm font-medium bg-purple-500/30 hover:bg-purple-500/40 text-purple-100 border border-purple-400/40"
            >
              See plans
            </a>
            <button
              onClick={() => setTierNudge(null)}
              className="text-purple-200/60 hover:text-purple-100 text-sm px-2"
              aria-label="Dismiss upgrade nudge"
            >
              Dismiss
            </button>
          </div>
        </div>
      )}

      {/* Search & Filter - Modern SaaS Design */}
      <div className="backdrop-blur-xl bg-white/5 rounded-2xl border border-white/10 p-6 mb-6">
        {/* Row 1: Search + Sort */}
        <div className="flex flex-col lg:flex-row gap-4 items-center">
          {/* Search Input - Full Width on Mobile */}
          <div className="flex-1 w-full flex gap-2">
            <div className="flex-1 relative">
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-white/40" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
                placeholder="Search winning products..."
                className="w-full pl-12 pr-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white placeholder-white/40 focus:outline-none focus:border-purple-500/50 focus:ring-1 focus:ring-purple-500/30"
              />
            </div>
            <button onClick={handleSearch} className="px-5 py-3 rounded-xl bg-gradient-to-r from-purple-600 to-cyan-600 text-white font-semibold hover:opacity-90 transition-all hover:scale-[1.02] active:scale-[0.98]">
              <Search className="w-5 h-5" />
            </button>
          </div>

          {/* Sort Dropdown - Replaces old tabs */}
          <div className="flex items-center gap-3">
            <span className="text-white/50 text-sm hidden sm:block">Sort by:</span>
            <select
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              className="px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white text-sm font-medium focus:outline-none focus:border-purple-500/50 cursor-pointer appearance-none min-w-[160px]"
              style={{ backgroundImage: `url("data:image/svg+xml,%3csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 20 20'%3e%3cpath stroke='%236b7280' stroke-linecap='round' stroke-linejoin='round' stroke-width='1.5' d='M6 8l4 4 4-4'/%3e%3c/svg%3e")`, backgroundPosition: 'right 0.75rem center', backgroundRepeat: 'no-repeat', backgroundSize: '1.5em 1.5em', paddingRight: '2.5rem' }}
            >
              <option value="trending" className="bg-gray-900">Trending Now</option>
              <option value="recommended" className="bg-gray-900">Top Rated</option>
              <option value="high-profit" className="bg-gray-900">High Profit</option>
            </select>
          </div>
        </div>

        {/* Row 2: Niche Quick Filters */}
        <div className="mt-4 flex flex-wrap gap-2">
          {[
            { key: 'smart_home', label: 'Smart Home' },
            { key: 'tech', label: 'Tech' },
            { key: 'fitness', label: 'Fitness' },
            { key: 'kitchen', label: 'Kitchen' },
            { key: 'beauty', label: 'Beauty' },
            { key: 'pet', label: 'Pet' },
          ].map((niche) => (
            <button
              key={niche.key}
              onClick={() => handleNicheClick(niche.key)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                currentNiche === niche.key
                  ? 'bg-purple-500/20 border border-purple-500/30 text-purple-300'
                  : 'bg-white/5 border border-white/10 text-white/70 hover:bg-white/10 hover:text-white hover:border-purple-500/30'
              }`}
            >
              {niche.label}
            </button>
          ))}
        </div>

        {/* Row 3: Image Tools - Collapsible/Minimal */}
        <div className="mt-4 pt-4 border-t border-white/5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <button
                onClick={() => setAutoEnhanceEnabled(!autoEnhanceEnabled)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium flex items-center gap-2 transition-all ${
                  autoEnhanceEnabled
                    ? 'bg-green-500/10 border border-green-500/20 text-green-400'
                    : 'bg-white/5 border border-white/5 text-white/40 hover:text-white/60'
                }`}
              >
                {autoEnhanceEnabled ? <ToggleRight className="w-3.5 h-3.5" /> : <ToggleLeft className="w-3.5 h-3.5" />}
                <span className="hidden sm:inline">Auto-Enhance</span>
                <span className="sm:hidden">{autoEnhanceEnabled ? 'ON' : 'OFF'}</span>
              </button>
              <span className="text-white/30 text-xs hidden md:block">
                {products.length > 0 && `${products.length} products`}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => autoEnhanceAllProducts(products)}
                disabled={enhanceProgress.enhancing || products.length === 0}
                className="px-3 py-1.5 rounded-lg bg-purple-500/10 border border-purple-500/20 text-purple-300 text-xs font-medium hover:bg-purple-500/20 disabled:opacity-30 disabled:cursor-not-allowed flex items-center gap-1.5 transition-all"
              >
                {enhanceProgress.enhancing ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    <span>{enhanceProgress.current}/{enhanceProgress.total}</span>
                  </>
                ) : (
                  <>
                    <Sparkles className="w-3.5 h-3.5" />
                    <span className="hidden sm:inline">Enhance Images</span>
                    <span className="sm:hidden">Enhance</span>
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Progress Bar */}
          {enhanceProgress.enhancing && (
            <div className="mt-2">
              <div className="h-1 bg-white/5 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-purple-500 to-cyan-500 transition-all duration-300"
                  style={{ width: `${(enhanceProgress.current / enhanceProgress.total) * 100}%` }}
                />
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Product Grid */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {[...Array(8)].map((_, i) => (
            <div key={i} className="backdrop-blur-xl bg-white/5 rounded-2xl border border-white/10 overflow-hidden animate-pulse">
              <div className="aspect-square bg-white/5" />
              <div className="p-4 space-y-3">
                <div className="h-4 bg-white/10 rounded w-3/4" />
                <div className="h-3 bg-white/10 rounded w-1/2" />
              </div>
            </div>
          ))}
        </div>
      ) : products.length > 0 ? (
        <>
          {/* Supplier / warehouse filter chips (Option A) - only show when there's
              something meaningful to filter by (don't clutter the UI with empty chips). */}
          {(supplierCounts.us > 0 || supplierCounts.eu > 0 || supplierCounts.cross > 0 || supplierCounts.cj_only > 0) && (
            <div className="mb-4 flex flex-wrap gap-2 items-center">
              <span className="text-white/40 text-xs mr-1">Supplier:</span>
              {[
                { key: 'all',     label: 'All',        count: supplierCounts.all,     activeClass: 'bg-white/10 border-white/30 text-white' },
                { key: 'us',      label: '🇺🇸 US',      count: supplierCounts.us,      activeClass: 'bg-green-500/20 border-green-500/40 text-green-300' },
                { key: 'eu',      label: '🇪🇺 EU',      count: supplierCounts.eu,      activeClass: 'bg-blue-500/20 border-blue-500/40 text-blue-300' },
                { key: 'cross',   label: '⚡ Cross-ref', count: supplierCounts.cross,   activeClass: 'bg-purple-500/20 border-purple-500/40 text-purple-300' },
                { key: 'cj_only', label: 'CJ only',    count: supplierCounts.cj_only, activeClass: 'bg-orange-500/20 border-orange-500/40 text-orange-300' },
              ]
                .filter(chip => chip.key === 'all' || chip.count > 0)
                .map(chip => {
                  const isActive = supplierFilter === chip.key;
                  return (
                    <button
                      key={chip.key}
                      onClick={() => setSupplierFilter(chip.key)}
                      className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-all flex items-center gap-1.5 ${
                        isActive
                          ? chip.activeClass
                          : 'bg-white/5 border-white/10 text-white/60 hover:bg-white/10 hover:text-white'
                      }`}
                    >
                      <span>{chip.label}</span>
                      <span className={`text-[10px] ${isActive ? '' : 'text-white/40'}`}>{chip.count}</span>
                    </button>
                  );
                })}
              {supplierFilter !== 'all' && (
                <button
                  onClick={() => setSupplierFilter('all')}
                  className="text-white/40 hover:text-white text-xs ml-1 underline underline-offset-2"
                >
                  clear
                </button>
              )}
            </div>
          )}

          {filteredProducts.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
              {filteredProducts.map((product) => (
                <ProductCard
                  key={product.id}
                  product={product}
                  onClick={() => handleProductSelect(product)}
                />
              ))}
            </div>
          ) : (
            <div className="text-center py-16 rounded-2xl bg-white/5 border border-white/10">
              <Package className="w-12 h-12 text-white/20 mx-auto mb-3" />
              <p className="text-white/70 mb-2">No products match this filter</p>
              <button
                onClick={() => setSupplierFilter('all')}
                className="text-purple-300 hover:text-purple-200 text-sm underline underline-offset-2"
              >
                Show all {supplierCounts.all} products
              </button>
            </div>
          )}
        </>
      ) : (
        <div className="text-center py-20">
          <Package className="w-16 h-16 text-white/20 mx-auto mb-4" />
          {discoveryError ? (
            <>
              <h3 className="text-xl font-semibold text-white mb-2">Discovery unavailable</h3>
              <p className="text-red-300 mb-4 max-w-lg mx-auto">
                {/* Coerce to string — the backend error field can be an object
                    like {code, message}; rendering that object directly crashes
                    React ("Objects are not valid as a React child"). */}
                {(typeof discoveryError.error === 'string'
                  ? discoveryError.error
                  : discoveryError.error?.message || discoveryError.error?.detail)
                  || 'No real products could be fetched.'}
              </p>

              {discoveryError.diagnostics && (
                <div className="max-w-lg mx-auto mb-4 text-left bg-red-500/10 border border-red-500/30 rounded-xl p-4">
                  <div className="text-sm text-red-200 mb-2 font-semibold">
                    Source status: {discoveryError.diagnostics.total_connected ?? 0}/{discoveryError.diagnostics.total_sources ?? 0} connected
                  </div>

                  {discoveryError.diagnostics.sources_connected?.length > 0 && (
                    <div className="text-xs text-green-300 mb-2">
                      <span className="font-semibold">Connected:</span>{' '}
                      {discoveryError.diagnostics.sources_connected.join(', ')}
                    </div>
                  )}

                  {discoveryError.diagnostics.sources_failed && Object.keys(discoveryError.diagnostics.sources_failed).length > 0 && (
                    <div className="text-xs text-red-300">
                      <span className="font-semibold">Failed:</span>
                      <ul className="mt-1 ml-4 list-disc">
                        {Object.entries(discoveryError.diagnostics.sources_failed).map(([k, v]) => (
                          <li key={k}><span className="font-mono">{k}</span>: {String(v)}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {discoveryError.discovery_error && (
                    <div className="text-xs text-red-200 mt-2 font-mono break-all">
                      Engine error: {typeof discoveryError.discovery_error === 'string'
                        ? discoveryError.discovery_error
                        : (discoveryError.discovery_error?.message
                          || JSON.stringify(discoveryError.discovery_error))}
                    </div>
                  )}
                </div>
              )}

              {discoveryError.hint && (
                <p className="text-white/60 text-sm max-w-lg mx-auto mb-4">{discoveryError.hint}</p>
              )}
            </>
          ) : (
            <>
              <h3 className="text-xl font-semibold text-white mb-2">No products found</h3>
              <p className="text-white/50 mb-4">No real products matched this niche. Try another niche or a fresh search.</p>
            </>
          )}

          <button
            onClick={() => loadProducts()}
            className="px-6 py-3 rounded-xl bg-purple-500/20 border border-purple-500/30 text-purple-300 font-medium hover:bg-purple-500/30 flex items-center gap-2 mx-auto"
          >
            <RefreshCw className="w-4 h-4" />
            Retry
          </button>
          <p className="text-white/30 text-xs mt-4">Check browser console (F12) for API errors</p>
        </div>
      )}

      {/* Detail Panel */}
      {selectedProduct && (
        <ProductDetailPanel
          product={selectedProduct}
          onClose={() => setSelectedProductState(null)}
          onDeploy={handleDeploy}
          onUpdateProduct={(updatedProduct) => {
            // Update product in list with new AI image
            setProducts(prev => prev.map(p => 
              p.id === updatedProduct.id ? updatedProduct : p
            ));
            setSelectedProductState(updatedProduct);
          }}
          onEnhance={(product) => {
            setEnhancerProduct(product);
            setShowEnhancer(true);
          }}
        />
      )}

      {/* Image Enhancer Modal */}
      {showEnhancer && (
        <AIImageComparison
          product={enhancerProduct || selectedProduct}
          isModal={true}
          onClose={() => {
            setShowEnhancer(false);
            setEnhancerProduct(null);
          }}
          onImageEnhanced={(enhancedUrl) => {
            // Update product with enhanced image
            const targetProduct = enhancerProduct || selectedProduct;
            if (targetProduct) {
              const updatedProduct = { ...targetProduct, ai_image_url: enhancedUrl };
              setProducts(prev => prev.map(p => 
                p.id === targetProduct.id ? updatedProduct : p
              ));
              if (selectedProduct?.id === targetProduct.id) {
                setSelectedProductState(updatedProduct);
              }
            }
          }}
        />
      )}
    </PageLayout>
  );
}

export default ProductDiscovery;
