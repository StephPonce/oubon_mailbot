/**
 * Ospra Intelligence - Unified Products Page V2
 * 
 * NOW SHOWS REAL INTELLIGENCE:
 * - Cross-source validation indicators
 * - Live price badges
 * - Trend direction from Google Trends
 * - Confidence scores
 * - Score breakdown
 */

import { useState, useEffect, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  Package,
  Search,
  Filter,
  TrendingUp,
  TrendingDown,
  Activity,
  Brain,
  Rocket,
  RefreshCw,
  ChevronDown,
  X,
  Loader2,
  ExternalLink,
  Zap,
  Grid3X3,
  List,
  CheckCircle2,
  AlertTriangle,
  Globe,
  ShoppingBag,
  BarChart3,
  DollarSign,
  Star,
  Eye,
} from 'lucide-react';

import {
  useProducts,
  useNiches,
  useDeployToShopify,
  useAnalyzeProduct,
} from '../hooks/useData';
import { productsAPI } from '../services/api';
import type { Product, ProductFilters } from '../services/api';
import { Top20Rankings } from '../components/rankings/Top20Rankings';

// =============================================================================
// CONSTANTS & UTILITIES
// =============================================================================

const SORT_OPTIONS = [
  { value: 'score', label: 'Highest Score' },
  { value: 'profit', label: 'Highest Profit' },
  { value: 'trend', label: 'Trending' },
  { value: 'newest', label: 'Newest' },
];

function formatNiche(niche: string): string {
  if (!niche) return '';
  return niche.split('_').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ');
}

