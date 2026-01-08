/**
 * OSPRA INTELLIGENCE - PRODUCT DISCOVERY v5
 * ==========================================
 * Clean Oi Score Only - No Tier Badges
 * 
 * Features:
 * - Single Oi Score (0-100) on cards
 * - Click card → Detail panel with score breakdown + data sources
 * - AI image generation
 * - Deploy to Shopify
 * 
 * v5 - Jan 2025: Removed tier badges, Oi Score only
 */

import React, { useState, useEffect, useCallback } from 'react';
import { 
  Search, Package, TrendingUp, Rocket, BarChart3, Tag, Loader2, Filter, 
  ArrowRight, Eye, AlertTriangle, RefreshCw, Sparkles, X, ExternalLink,
  Brain, ShoppingCart, Copy, Check, ChevronRight, Star, Image as ImageIcon,
  Link2, Database, Zap, Target, Wand2, Camera, Layers, DollarSign
} from 'lucide-react';

// ============================================================================
// API CONFIG
// ============================================================================

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

function getToken(): string | null {
  return localStorage.getItem('ospra_token') || sessionStorage.getItem('ospra_token');
}

async function apiCall<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const token = getToken();
  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
      ...options?.headers,
    },
  });
  if (!response.ok) throw new Error(`API error: ${response.status}`);
  return response.json();
}

// ============================================================================
// TYPES
// ============================================================================

interface Product {
  id: string;
  title: string;
  image_url: string | null;
  ai_image_url?: string | null;
  cost_price: number;
  suggested_price: number;
  profit: number;
  oi_score: number;
  niche: string;
  tags: string[];
  source: string;
  is_mock: boolean;
  affiliate_url?: string;
  source_url?: string;
  sales_count?: number;
  rating?: number;
  reviews_count?: number;
  trend_score?: number;
  demand_score?: number;
  competition_score?: number;
  viral_score?: number;
  profit_score?: number;
  recommendation?: string;
  reasons?: string[];
  risks?: string[];
  data_sources?: Record<string, any>;
  image_source?: string;
}

// ============================================================================
// HELPER: Normalize product data
// ============================================================================