function sanitizeImageUrl(url?: string, productName?: string): string {
  if (!url || url.trim() === '') {
    return getPlaceholder(productName);
  }
  let cleanUrl = url.replace(/^http:\/\//i, 'https://');
  if (cleanUrl.includes('alicdn.com') || cleanUrl.includes('aliexpress-media')) {
    cleanUrl = cleanUrl.split('_')[0];
    if (!cleanUrl.includes('?')) {
      cleanUrl = cleanUrl + '_400x400.jpg';
    }
  }
  return cleanUrl;
}

function getPlaceholder(name?: string): string {
  const text = encodeURIComponent(name?.substring(0, 20) || 'Product');
  return `https://placehold.co/400x400/1a1a2e/eaeaea?text=${text}`;
}

// Get recommendation badge styling
function getRecommendationStyle(rec?: string) {
  switch (rec) {
    case 'STRONG_BUY': return 'bg-gradient-to-r from-green-500 to-emerald-500 text-white';
    case 'BUY': return 'bg-gradient-to-r from-cyan-500 to-blue-500 text-white';
    case 'HOLD': return 'bg-gradient-to-r from-amber-500 to-yellow-500 text-black';
    default: return 'bg-gradient-to-r from-gray-500 to-gray-600 text-white';
  }
}

// =============================================================================
// INTELLIGENCE BADGE - Shows data sources that validated this product
// =============================================================================

interface IntelligenceBadgeProps {
  product: Product;
}

function IntelligenceBadge({ product }: IntelligenceBadgeProps) {
  const sources = product.data_sources || 1;
  const confidence = product.confidence || (sources * 30 + 10);
  const trendDirection = product.trend_direction;
  const livePricing = product.live_price !== false;
  
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {/* Live Price Indicator */}
      {livePricing && (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-green-500/10 text-green-600 text-[10px] font-medium">
          <DollarSign className="w-3 h-3" />
          Live
        </span>
      )}
      
      {/* Trend Direction */}
      {trendDirection && trendDirection !== 'unknown' && (
        <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium ${
          trendDirection === 'rising' ? 'bg-green-500/10 text-green-600' :
          trendDirection === 'declining' ? 'bg-red-500/10 text-red-600' :
          'bg-gray-500/10 text-gray-600'
        }`}>
          {trendDirection === 'rising' ? <TrendingUp className="w-3 h-3" /> :
           trendDirection === 'declining' ? <TrendingDown className="w-3 h-3" /> :
           <Activity className="w-3 h-3" />}
          {trendDirection}
        </span>
      )}
      
      {/* Data Sources Count */}
      {sources > 1 && (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-purple-500/10 text-purple-600 text-[10px] font-medium">
          <Eye className="w-3 h-3" />
          {sources} sources
        </span>
      )}
      
      {/* Confidence */}
      {confidence > 50 && (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-cyan-500/10 text-cyan-600 text-[10px] font-medium">
          {confidence}% conf
        </span>
      )}
    </div>
  );
}

// =============================================================================
// PRODUCT CARD COMPONENT - Now with Intelligence Display
// =============================================================================

interface ProductCardProps {
  product: Product;
  viewMode: 'grid' | 'list';
  onAnalyze: (product: Product) => void;
  onDeploy: (product: Product) => void;
  onSelect: (product: Product) => void;
  isSelected: boolean;
  isDeploying: boolean;
  isAnalyzing: boolean;
}

function ProductCard({
  product,
  viewMode,
  onAnalyze,
  onDeploy,
  onSelect,
  isSelected,
  isDeploying,
  isAnalyzing,
}: ProductCardProps) {
  const getScoreColor = (score: number) => {
    if (score >= 7.5) return 'bg-gradient-to-br from-green-500 to-emerald-600 text-white';
    if (score >= 6) return 'bg-gradient-to-br from-cyan-500 to-blue-600 text-white';
    if (score >= 4) return 'bg-gradient-to-br from-amber-500 to-orange-600 text-white';
    return 'bg-gradient-to-br from-gray-500 to-gray-600 text-white';
  };

  const score = product.score || 0;
  const profit = product.profit || product.estimated_profit || 0;
  const cost = product.cost || 0;
  const margin = product.profit_margin || 0;
  const orders = product.orders || 0;
  const recommendation = product.recommendation;

  if (viewMode === 'list') {
    return (
      <div 
        className={`glass-card p-4 flex items-center gap-4 cursor-pointer transition-all ${
          isSelected ? 'ring-2 ring-accent' : 'hover:shadow-md'
        }`}
        onClick={() => onSelect(product)}
      >
        {/* Image */}
        <div className="w-20 h-20 rounded-lg bg-black/5 flex-shrink-0 overflow-hidden relative">
          <img
            src={sanitizeImageUrl(product.image_url, product.name)}
            alt={product.name}
            className="w-full h-full object-cover"
            crossOrigin="anonymous"
            referrerPolicy="no-referrer"
            loading="lazy"
            onError={(e) => {
              const target = e.currentTarget;
              if (!target.dataset.retried) {
                target.dataset.retried = 'true';
                target.src = getPlaceholder(product.name);
              }
            }}
          />
          {orders > 0 && (
            <div className="absolute bottom-1 right-1 px-1.5 py-0.5 rounded bg-black/70 text-white text-[10px]">
              {orders > 1000 ? `${(orders/1000).toFixed(1)}k` : orders} sold
            </div>
          )}
        </div>

        {/* Info */}
        <div className="flex-1 min-w-0">
          <h3 className="text-sm font-medium text-primary line-clamp-1">{product.name}</h3>
          <div className="flex items-center gap-2 mt-1 flex-wrap">
            <span className="badge badge-blue">{formatNiche(product.niche)}</span>
            {recommendation && (
              <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${getRecommendationStyle(recommendation)}`}>
                {recommendation.replace('_', ' ')}
              </span>
            )}
          </div>
          <div className="mt-1">
            <IntelligenceBadge product={product} />
          </div>
        </div>

        {/* Stats */}
        <div className="flex items-center gap-6 flex-shrink-0">
          <div className="text-center">
            <div className={`text-lg font-bold px-3 py-1 rounded-lg ${getScoreColor(score)}`}>
              {score.toFixed(1)}
            </div>
            <div className="text-xs text-tertiary mt-1">Score</div>
          </div>
          <div className="text-center">
            <div className="text-lg font-semibold text-green-600">${profit.toFixed(2)}</div>
            <div className="text-xs text-tertiary">Profit</div>
          </div>
          <div className="text-center">
            <div className="text-lg font-semibold text-primary">{margin.toFixed(0)}%</div>
            <div className="text-xs text-tertiary">Margin</div>
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2 flex-shrink-0">
          {(product.aliexpress_url || product.url || product.supplier_url) && (
            <a
              href={product.aliexpress_url || product.supplier_url || product.url}
              target="_blank"
              rel="noopener noreferrer"
              className="btn-ghost text-xs"
              onClick={(e) => e.stopPropagation()}
              title="View on AliExpress"
            >
              <ExternalLink className="w-4 h-4" />
            </a>
          )}
          <button
            className="btn-ghost text-xs"
            onClick={(e) => { e.stopPropagation(); onAnalyze(product); }}
            disabled={isAnalyzing}
          >
            {isAnalyzing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Brain className="w-4 h-4" />}
          </button>
          <button
            className="btn-primary text-xs"
            onClick={(e) => { e.stopPropagation(); onDeploy(product); }}
            disabled={isDeploying}
          >
            {isDeploying ? <Loader2 className="w-4 h-4 animate-spin" /> : <Rocket className="w-4 h-4" />}
            <span>Deploy</span>
          </button>
        </div>
      </div>
    );
  }

  // Grid view
  return (
    <div 
      className={`glass-card overflow-hidden cursor-pointer transition-all ${
        isSelected ? 'ring-2 ring-accent' : 'hover:shadow-lg hover:-translate-y-1'
      }`}
      onClick={() => onSelect(product)}
    >
      {/* Image */}
      <div className="relative h-48 bg-gradient-to-br from-black/5 to-transparent">
        <img
          src={sanitizeImageUrl(product.image_url, product.name)}
          alt={product.name}
          className="w-full h-full object-cover"
          crossOrigin="anonymous"
          referrerPolicy="no-referrer"
          loading="lazy"
          onError={(e) => {
            const target = e.currentTarget;
            if (!target.dataset.retried) {
              target.dataset.retried = 'true';
              target.src = getPlaceholder(product.name);
            }
          }}
        />

        {/* Score Badge - Top Right */}
        <div className={`absolute top-3 right-3 px-2.5 py-1.5 rounded-lg text-sm font-bold shadow-lg ${getScoreColor(score)}`}>
          {score.toFixed(1)}
        </div>

        {/* Recommendation Badge - Top Left */}
        {recommendation && (
          <div className={`absolute top-3 left-3 px-2 py-1 rounded-lg text-xs font-bold shadow-lg ${getRecommendationStyle(recommendation)}`}>
            {recommendation.replace('_', ' ')}
          </div>
        )}

        {/* Orders Badge - Bottom Right */}
        {orders > 0 && (
          <div className="absolute bottom-3 right-3 flex items-center gap-1 px-2 py-1 rounded-lg bg-black/70 text-white text-xs backdrop-blur-sm">
            <ShoppingBag className="w-3 h-3" />
            {orders > 1000 ? `${(orders/1000).toFixed(1)}k` : orders}
          </div>
        )}

        {/* Selection Indicator */}
        {isSelected && (
          <div className="absolute inset-0 bg-accent/10 flex items-center justify-center">
            <CheckCircle2 className="w-12 h-12 text-accent" />
          </div>
        )}
      </div>

      {/* Content */}
      <div className="p-4">
        <h3 className="text-sm font-medium text-primary line-clamp-2 mb-2">{product.name}</h3>

        <div className="flex items-center gap-2 mb-2 flex-wrap">
          <span className="badge badge-blue">{formatNiche(product.niche)}</span>
        </div>

        {/* Intelligence Badges */}
        <div className="mb-3">
          <IntelligenceBadge product={product} />
        </div>

        {/* AI Reason */}
        {product.ai_reason && (
          <div className="p-2 rounded-lg bg-gradient-to-r from-purple-500/10 to-cyan-500/10 border border-purple-500/20 mb-3">
            <div className="flex items-start gap-2">
              <Brain className="w-3.5 h-3.5 text-purple-600 mt-0.5 flex-shrink-0" />
              <p className="text-xs text-secondary line-clamp-2">{product.ai_reason}</p>
            </div>
          </div>
        )}

        {/* Stats Grid */}
        <div className="grid grid-cols-3 gap-2 mb-3">
          <div className="text-center p-2 rounded-lg bg-green-500/10">
            <div className="text-sm font-bold text-green-600">${profit.toFixed(2)}</div>
            <div className="text-[10px] text-tertiary">Profit</div>
          </div>
          <div className="text-center p-2 rounded-lg bg-black/5">
            <div className="text-sm font-semibold text-primary">${cost.toFixed(2)}</div>
            <div className="text-[10px] text-tertiary">Cost</div>
          </div>
          <div className="text-center p-2 rounded-lg bg-black/5">
            <div className="text-sm font-semibold text-primary">{margin.toFixed(0)}%</div>
            <div className="text-[10px] text-tertiary">Margin</div>
          </div>
        </div>

        {/* Actions */}
        <div className="flex flex-col gap-2">
          {(product.aliexpress_url || product.url || product.supplier_url) && (
            <a
              href={product.aliexpress_url || product.supplier_url || product.url}
              target="_blank"
              rel="noopener noreferrer"
              className="btn-ghost text-xs justify-center w-full"
              onClick={(e) => e.stopPropagation()}
            >
              <ExternalLink className="w-4 h-4" />
              <span>View on AliExpress</span>
            </a>
          )}
          <div className="flex items-center gap-2">
            <button
              className="flex-1 btn-ghost text-xs justify-center"
              onClick={(e) => { e.stopPropagation(); onAnalyze(product); }}
              disabled={isAnalyzing}
            >
              {isAnalyzing ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <>
                  <Brain className="w-4 h-4" />
                  <span>Analyze</span>
                </>
              )}
            </button>
            <button
              className="flex-1 btn-primary text-xs justify-center"
              onClick={(e) => { e.stopPropagation(); onDeploy(product); }}
              disabled={isDeploying}
            >
              {isDeploying ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <>
                  <Rocket className="w-4 h-4" />
                  <span>Deploy</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// PRODUCT DETAIL MODAL - Full Intelligence Display
// =============================================================================

interface ProductDetailModalProps {
  product: Product | null;
  analysis: unknown | null;
  isAnalyzing: boolean;
  onClose: () => void;
  onAnalyze: (product: Product) => void;
  onDeploy: (product: Product) => void;
  isDeploying: boolean;
}

function ProductDetailModal({
  product,
  analysis,
  isAnalyzing,
  onClose,
  onAnalyze,
  onDeploy,
  isDeploying,
}: ProductDetailModalProps) {
  if (!product) return null;

  const score = product.score || 0;
  const profit = product.profit || product.estimated_profit || 0;
  const cost = product.cost || 0;
  const margin = product.profit_margin || 0;
  const orders = product.orders || 0;
  const rating = product.rating || 0;
  const recommendation = product.recommendation;
  const confidence = product.confidence || 50;
  const dataSources = product.data_sources || 1;
  const trendDirection = product.trend_direction;
  const trendScore = product.trend_score || 0;
  const scoreBreakdown = product.score_breakdown;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
      <div className="glass-card max-w-3xl w-full max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-start justify-between p-6 border-b border-black/10">
          <div className="flex items-start gap-4">
            <div className="w-28 h-28 rounded-xl bg-black/5 overflow-hidden flex-shrink-0 shadow-lg">
              {product.image_url ? (
                <img 
                  src={sanitizeImageUrl(product.image_url, product.name)} 
                  alt={product.name} 
                  className="w-full h-full object-cover" 
                />
              ) : (
                <div className="w-full h-full flex items-center justify-center">
                  <Package className="w-10 h-10 text-tertiary" />
                </div>
              )}
            </div>
            <div>
              <h2 className="text-lg font-semibold text-primary">{product.name}</h2>
              <div className="flex items-center gap-2 mt-2 flex-wrap">
                <span className="badge badge-blue">{formatNiche(product.niche)}</span>
                {recommendation && (
                  <span className={`px-2 py-1 rounded-lg text-xs font-bold ${getRecommendationStyle(recommendation)}`}>
                    {recommendation.replace('_', ' ')}
                  </span>
                )}
              </div>
              <div className="mt-2">
                <IntelligenceBadge product={product} />
              </div>
              {(product.aliexpress_url || product.url || product.supplier_url) && (
                <a
                  href={product.aliexpress_url || product.supplier_url || product.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-sm text-cyan-600 hover:text-cyan-500 mt-2"
                >
                  <ExternalLink className="w-3.5 h-3.5" />
                  View on AliExpress
                </a>
              )}
            </div>
          </div>
          <button onClick={onClose} className="p-2 hover:bg-black/5 rounded-lg">
            <X className="w-5 h-5 text-tertiary" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6">
          {/* Main Score Card */}
          <div className="p-4 rounded-xl bg-gradient-to-r from-purple-600/20 via-cyan-600/20 to-green-600/20 border border-purple-500/20">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs text-tertiary">Ospra Intelligence Score</p>
                <div className="flex items-baseline gap-2 mt-1">
                  <span className="text-4xl font-bold text-primary">{score.toFixed(1)}</span>
                  <span className="text-xl text-tertiary">/10</span>
                </div>
                <p className="text-sm text-secondary mt-1">{confidence}% confidence • {dataSources} data source{dataSources > 1 ? 's' : ''}</p>
              </div>
              {recommendation && (
                <div className={`px-4 py-2 rounded-xl text-lg font-bold shadow-lg ${getRecommendationStyle(recommendation)}`}>
                  {recommendation.replace('_', ' ')}
                </div>
              )}
            </div>
          </div>

          {/* Stats Grid */}
          <div className="grid grid-cols-5 gap-3">
            <div className="text-center p-3 rounded-xl bg-green-500/10 border border-green-500/20">
              <DollarSign className="w-5 h-5 text-green-600 mx-auto mb-1" />
              <div className="text-xl font-bold text-green-600">${profit.toFixed(2)}</div>
              <div className="text-xs text-tertiary">Profit</div>
            </div>
            <div className="text-center p-3 rounded-xl bg-black/5">
              <ShoppingBag className="w-5 h-5 text-primary mx-auto mb-1" />
              <div className="text-xl font-bold text-primary">${cost.toFixed(2)}</div>
              <div className="text-xs text-tertiary">Cost</div>
            </div>
            <div className="text-center p-3 rounded-xl bg-black/5">
              <BarChart3 className="w-5 h-5 text-primary mx-auto mb-1" />
              <div className="text-xl font-bold text-primary">{margin.toFixed(0)}%</div>
              <div className="text-xs text-tertiary">Margin</div>
            </div>
            <div className="text-center p-3 rounded-xl bg-black/5">
              <ShoppingBag className="w-5 h-5 text-primary mx-auto mb-1" />
              <div className="text-xl font-bold text-primary">{orders > 1000 ? `${(orders/1000).toFixed(1)}k` : orders}</div>
              <div className="text-xs text-tertiary">Orders</div>
            </div>
            <div className="text-center p-3 rounded-xl bg-black/5">
              <Star className="w-5 h-5 text-amber-500 mx-auto mb-1" />
              <div className="text-xl font-bold text-primary">{rating.toFixed(1)}</div>
              <div className="text-xs text-tertiary">Rating</div>
            </div>
          </div>

          {/* Trend Info */}
          {trendDirection && trendDirection !== 'unknown' && (
            <div className={`flex items-center gap-3 p-4 rounded-xl border ${
              trendDirection === 'rising' ? 'bg-green-500/10 border-green-500/20' :
              trendDirection === 'declining' ? 'bg-red-500/10 border-red-500/20' :
              'bg-gray-500/10 border-gray-500/20'
            }`}>
              {trendDirection === 'rising' ? <TrendingUp className="w-6 h-6 text-green-600" /> :
               trendDirection === 'declining' ? <TrendingDown className="w-6 h-6 text-red-600" /> :
               <Activity className="w-6 h-6 text-gray-600" />}
              <div>
                <p className={`font-semibold ${
                  trendDirection === 'rising' ? 'text-green-600' :
                  trendDirection === 'declining' ? 'text-red-600' :
                  'text-gray-600'
                }`}>
                  {trendDirection === 'rising' ? '📈 Rising Trend' :
                   trendDirection === 'declining' ? '📉 Declining Trend' :
                   '📊 Stable Trend'}
                </p>
                <p className="text-sm text-secondary">Google Trends score: {trendScore}</p>
              </div>
            </div>
          )}

          {/* Score Breakdown */}
          {scoreBreakdown && (
            <div>
              <h4 className="text-sm font-semibold text-primary mb-3 flex items-center gap-2">
                <Brain className="w-4 h-4 text-purple-600" />
                Score Breakdown
              </h4>
              <div className="grid grid-cols-5 gap-2">
                {Object.entries(scoreBreakdown).map(([key, value]) => (
                  <div key={key} className="text-center p-2 rounded-lg bg-purple-500/10">
                    <div className="text-sm font-bold text-purple-600">{(value as number).toFixed(2)}</div>
                    <div className="text-[10px] text-tertiary capitalize">{key.replace('_', ' ')}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* AI Reason */}
          {product.ai_reason && (
            <div className="p-4 rounded-xl bg-gradient-to-r from-purple-500/10 to-cyan-500/10 border border-purple-500/20">
              <div className="flex items-center gap-2 mb-2">
                <Brain className="w-4 h-4 text-purple-600" />
                <span className="text-sm font-medium text-purple-600">AI Intelligence Summary</span>
              </div>
              <p className="text-sm text-secondary leading-relaxed">{product.ai_reason}</p>
            </div>
          )}

          {/* Deep Analysis Result */}
          {analysis && (
            <div className="space-y-4">
              <div className="flex items-center justify-between p-4 rounded-xl bg-gradient-to-r from-purple-600/20 to-cyan-600/20 border border-purple-500/20">
                <div>
                  <p className="text-xs text-tertiary">Deep Analysis Score</p>
                  <div className="flex items-baseline gap-1">
                    <span className="text-3xl font-bold text-primary">{(analysis as any).score?.toFixed(1) || score.toFixed(1)}</span>
                    <span className="text-lg text-tertiary">/10</span>
                  </div>
                </div>
                <div className={`px-3 py-1.5 rounded-lg text-sm font-bold ${getRecommendationStyle((analysis as any).recommendation)}`}>
                  {((analysis as any).recommendation || 'PENDING').replace('_', ' ')}
                </div>
              </div>

              {(analysis as any).success_prediction && (
                <div className="flex items-center gap-3 p-3 rounded-xl bg-cyan-500/10 border border-cyan-500/20">
                  <TrendingUp className="w-5 h-5 text-cyan-600" />
                  <span className="text-sm text-secondary">Success Prediction: </span>
                  <span className="text-cyan-600 font-bold">{(analysis as any).success_prediction}</span>
                </div>
              )}

              {(analysis as any).analysis && (
                <div className="p-4 rounded-xl bg-black/5">
                  <p className="text-sm text-secondary leading-relaxed">{(analysis as any).analysis}</p>
                </div>
              )}

              {(analysis as any).reasoning?.length > 0 && (
                <div>
                  <h4 className="text-sm font-semibold text-primary mb-2 flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4 text-green-600" />
                    Why This Product Wins
                  </h4>
                  <div className="space-y-2">
                    {(analysis as any).reasoning.map((reason: string, i: number) => (
                      <div key={i} className="flex gap-2 p-3 rounded-lg bg-green-500/10 border border-green-500/20">
                        <span className="text-green-600 font-bold">✓</span>
                        <p className="text-sm text-secondary">{reason}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {(analysis as any).risks?.length > 0 && (
                <div>
                  <h4 className="text-sm font-semibold text-primary mb-2 flex items-center gap-2">
                    <AlertTriangle className="w-4 h-4 text-amber-600" />
                    Risks to Consider
                  </h4>
                  <div className="space-y-2">
                    {(analysis as any).risks.map((risk: string, i: number) => (
                      <div key={i} className="flex gap-2 p-3 rounded-lg bg-amber-500/10 border border-amber-500/20">
                        <span className="text-amber-600 font-bold">!</span>
                        <p className="text-sm text-secondary">{risk}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Analyze Button */}
          {!analysis && !isAnalyzing && (
            <button
              className="w-full py-4 bg-gradient-to-r from-purple-600 to-cyan-600 text-white rounded-xl font-semibold hover:from-purple-500 hover:to-cyan-500 transition-all flex items-center justify-center gap-2 shadow-lg"
              onClick={() => onAnalyze(product)}
            >
              <Brain className="w-5 h-5" />
              Run Deep Analysis
            </button>
          )}

          {isAnalyzing && (
            <div className="flex items-center justify-center gap-3 py-8">
              <Loader2 className="w-6 h-6 text-purple-600 animate-spin" />
              <span className="text-secondary">Analyzing product with AI...</span>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between p-6 border-t border-black/10">
          <button
            className="btn-ghost"
            onClick={() => onAnalyze(product)}
            disabled={isAnalyzing}
          >
            {isAnalyzing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Brain className="w-4 h-4" />}
            <span>{analysis ? 'Re-Analyze' : 'Deep Analysis'}</span>
          </button>
          <button
            className="btn-primary"
            onClick={() => onDeploy(product)}
            disabled={isDeploying}
          >
            {isDeploying ? <Loader2 className="w-4 h-4 animate-spin" /> : <Rocket className="w-4 h-4" />}
            <span>Deploy to Shopify</span>
          </button>
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// MAIN COMPONENT
// =============================================================================

export default function UnifiedProductsPage() {
  const [searchParams, setSearchParams] = useSearchParams();

  // State
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [filters, setFilters] = useState<ProductFilters>({
    niches: undefined,
    min_score: 0,
    source: undefined,
    sort_by: 'score',
    sort_order: 'desc',
    limit: 50,
  });
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedProducts, setSelectedProducts] = useState<Set<string>>(new Set());
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [analysisResult, setAnalysisResult] = useState<unknown>(null);
  const [isDiscovering, setIsDiscovering] = useState(false);
  const [showFilters, setShowFilters] = useState(false);

  // Mutation hooks
  const { deploy, isLoading: isDeploying } = useDeployToShopify();
  const { analyze, isLoading: isAnalyzing } = useAnalyzeProduct();

  // Track which products are being processed
  const [deployingProductId, setDeployingProductId] = useState<string | null>(null);
  const [analyzingProductId, setAnalyzingProductId] = useState<string | null>(null);

  // Data hooks
  const { data: productsData, isLoading: productsLoading, refetch: refetchProducts } = useProducts(filters);
  const { data: nichesData } = useNiches();

  const products = productsData?.products || [];
  const niches = nichesData || [];
  const dataSource = productsData?.data_source || 'DATABASE';

  // Filter products by search
  const filteredProducts = useMemo(() => {
    if (!searchQuery) return products;
    const query = searchQuery.toLowerCase();
    return products.filter(p => 
      p.name.toLowerCase().includes(query) ||
      p.niche?.toLowerCase().includes(query) ||
      p.source?.toLowerCase().includes(query)
    );
  }, [products, searchQuery]);

  // Check URL for product ID
  useEffect(() => {
    const productId = searchParams.get('id');
    if (productId && products.length > 0) {
      const product = products.find(p => p.id === productId);
      if (product) {
        setSelectedProduct(product);
      }
    }
  }, [searchParams, products]);

  // Handlers
  const handleDiscover = async () => {
    setIsDiscovering(true);
    try {
      const selectedNiches = filters.niches?.length ? filters.niches : ['smart_home', 'fitness', 'tech_accessories'];
      await productsAPI.discover(selectedNiches, 30);
      await new Promise(resolve => setTimeout(resolve, 1000));
      await refetchProducts();
    } catch (error) {
      console.error('Discovery failed:', error);
      alert('Product discovery failed. Please check if the backend is running.');
    } finally {
      setIsDiscovering(false);
    }
  };

  const handleAnalyze = async (product: Product) => {
    setAnalyzingProductId(product.id);
    try {
      const result = await analyze(product.id, product);
      setAnalysisResult(result);
      setSelectedProduct(product);
    } catch (error) {
      console.error('Analysis failed:', error);
      alert('Analysis failed. Please try again.');
    } finally {
      setAnalyzingProductId(null);
    }
  };

  const handleDeploy = async (product: Product) => {
    if (!confirm(`Deploy "${product.name}" to Shopify?\n\nThis will create a new product listing.`)) return;
    
    setDeployingProductId(product.id);
    try {
      const result = await deploy(product.id, product);
      if (result.success) {
        alert(`✅ Product deployed successfully!\n\nShopify URL: ${result.shopify_url || 'Check your Shopify admin'}`);
        if (result.admin_url) {
          window.open(result.admin_url, '_blank');
        }
      } else {
        alert(`❌ Deploy failed: ${result.error || 'Unknown error'}`);
      }
    } catch (error) {
      console.error('Deploy failed:', error);
      alert('Deploy failed. Please check if Shopify is connected.');
    } finally {
      setDeployingProductId(null);
    }
  };

  const handleProductClick = (product: Product) => {
    setSelectedProduct(product);
    setAnalysisResult(null);
    setSearchParams({ id: product.id });
  };

  const handleCloseModal = () => {
    setSelectedProduct(null);
    setAnalysisResult(null);
    setSearchParams({});
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-primary flex items-center gap-2">
            <Brain className="w-7 h-7 text-purple-600" />
            Ospra Intelligence
          </h1>
          <p className="text-sm text-secondary mt-1">
            {products.length > 0 
              ? `${products.length} products • ${dataSource.includes('V5') ? '✨ Cross-source validated' : dataSource}`
              : 'Click "Discover Products" to find winning products with AI'
            }
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            className="btn-primary bg-gradient-to-r from-purple-600 to-cyan-600 hover:from-purple-500 hover:to-cyan-500"
            onClick={handleDiscover}
            disabled={isDiscovering}
          >
            {isDiscovering ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Zap className="w-4 h-4" />
            )}
            <span>Discover Products</span>
          </button>
        </div>
      </div>

      {/* Intelligence Banner */}
      {dataSource.includes('V5') && (
        <div className="p-4 rounded-xl bg-gradient-to-r from-purple-600/10 via-cyan-600/10 to-green-600/10 border border-purple-500/20">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-purple-600/20">
              <Brain className="w-5 h-5 text-purple-600" />
            </div>
            <div>
              <p className="font-medium text-primary">Ospra Intelligence V5 Active</p>
              <p className="text-sm text-secondary">Products are cross-referenced with Google Trends + AliExpress data for validated scores</p>
            </div>
          </div>
        </div>
      )}

      {/* Toolbar */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-4">
        {/* Search */}
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-tertiary" />
          <input
            type="text"
            placeholder="Search products..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-white/50 border border-black/10 focus:border-accent focus:ring-2 focus:ring-accent/20 outline-none text-sm"
          />
        </div>

        {/* Filters Toggle */}
        <button
          className={`btn-ghost ${showFilters ? 'bg-black/5' : ''}`}
          onClick={() => setShowFilters(!showFilters)}
        >
          <Filter className="w-4 h-4" />
          <span>Filters</span>
          <ChevronDown className={`w-4 h-4 transition-transform ${showFilters ? 'rotate-180' : ''}`} />
        </button>

        {/* View Mode */}
        <div className="flex items-center gap-1 p-1 rounded-lg bg-black/5">
          <button
            className={`p-2 rounded-lg transition-colors ${viewMode === 'grid' ? 'bg-white shadow-sm' : 'hover:bg-white/50'}`}
            onClick={() => setViewMode('grid')}
          >
            <Grid3X3 className="w-4 h-4" />
          </button>
          <button
            className={`p-2 rounded-lg transition-colors ${viewMode === 'list' ? 'bg-white shadow-sm' : 'hover:bg-white/50'}`}
            onClick={() => setViewMode('list')}
          >
            <List className="w-4 h-4" />
          </button>
        </div>

        {/* Refresh */}
        <button
          className="btn-ghost"
          onClick={() => refetchProducts()}
          disabled={productsLoading}
        >
          <RefreshCw className={`w-4 h-4 ${productsLoading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* Filters Panel */}
      {showFilters && (
        <div className="glass-card p-4">
          <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
            {/* Niche Filter */}
            <div>
              <label className="text-xs font-medium text-secondary mb-2 block">Niche</label>
              <select
                className="w-full px-3 py-2 rounded-lg bg-white border border-black/10 text-sm"
                value={filters.niches?.[0] || ''}
                onChange={(e) => setFilters(f => ({ ...f, niches: e.target.value ? [e.target.value] : undefined }))}
              >
                <option value="">All Niches</option>
                {niches.map((niche) => (
                  <option key={niche.id} value={niche.id}>{niche.name}</option>
                ))}
              </select>
            </div>

            {/* Min Score Filter */}
            <div>
              <label className="text-xs font-medium text-secondary mb-2 block">Min Score: {filters.min_score || 0}+</label>
              <input
                type="range"
                min="0"
                max="10"
                step="0.5"
                value={filters.min_score || 0}
                onChange={(e) => setFilters(f => ({ ...f, min_score: Number(e.target.value) }))}
                className="w-full accent-purple-600"
              />
            </div>

            {/* Sort */}
            <div>
              <label className="text-xs font-medium text-secondary mb-2 block">Sort By</label>
              <select
                className="w-full px-3 py-2 rounded-lg bg-white border border-black/10 text-sm"
                value={filters.sort_by || 'score'}
                onChange={(e) => setFilters(f => ({ ...f, sort_by: e.target.value as any }))}
              >
                {SORT_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </select>
            </div>

            {/* Reset */}
            <div className="flex items-end">
              <button
                className="btn-ghost w-full justify-center"
                onClick={() => setFilters({ niches: undefined, min_score: 0, sort_by: 'score', sort_order: 'desc', limit: 50 })}
              >
                <X className="w-4 h-4" />
                <span>Reset</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Products Grid/List */}
      {productsLoading ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="w-8 h-8 text-purple-600 animate-spin" />
          <span className="ml-3 text-secondary">Loading products...</span>
        </div>
      ) : filteredProducts.length === 0 ? (
        <div className="text-center py-20">
          <Package className="w-16 h-16 text-tertiary mx-auto mb-4" />
          <h3 className="text-lg font-medium text-primary mb-2">No Products Yet</h3>
          <p className="text-secondary mb-4">Click "Discover Products" to find winning products with Ospra Intelligence</p>
          <button
            className="btn-primary bg-gradient-to-r from-purple-600 to-cyan-600"
            onClick={handleDiscover}
            disabled={isDiscovering}
          >
            {isDiscovering ? <Loader2 className="w-4 h-4 animate-spin" /> : <Zap className="w-4 h-4" />}
            <span>Discover Products</span>
          </button>
        </div>
      ) : (
        <div className={viewMode === 'grid' 
          ? 'grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4'
          : 'space-y-3'
        }>
          {filteredProducts.map((product) => (
            <ProductCard
              key={product.id}
              product={product}
              viewMode={viewMode}
              onAnalyze={handleAnalyze}
              onDeploy={handleDeploy}
              onSelect={handleProductClick}
              isSelected={selectedProducts.has(product.id)}
              isDeploying={deployingProductId === product.id}
              isAnalyzing={analyzingProductId === product.id}
            />
          ))}
        </div>
      )}

      {/* Product Detail Modal */}
      <ProductDetailModal
        product={selectedProduct}
        analysis={analysisResult}
        isAnalyzing={analyzingProductId === selectedProduct?.id}
        onClose={handleCloseModal}
        onAnalyze={handleAnalyze}
        onDeploy={handleDeploy}
        isDeploying={deployingProductId === selectedProduct?.id}
      />
    </div>
  );
}