function normalizeProduct(p: any, fallbackNiche = 'general'): Product {
  const costPrice = parseFloat(p.cost_price || p.supplier_cost || p.price || 0);
  let suggestedPrice = parseFloat(p.suggested_price || 0);
  if (!suggestedPrice && costPrice > 0) suggestedPrice = costPrice * 2.5;
  let profit = parseFloat(p.profit || 0);
  if (!profit && suggestedPrice > 0 && costPrice > 0) profit = suggestedPrice - costPrice;
  
  const oiScore = Math.round(
    p.oi_score || p.score || p.final_score || p.opportunity_score || 50
  );
  
  return {
    id: p.id || p.product_id || `prod_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
    title: p.title || p.name || p.product_title || 'Untitled Product',
    image_url: p.image_url || p.imageUrl || p.main_image || p.productMainImageUrl || p.original_image_url || null,
    ai_image_url: p.ai_image_url || null,
    cost_price: parseFloat(costPrice.toFixed(2)),
    suggested_price: parseFloat(suggestedPrice.toFixed(2)),
    profit: parseFloat(profit.toFixed(2)),
    oi_score: oiScore,
    niche: p.niche || p.category || fallbackNiche,
    tags: p.tags || [p.niche || fallbackNiche],
    source: p.source || 'aliexpress',
    is_mock: p.is_mock || p.source === 'mock_data',
    affiliate_url: p.affiliate_url || p.affiliateUrl || p.promotionLink || p.promotion_link,
    source_url: p.source_url || p.sourceUrl,
    sales_count: p.sales_count || p.salesCount || p.lastest_volume || 0,
    rating: p.rating,
    reviews_count: p.reviews_count || p.reviewsCount,
    trend_score: p.trend_score,
    demand_score: p.demand_score,
    competition_score: p.competition_score,
    viral_score: p.viral_score,
    profit_score: p.profit_score,
    recommendation: p.recommendation,
    reasons: p.reasons || [],
    risks: p.risks || [],
    data_sources: p.data_sources || {},
    image_source: p.image_source,
  };
}

// ============================================================================
// HELPER: Score color based on value
// ============================================================================

function getScoreColor(score: number): string {
  if (score >= 80) return 'text-green-400';
  if (score >= 60) return 'text-cyan-400';
  if (score >= 40) return 'text-yellow-400';
  return 'text-red-400';
}

function getScoreBgColor(score: number): string {
  if (score >= 80) return 'from-green-500/20 to-green-600/10 border-green-500/30';
  if (score >= 60) return 'from-cyan-500/20 to-cyan-600/10 border-cyan-500/30';
  if (score >= 40) return 'from-yellow-500/20 to-yellow-600/10 border-yellow-500/30';
  return 'from-red-500/20 to-red-600/10 border-red-500/30';
}

function getSourceInfo(source: string) {
  const sources: Record<string, { label: string; color: string; icon: string }> = {
    'aliexpress': { label: 'AliExpress', color: 'bg-orange-500/20 text-orange-300 border-orange-500/30', icon: '[CART]' },
    'cj_dropshipping': { label: 'CJ', color: 'bg-blue-500/20 text-blue-300 border-blue-500/30', icon: '[PACKAGE]' },
    'tiktok_shop': { label: 'TikTok', color: 'bg-pink-500/20 text-pink-300 border-pink-500/30', icon: '' },
    'amazon_bestsellers': { label: 'Amazon', color: 'bg-yellow-500/20 text-yellow-300 border-yellow-500/30', icon: '[PACKAGE]' },
    'mock_data': { label: 'Demo', color: 'bg-gray-500/20 text-gray-300 border-gray-500/30', icon: '[TEST]' },
  };
  return sources[source] || { label: source, color: 'bg-white/10 text-white/60 border-white/20', icon: '[LINK]' };
}

// ============================================================================
// COMPONENT: Product Card - CLICKABLE, Oi Score Only
// ============================================================================

function ProductCard({ 
  product, 
  onClick
}: { 
  product: Product; 
  onClick: () => void;
}) {
  const [imageError, setImageError] = useState(false);
  const sourceInfo = getSourceInfo(product.source);
  const displayImage = product.ai_image_url || product.image_url;
  const hasAiImage = !!product.ai_image_url;

  return (
    <div 
      onClick={onClick}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => e.key === 'Enter' && onClick()}
      className="glass-card-static overflow-hidden hover:border-purple-500/40 hover:scale-[1.02] transition-all cursor-pointer group select-none"
    >
      {/* Image */}
      <div className="aspect-square bg-gradient-to-br from-purple-500/10 to-cyan-500/10 relative overflow-hidden pointer-events-none">
        {displayImage && !imageError ? (
          <img 
            src={displayImage} 
            alt={product.title}
            className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
            onError={() => setImageError(true)}
            draggable={false}
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
        
        {/* Oi Score Badge - THE ONLY SCORE */}
        <div className={`absolute top-3 right-3 px-3 py-2 rounded-xl bg-gradient-to-br ${getScoreBgColor(product.oi_score)} border backdrop-blur-sm`}>
          <div className="flex items-center gap-1.5">
            <Brain className="w-4 h-4 text-purple-400" />
            <span className={`text-lg font-bold ${getScoreColor(product.oi_score)}`}>{product.oi_score}</span>
          </div>
        </div>

        {/* Source Badge */}
        <div className={`absolute top-3 left-3 px-2 py-1 rounded-full border text-xs font-medium ${sourceInfo.color}`}>
          {sourceInfo.icon} {sourceInfo.label}
        </div>

        {/* Hover Overlay - Click Hint */}
        <div className="absolute inset-0 bg-purple-500/0 group-hover:bg-purple-500/10 transition-colors flex items-center justify-center opacity-0 group-hover:opacity-100">
          <div className="px-4 py-2 rounded-xl bg-black/80 backdrop-blur-sm text-white text-sm font-medium flex items-center gap-2">
            <Eye className="w-4 h-4" />
            View Details & Score Breakdown
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="p-4 pointer-events-none">
        <h3 className="text-white font-semibold mb-2 line-clamp-2 group-hover:text-purple-300 transition-colors text-sm">
          {product.title}
        </h3>
        
        {/* Pricing */}
        <div className="flex items-center gap-2 mb-2">
          <span className="text-white/50 text-sm">${product.cost_price.toFixed(2)}</span>
          <ArrowRight className="w-3 h-3 text-white/20" />
          <span className="text-green-400 font-medium">${product.suggested_price.toFixed(2)}</span>
          <span className="text-purple-400 font-bold ml-auto">+${product.profit.toFixed(2)}</span>
        </div>

        {/* Quick Stats */}
        <div className="flex items-center gap-3 text-xs text-white/50">
          {product.sales_count && product.sales_count > 0 && (
            <span className="flex items-center gap-1">
              <ShoppingCart className="w-3 h-3" />
              {product.sales_count.toLocaleString()}
            </span>
          )}
          {product.rating && (
            <span className="flex items-center gap-1">
              <Star className="w-3 h-3 text-yellow-400" />
              {product.rating.toFixed(1)}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// COMPONENT: Product Detail Panel - Full Oi Score Breakdown + Data Sources
// ============================================================================

function ProductDetailPanel({ 
  product, 
  onClose,
  onGenerateImage
}: { 
  product: Product; 
  onClose: () => void;
  onGenerateImage: (product: Product) => void;
}) {
  const [caption, setCaption] = useState('');
  const [generating, setGenerating] = useState(false);
  const [generatingImage, setGeneratingImage] = useState(false);
  const [copied, setCopied] = useState(false);
  const [showOriginal, setShowOriginal] = useState(false);
  
  const sourceInfo = getSourceInfo(product.source);
  const displayImage = showOriginal ? product.image_url : (product.ai_image_url || product.image_url);
  const hasAiImage = !!product.ai_image_url;
  const hasOriginalImage = !!product.image_url;

  useEffect(() => {
    setCaption(`${product.title}\n\nTrending in ${product.niche.replace(/_/g, ' ')}!\nSpecial Price: $${product.suggested_price.toFixed(2)}\n\nPremium Quality\nFast Shipping\n\nShop now!`);
  }, [product]);

  const handleGenerateImage = async () => {
    setGeneratingImage(true);
    await onGenerateImage(product);
    setGeneratingImage(false);
  };

  const generateCaption = async () => {
    setGenerating(true);
    try {
      const response = await apiCall<{ success: boolean; caption: string }>(
        `/api/oi/generate-caption`,
        {
          method: 'POST',
          body: JSON.stringify({ 
            product_title: product.title,
            product_niche: product.niche,
            price: product.suggested_price,
            tags: product.tags,
          }),
        }
      );
      if (response.success && response.caption) setCaption(response.caption);
    } catch (error) {
      console.error('Caption failed:', error);
    } finally {
      setGenerating(false);
    }
  };

  const copyCaption = () => {
    navigator.clipboard.writeText(caption);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDeploy = async () => {
    if (product.is_mock) {
      alert('[ERROR] Cannot deploy demo products. Connect APIs for real products.');
      return;
    }
    try {
      await apiCall('/api/deploy/product', {
        method: 'POST',
        body: JSON.stringify({ 
          product_id: product.id, 
          caption,
          use_ai_image: !!product.ai_image_url 
        }),
      });
      alert(`[SUCCESS] ${product.title} deployed to Shopify!`);
      onClose();
    } catch (error) {
      alert('[ERROR] Deploy failed.');
    }
  };

  // Score breakdown items
  const scoreBreakdown = [
    { key: 'demand_score', label: 'Demand', icon: TrendingUp, color: 'text-green-400', value: product.demand_score },
    { key: 'trend_score', label: 'Trend', icon: Zap, color: 'text-cyan-400', value: product.trend_score },
    { key: 'competition_score', label: 'Competition', icon: Target, color: 'text-yellow-400', value: product.competition_score },
    { key: 'viral_score', label: 'Viral Potential', icon: Sparkles, color: 'text-pink-400', value: product.viral_score },
    { key: 'profit_score', label: 'Profit Margin', icon: DollarSign, color: 'text-purple-400', value: product.profit_score },
  ].filter(item => item.value !== undefined);

  return (
    <>
      {/* Backdrop */}
      <div 
        className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40" 
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Panel */}
      <div 
        className="fixed right-0 top-0 h-full w-full max-w-2xl bg-[#0a0a0f]/95 backdrop-blur-xl border-l border-white/10 z-50 overflow-y-auto"
        style={{ animation: 'slideIn 0.3s ease-out' }}
        role="dialog"
        aria-modal="true"
      >
        {/* Header */}
        <div className="sticky top-0 bg-[#0a0a0f]/90 backdrop-blur-xl border-b border-white/10 p-4 flex items-center justify-between z-10">
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <Package className="w-5 h-5 text-purple-400" />
            Product Details
          </h2>
          <button 
            onClick={onClose} 
            className="p-2 rounded-xl hover:bg-white/10 text-white/60 hover:text-white transition-colors"
            aria-label="Close panel"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 space-y-6">
          {/* Product Image Section */}
          <div className="glass-card-static p-4">
            <div className="flex items-center justify-between mb-3">
              <h4 className="text-white font-semibold flex items-center gap-2">
                <Camera className="w-4 h-4 text-purple-400" />
                Product Image
              </h4>
              
              {/* Image Toggle */}
              {hasAiImage && hasOriginalImage && (
                <div className="flex items-center gap-1 bg-white/5 rounded-lg p-1">
                  <button
                    onClick={() => setShowOriginal(false)}
                    className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                      !showOriginal ? 'bg-purple-500/30 text-purple-300' : 'text-white/50 hover:text-white'
                    }`}
                  >
                    <Sparkles className="w-3 h-3 inline mr-1" />
                    AI
                  </button>
                  <button
                    onClick={() => setShowOriginal(true)}
                    className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                      showOriginal ? 'bg-orange-500/30 text-orange-300' : 'text-white/50 hover:text-white'
                    }`}
                  >
                    <Layers className="w-3 h-3 inline mr-1" />
                    Original
                  </button>
                </div>
              )}
            </div>
            
            {/* Image Display */}
            <div className="relative aspect-video rounded-xl overflow-hidden bg-gradient-to-br from-purple-500/10 to-cyan-500/10">
              {displayImage ? (
                <img src={displayImage} alt={product.title} className="w-full h-full object-contain" />
              ) : (
                <div className="w-full h-full flex items-center justify-center flex-col gap-3">
                  <ImageIcon className="w-16 h-16 text-white/20" />
                  <p className="text-white/40 text-sm">No image available</p>
                </div>
              )}
            </div>
            
            {/* Generate AI Image Button */}
            <button
              onClick={handleGenerateImage}
              disabled={generatingImage}
              className="w-full mt-3 py-3 rounded-xl bg-gradient-to-r from-purple-600/50 to-cyan-600/50 border border-purple-500/30 text-white font-medium hover:from-purple-600 hover:to-cyan-600 transition-all flex items-center justify-center gap-2"
            >
              {generatingImage ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Generating...
                </>
              ) : hasAiImage ? (
                <>
                  <RefreshCw className="w-4 h-4" />
                  Regenerate AI Image
                </>
              ) : (
                <>
                  <Wand2 className="w-4 h-4" />
                  Generate AI Product Image
                </>
              )}
            </button>
          </div>

          {/* Product Info + Oi Score */}
          <div className="glass-card-static p-4">
            <div className={`inline-flex items-center gap-1 px-2 py-1 rounded-full border text-xs font-medium mb-3 ${sourceInfo.color}`}>
              {sourceInfo.icon} {sourceInfo.label}
            </div>
            <h3 className="text-lg font-bold text-white mb-4">{product.title}</h3>
            
            {/* MAIN Oi Score */}
            <div className={`p-4 rounded-xl bg-gradient-to-br ${getScoreBgColor(product.oi_score)} border`}>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="p-3 rounded-xl bg-black/30">
                    <Brain className="w-6 h-6 text-purple-400" />
                  </div>
                  <div>
                    <p className="text-white/60 text-sm">Oi Score</p>
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
          <div className="glass-card-static p-4">
            <h4 className="text-white font-semibold mb-4 flex items-center gap-2">
              <Brain className="w-4 h-4 text-purple-400" />
              Score Breakdown
            </h4>
            
            {scoreBreakdown.length > 0 ? (
              <div className="space-y-3">
                {scoreBreakdown.map((item) => {
                  const Icon = item.icon;
                  const value = item.value || 0;
                  return (
                    <div key={item.key} className="flex items-center gap-3">
                      <div className="p-2 rounded-lg bg-white/5">
                        <Icon className={`w-4 h-4 ${item.color}`} />
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-white/70 text-sm">{item.label}</span>
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
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <p className="text-white/40 text-sm text-center py-4">
                Detailed breakdown not available for this product
              </p>
            )}

            {/* AI Recommendation */}
            {product.recommendation && (
              <div className="mt-4 p-3 rounded-xl bg-purple-500/10 border border-purple-500/20">
                <p className="text-purple-200 text-sm">{product.recommendation}</p>
              </div>
            )}

            {/* Strengths & Risks */}
            {(product.reasons?.length || product.risks?.length) ? (
              <div className="grid grid-cols-2 gap-4 mt-4">
                {product.reasons && product.reasons.length > 0 && (
                  <div>
                    <p className="text-green-400 text-sm font-medium mb-2 flex items-center gap-1">
                      <Check className="w-4 h-4" /> Strengths
                    </p>
                    <ul className="space-y-1">
                      {product.reasons.slice(0, 3).map((r, i) => (
                        <li key={i} className="text-white/60 text-sm">• {r}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {product.risks && product.risks.length > 0 && (
                  <div>
                    <p className="text-yellow-400 text-sm font-medium mb-2 flex items-center gap-1">
                      <AlertTriangle className="w-4 h-4" /> Risks
                    </p>
                    <ul className="space-y-1">
                      {product.risks.slice(0, 3).map((r, i) => (
                        <li key={i} className="text-white/60 text-sm">• {r}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            ) : null}
          </div>

          {/* Data Sources */}
          <div className="glass-card-static p-4">
            <h4 className="text-white font-semibold mb-3 flex items-center gap-2">
              <Database className="w-4 h-4 text-purple-400" />
              Data Sources
            </h4>
            {product.data_sources && Object.keys(product.data_sources).length > 0 ? (
              <div className="flex flex-wrap gap-2">
                {Object.entries(product.data_sources).map(([source, data]: [string, any]) => (
                  <div key={source} className={`px-3 py-2 rounded-lg border text-xs flex items-center gap-2 ${
                    data?.available ? 'bg-green-500/10 border-green-500/30 text-green-300' : 'bg-white/5 border-white/10 text-white/40'
                  }`}>
                    {source === 'google_trends' && '[TREND]'}
                    {source === 'tiktok' && ''}
                    {source === 'amazon' && '[PACKAGE]'}
                    {source === 'aliexpress' && '[CART]'}
                    {source === 'cj_dropshipping' && '[PACKAGE]'}
                    {source === 'mock' && '[TEST]'}
                    <span className="capitalize">{source.replace(/_/g, ' ')}</span>
                    {data?.available && <Check className="w-3 h-3" />}
                  </div>
                ))}
              </div>
            ) : (
              <div className="flex flex-wrap gap-2">
                <div className="px-3 py-2 rounded-lg border bg-orange-500/10 border-orange-500/30 text-orange-300 text-xs flex items-center gap-2">
                  [CART] <span>AliExpress</span> <Check className="w-3 h-3" />
                </div>
                <div className="px-3 py-2 rounded-lg border bg-white/5 border-white/10 text-white/40 text-xs">
                  [TREND] Google Trends
                </div>
                <div className="px-3 py-2 rounded-lg border bg-white/5 border-white/10 text-white/40 text-xs">
                   TikTok
                </div>
              </div>
            )}
          </div>

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

          {/* Supplier Links */}
          <div className="glass-card-static p-4">
            <h4 className="text-white font-semibold mb-3 flex items-center gap-2">
              <Link2 className="w-4 h-4 text-purple-400" />
              Supplier Link
            </h4>
            {product.affiliate_url ? (
              <a 
                href={product.affiliate_url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center justify-between p-3 rounded-xl bg-orange-500/10 border border-orange-500/20 hover:bg-orange-500/20 transition-colors group"
              >
                <span className="text-orange-300 flex items-center gap-2">
                  [CART] View on AliExpress
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
          <div className="glass-card-static p-4">
            <h4 className="text-white font-semibold mb-3 flex items-center gap-2">
              <Rocket className="w-4 h-4 text-purple-400" />
              Deploy to Shopify
            </h4>
            
            {/* Caption */}
            <div className="mb-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-white/60 text-sm">Product Caption</span>
                <button
                  onClick={generateCaption}
                  disabled={generating}
                  className="text-purple-400 text-sm hover:text-purple-300 flex items-center gap-1"
                >
                  {generating ? <Loader2 className="w-3 h-3 animate-spin" /> : <Sparkles className="w-3 h-3" />}
                  {generating ? 'Generating...' : 'AI Generate'}
                </button>
              </div>
              <div className="relative">
                <textarea
                  value={caption}
                  onChange={(e) => setCaption(e.target.value)}
                  className="w-full h-28 p-3 rounded-xl bg-white/5 border border-white/10 text-white placeholder-white/30 resize-none focus:outline-none focus:border-purple-500/50 text-sm"
                />
                <button
                  onClick={copyCaption}
                  className="absolute top-2 right-2 p-2 rounded-lg bg-white/10 hover:bg-white/20 text-white/60 hover:text-white"
                >
                  {copied ? <Check className="w-4 h-4 text-green-400" /> : <Copy className="w-4 h-4" />}
                </button>
              </div>
            </div>

            {/* Deploy Button */}
            <button
              onClick={handleDeploy}
              disabled={product.is_mock}
              className="w-full py-4 rounded-xl bg-gradient-to-r from-purple-600 to-cyan-600 text-white font-bold hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-3"
            >
              {product.is_mock ? (
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
          {product.tags && product.tags.length > 0 && (
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
// MAIN COMPONENT
// ============================================================================

export default function Products() {
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [filter, setFilter] = useState('trending');
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [hasMockData, setHasMockData] = useState(false);
  const [imageServiceStatus, setImageServiceStatus] = useState<any>(null);

  useEffect(() => {
    loadProducts();
    checkImageService();
  }, [filter]);

  const checkImageService = async () => {
    try {
      const status = await apiCall<any>('/api/images/status');
      setImageServiceStatus(status);
    } catch (error) {
      setImageServiceStatus({ available: false });
    }
  };

  const loadProducts = async () => {
    setLoading(true);
    try {
      let niche = filter === 'trending' ? 'smart_home' : filter === 'recommended' ? 'tech' : 'fitness';
      const response = await apiCall<any>(`/api/discovery/quick/${niche}?count=20&include_ai_images=true`);
      const data = response.products || response.data || response || [];
      const normalized = data.map((p: any) => normalizeProduct(p, niche));
      setProducts(normalized);
      setHasMockData(normalized.some((p: Product) => p.is_mock));
    } catch (error) {
      console.error('Load failed:', error);
      setProducts([]);
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;
    setLoading(true);
    try {
      const response = await apiCall<any>(`/api/discovery/quick/${searchQuery.trim()}?count=20&include_ai_images=true`);
      const data = response.products || response.data || response || [];
      const normalized = data.map((p: any) => normalizeProduct(p, searchQuery));
      setProducts(normalized);
      setHasMockData(normalized.some((p: Product) => p.is_mock));
    } catch (error) {
      console.error('Search failed:', error);
    } finally {
      setLoading(false);
    }
  };

  const generateImageForProduct = useCallback(async (product: Product) => {
    try {
      const response = await apiCall<any>('/api/images/generate', {
        method: 'POST',
        body: JSON.stringify({
          product_title: product.title,
          niche: product.niche,
          original_image_url: product.image_url,
          tags: product.tags
        })
      });
      
      if (response.success && response.ai_image_url) {
        setProducts(prev => prev.map(p => 
          p.id === product.id 
            ? { ...p, ai_image_url: response.ai_image_url, image_source: response.source }
            : p
        ));
        
        if (selectedProduct?.id === product.id) {
          setSelectedProduct(prev => prev ? { 
            ...prev, 
            ai_image_url: response.ai_image_url,
            image_source: response.source 
          } : null);
        }
      }
    } catch (error) {
      console.error('Image generation failed:', error);
      alert('Image generation failed. Check if OPENAI_API_KEY is configured.');
    }
  }, [selectedProduct]);

  const openProductDetail = useCallback((product: Product) => {
    setSelectedProduct(product);
  }, []);

  return (
    <div className="animate-fade-in space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Sparkles className="w-7 h-7 text-purple-400" />
            Product Discovery
          </h1>
          <p className="text-white/60 text-sm mt-1">
            {products.length} products • Click any card for Oi Score breakdown
          </p>
        </div>
        <button 
          onClick={loadProducts}
          disabled={loading}
          className="p-2 rounded-xl text-white/40 hover:text-white/80 hover:bg-white/[0.04]"
        >
          <RefreshCw className={`w-5 h-5 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* Mock Warning */}
      {hasMockData && (
        <div className="p-4 rounded-xl bg-yellow-500/10 border border-yellow-500/30 flex items-center gap-3">
          <AlertTriangle className="w-5 h-5 text-yellow-400 flex-shrink-0" />
          <div>
            <p className="text-yellow-200 font-medium">Demo Products Shown</p>
            <p className="text-yellow-200/70 text-sm">APIs returned empty. Check backend logs.</p>
          </div>
        </div>
      )}

      {/* Search & Filters */}
      <div className="glass-card-static p-4">
        <div className="flex flex-col md:flex-row gap-4">
          <div className="flex-1 flex gap-2">
            <div className="flex-1 relative">
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-white/40" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                placeholder="Search products or niches..."
                className="w-full pl-12 pr-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white placeholder-white/40 focus:outline-none focus:border-purple-500/50"
              />
            </div>
            <button onClick={handleSearch} className="px-6 py-3 rounded-xl bg-gradient-to-r from-purple-600 to-cyan-600 text-white font-semibold hover:opacity-90 transition-opacity">
              <Search className="w-4 h-4" />
            </button>
          </div>
          <div className="flex gap-2">
            {['trending', 'recommended', 'high-profit'].map((f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`px-4 py-2 rounded-xl text-sm font-medium transition-all ${
                  filter === f
                    ? 'bg-purple-500/20 border border-purple-500/30 text-purple-300'
                    : 'bg-white/5 border border-white/10 text-white/60 hover:text-white hover:bg-white/10'
                }`}
              >
                {f === 'trending' && <TrendingUp className="w-4 h-4 inline mr-1" />}
                {f === 'recommended' && <Filter className="w-4 h-4 inline mr-1" />}
                {f === 'high-profit' && <BarChart3 className="w-4 h-4 inline mr-1" />}
                {f.replace('-', ' ').replace(/\b\w/g, l => l.toUpperCase())}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Grid */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {[...Array(8)].map((_, i) => (
            <div key={i} className="glass-card-static overflow-hidden animate-pulse">
              <div className="aspect-square bg-white/5" />
              <div className="p-4 space-y-3">
                <div className="h-4 bg-white/10 rounded w-3/4" />
                <div className="h-3 bg-white/10 rounded w-1/2" />
              </div>
            </div>
          ))}
        </div>
      ) : products.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {products.map((product) => (
            <ProductCard 
              key={product.id} 
              product={product} 
              onClick={() => openProductDetail(product)}
            />
          ))}
        </div>
      ) : (
        <div className="text-center py-20">
          <Package className="w-16 h-16 text-white/20 mx-auto mb-4" />
          <h3 className="text-xl font-semibold text-white mb-2">No products found</h3>
          <p className="text-white/50">Try a different search or filter</p>
        </div>
      )}

      {/* Detail Panel */}
      {selectedProduct && (
        <ProductDetailPanel
          product={selectedProduct}
          onClose={() => setSelectedProduct(null)}
          onGenerateImage={generateImageForProduct}
        />
      )}
    </div>
  );
}
