/**
 * Ospra Intelligence - Unified Products Page
 * 
 * FULLY FUNCTIONAL:
 * - Product discovery from AliExpress, TikTok, Amazon
 * - Filtering and sorting
 * - One-click deploy to Shopify
 * - AI analysis
 * - Real-time data
 */

import { useState, useEffect, useMemo } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
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
} from 'lucide-react';

import {
  useProducts,
  useNiches,
  useDeployToShopify,
  useAnalyzeProduct,
} from '../hooks/useData';
import { productsAPI } from '../services/api';
import type { Product, ProductFilters } from '../services/api';

// =============================================================================
// CONSTANTS & UTILITIES
// =============================================================================

const SORT_OPTIONS = [
  { value: 'score', label: 'Highest Score' },
  { value: 'profit', label: 'Highest Profit' },
  { value: 'trend', label: 'Trending' },
  { value: 'newest', label: 'Newest' },
];

const SOURCE_OPTIONS = [
  { value: 'all', label: 'All Sources' },
  { value: 'aliexpress', label: 'AliExpress' },
  { value: 'tiktok_shop', label: 'TikTok Shop' },
  { value: 'amazon', label: 'Amazon' },
];

// Format niche name: "smart_home" => "Smart Home"
function formatNiche(niche: string): string {
  if (!niche) return '';
  return niche
    .split('_')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

// Sanitize image URL to fix CORS and protocol issues
function sanitizeImageUrl(url?: string, productName?: string): string {
  if (!url || url.trim() === '') {
    return getPlaceholder(productName);
  }

  // Force HTTPS (AliExpress CDN requires it)
  let cleanUrl = url.replace(/^http:\/\//i, 'https://');

  // Handle AliExpress CDN URLs - use optimized size for faster loading
  if (cleanUrl.includes('alicdn.com') || cleanUrl.includes('aliexpress-media')) {
    // Remove any existing size params and add 400x400 for cards
    cleanUrl = cleanUrl.split('_')[0];
    // Don't add extension if URL already has query params
    if (!cleanUrl.includes('?')) {
      cleanUrl = cleanUrl + '_400x400.jpg';
    }
  }

  return cleanUrl;
}

// Generate placeholder image with product name
function getPlaceholder(name?: string): string {
  const text = encodeURIComponent(name?.substring(0, 20) || 'Product');
  return `https://placehold.co/400x400/1a1a2e/eaeaea?text=${text}`;
}

// =============================================================================
// PRODUCT CARD COMPONENT
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
    if (score >= 8) return 'bg-green-500 text-white';
    if (score >= 6) return 'bg-amber-500 text-white';
    return 'bg-red-500 text-white';
  };

  const getSaturationColor = (level?: string) => {
    switch (level) {
      case 'low': return 'text-green-600 bg-green-500/10';
      case 'medium': return 'text-amber-600 bg-amber-500/10';
      case 'high': return 'text-red-600 bg-red-500/10';
      default: return 'text-gray-600 bg-gray-500/10';
    }
  };

  const score = product.score || product.final_score || 0;
  const profit = product.profit || product.estimated_profit || 0;

  if (viewMode === 'list') {
    return (
      <div 
        className={`glass-card p-4 flex items-center gap-4 cursor-pointer transition-all ${
          isSelected ? 'ring-2 ring-accent' : 'hover:shadow-md'
        }`}
        onClick={() => onSelect(product)}
      >
        {/* Image */}
        <div className="w-20 h-20 rounded-lg bg-black/5 flex-shrink-0 overflow-hidden">
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
        </div>

        {/* Info */}
        <div className="flex-1 min-w-0">
          <h3 className="text-sm font-medium text-primary line-clamp-1">{product.name}</h3>
          <div className="flex items-center gap-2 mt-1">
            <span className="badge badge-blue">{formatNiche(product.niche)}</span>
            <span className="text-xs text-tertiary">{product.source}</span>
            {product.saturation_level && (
              <span className={`text-xs px-2 py-0.5 rounded-full ${getSaturationColor(product.saturation_level)}`}>
                {product.saturation_level} saturation
              </span>
            )}
          </div>
        </div>

        {/* Stats */}
        <div className="flex items-center gap-6 flex-shrink-0">
          <div className="text-center">
            <div className={`text-lg font-bold px-2 py-1 rounded ${getScoreColor(score)}`}>
              {score.toFixed(1)}
            </div>
            <div className="text-xs text-tertiary mt-1">Score</div>
          </div>
          <div className="text-center">
            <div className="text-lg font-semibold text-green-600">${profit.toFixed(2)}</div>
            <div className="text-xs text-tertiary">Profit</div>
          </div>
          <div className="text-center">
            <div className={`flex items-center justify-center ${
              product.trend === 'up' ? 'text-green-600' : 
              product.trend === 'down' ? 'text-red-500' : 'text-tertiary'
            }`}>
              {product.trend === 'up' ? <TrendingUp className="w-5 h-5" /> : 
               product.trend === 'down' ? <TrendingDown className="w-5 h-5" /> : 
               <Activity className="w-5 h-5" />}
            </div>
            <div className="text-xs text-tertiary">Trend</div>
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2 flex-shrink-0">
          {(product.aliexpress_url || product.url) && (
            <a
              href={product.aliexpress_url || product.url}
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
        isSelected ? 'ring-2 ring-accent' : 'hover:shadow-lg'
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

        {/* Score Badge */}
        <div className={`absolute top-3 right-3 px-2 py-1 rounded-lg text-sm font-bold ${getScoreColor(score)}`}>
          {score.toFixed(1)}
        </div>

        {/* Trend Badge */}
        <div className="absolute top-3 left-3 flex items-center gap-1 px-2 py-1 rounded-lg bg-white/90 backdrop-blur-sm">
          {product.trend === 'up' ? (
            <TrendingUp className="w-3.5 h-3.5 text-green-600" />
          ) : product.trend === 'down' ? (
            <TrendingDown className="w-3.5 h-3.5 text-red-500" />
          ) : (
            <Activity className="w-3.5 h-3.5 text-tertiary" />
          )}
          <span className={`text-xs font-medium ${
            product.trend === 'up' ? 'text-green-600' : 
            product.trend === 'down' ? 'text-red-500' : 'text-tertiary'
          }`}>
            {product.trend_value || `${product.velocity_score || 0}%`}
          </span>
        </div>

        {/* Platform Badges */}
        {product.platform_badges && product.platform_badges.length > 0 && (
          <div className="absolute bottom-3 left-3 flex gap-1">
            {product.platform_badges.map((badge, i) => (
              <div
                key={i}
                className="px-2 py-0.5 rounded text-xs font-medium bg-white/90 backdrop-blur-sm"
                title={badge.label}
              >
                {badge.emoji} {badge.platform}
              </div>
            ))}
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

        <div className="flex items-center gap-2 mb-3">
          <span className="badge badge-blue">{formatNiche(product.niche)}</span>
          <span className="text-xs text-tertiary">{product.source}</span>
        </div>

        {/* AI Reason */}
        {product.ai_reason && (
          <div className="p-2 rounded-lg bg-blue-500/8 border border-blue-500/15 mb-3">
            <div className="flex items-start gap-2">
              <Brain className="w-3.5 h-3.5 text-blue-600 mt-0.5 flex-shrink-0" />
              <p className="text-xs text-secondary line-clamp-2">{product.ai_reason}</p>
            </div>
          </div>
        )}

        {/* Stats */}
        <div className="grid grid-cols-3 gap-2 mb-3">
          <div className="text-center p-2 rounded-lg bg-black/5">
            <div className="text-sm font-semibold text-green-600">${profit.toFixed(2)}</div>
            <div className="text-[10px] text-tertiary">Profit</div>
          </div>
          <div className="text-center p-2 rounded-lg bg-black/5">
            <div className="text-sm font-semibold text-primary">${(product.cost || 0).toFixed(2)}</div>
            <div className="text-[10px] text-tertiary">Cost</div>
          </div>
          <div className="text-center p-2 rounded-lg bg-black/5">
            <div className="text-sm font-semibold text-primary">{(product.profit_margin || 0).toFixed(0)}%</div>
            <div className="text-[10px] text-tertiary">Margin</div>
          </div>
        </div>

        {/* Actions */}
        <div className="flex flex-col gap-2">
          {(product.aliexpress_url || product.url) && (
            <a
              href={product.aliexpress_url || product.url}
              target="_blank"
              rel="noopener noreferrer"
              className="btn-ghost text-xs justify-center w-full"
              onClick={(e) => e.stopPropagation()}
            >
              <ExternalLink className="w-4 h-4" />
              <span>View Product</span>
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
// PRODUCT DETAIL MODAL
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

  const score = product.score || product.final_score || 0;
  const profit = product.profit || product.estimated_profit || 0;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
      <div className="glass-card max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-start justify-between p-6 border-b border-black/10">
          <div className="flex items-start gap-4">
            <div className="w-24 h-24 rounded-xl bg-black/5 overflow-hidden flex-shrink-0">
              {product.image_url ? (
                <img src={product.image_url} alt={product.name} className="w-full h-full object-cover" />
              ) : (
                <div className="w-full h-full flex items-center justify-center">
                  <Package className="w-10 h-10 text-tertiary" />
                </div>
              )}
            </div>
            <div>
              <h2 className="text-lg font-semibold text-primary">{product.name}</h2>
              <div className="flex items-center gap-2 mt-2">
                <span className="badge badge-blue">{product.niche}</span>
                <span className="text-sm text-tertiary">{product.source}</span>
              </div>
            </div>
          </div>
          <button onClick={onClose} className="p-2 hover:bg-black/5 rounded-lg">
            <X className="w-5 h-5 text-tertiary" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6">
          {/* Score & Stats */}
          <div className="grid grid-cols-4 gap-4">
            <div className="text-center p-4 rounded-xl bg-black/5">
              <div className={`text-2xl font-bold ${score >= 7 ? 'text-green-600' : score >= 5 ? 'text-amber-600' : 'text-red-500'}`}>
                {score.toFixed(1)}
              </div>
              <div className="text-xs text-tertiary mt-1">AI Score</div>
            </div>
            <div className="text-center p-4 rounded-xl bg-black/5">
              <div className="text-2xl font-bold text-green-600">${profit.toFixed(2)}</div>
              <div className="text-xs text-tertiary mt-1">Est. Profit</div>
            </div>
            <div className="text-center p-4 rounded-xl bg-black/5">
              <div className="text-2xl font-bold text-primary">{(product.profit_margin || 0).toFixed(0)}%</div>
              <div className="text-xs text-tertiary mt-1">Margin</div>
            </div>
            <div className="text-center p-4 rounded-xl bg-black/5">
              <div className="text-2xl font-bold text-primary">{product.velocity_score || 0}</div>
              <div className="text-xs text-tertiary mt-1">Velocity</div>
            </div>
          </div>

          {/* AI Recommendation */}
          {product.ai_reason && (
            <div className="p-4 rounded-xl bg-blue-500/8 border border-blue-500/15">
              <div className="flex items-center gap-2 mb-2">
                <Brain className="w-4 h-4 text-blue-600" />
                <span className="text-sm font-medium text-blue-700">AI Analysis</span>
              </div>
              <p className="text-sm text-secondary">{product.ai_reason}</p>
            </div>
          )}

          {/* Deep Analysis Result */}
          {analysis && (
            <div className="p-4 rounded-xl bg-purple-500/8 border border-purple-500/15">
              <div className="flex items-center gap-2 mb-2">
                <Zap className="w-4 h-4 text-purple-600" />
                <span className="text-sm font-medium text-purple-700">Deep Analysis</span>
              </div>
              <pre className="text-xs text-secondary whitespace-pre-wrap overflow-auto max-h-60">
                {JSON.stringify(analysis, null, 2)}
              </pre>
            </div>
          )}

          {/* Links */}
          <div className="flex items-center gap-4">
            {product.aliexpress_url && (
              <a
                href={product.aliexpress_url}
                target="_blank"
                rel="noopener noreferrer"
                className="btn-ghost text-sm"
              >
                <ExternalLink className="w-4 h-4" />
                <span>View on AliExpress</span>
              </a>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between p-6 border-t border-black/10">
          <button
            className="btn-ghost"
            onClick={() => onAnalyze(product)}
            disabled={isAnalyzing}
          >
            {isAnalyzing ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Brain className="w-4 h-4" />
            )}
            <span>Deep Analysis</span>
          </button>
          <button
            className="btn-primary"
            onClick={() => onDeploy(product)}
            disabled={isDeploying}
          >
            {isDeploying ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Rocket className="w-4 h-4" />
            )}
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
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  // State
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [filters, setFilters] = useState<ProductFilters>({
    niches: [],
    min_score: 0,
    source: undefined,
    sort_by: 'score',
    sort_order: 'desc',
    limit: 20,
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

  // Data hooks - live data only
  const { data: productsData, isLoading: productsLoading, isError: productsError, error: productsErrorObj, refetch: refetchProducts } = useProducts(filters);
  const { data: nichesData } = useNiches();

  const products = productsData?.products || [];
  const niches = nichesData || [];

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
      const selectedNiches = filters.niches?.length ? filters.niches : ['smart_home', 'tech_gadgets', 'fitness'];
      await productsAPI.discover(selectedNiches, 10);
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

  const handleBulkDeploy = async () => {
    if (selectedProducts.size === 0) {
      alert('Please select products to deploy.');
      return;
    }

    if (!confirm(`Deploy ${selectedProducts.size} products to Shopify?`)) return;

    const productsToDeploy = products.filter(p => selectedProducts.has(p.id));
    let successCount = 0;
    let failCount = 0;

    for (const product of productsToDeploy) {
      try {
        const result = await deploy(product.id, product);
        if (result.success) successCount++;
        else failCount++;
      } catch {
        failCount++;
      }
    }

    alert(`Deployment complete!\n\n✅ Success: ${successCount}\n❌ Failed: ${failCount}`);
    setSelectedProducts(new Set());
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
          <h1 className="text-2xl font-semibold text-primary">Product Discovery</h1>
          <p className="text-sm text-secondary mt-1">
            Discover winning products from AliExpress, TikTok Shop, and Amazon
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            className="btn-primary"
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
                onChange={(e) => setFilters(f => ({ ...f, niches: e.target.value ? [e.target.value] : [] }))}
              >
                <option value="">All Niches</option>
                {niches.map((niche) => (
                  <option key={niche.id} value={niche.id}>{niche.name}</option>
                ))}
              </select>
            </div>

            {/* Source Filter */}
            <div>
              <label className="text-xs font-medium text-secondary mb-2 block">Source</label>
              <select
                className="w-full px-3 py-2 rounded-lg bg-white border border-black/10 text-sm"
                value={filters.source || 'all'}
                onChange={(e) => setFilters(f => ({ ...f, source: e.target.value === 'all' ? undefined : e.target.value }))}
              >
                {SOURCE_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </select>
            </div>

            {/* Min Score Filter */}
            <div>
              <label className="text-xs font-medium text-secondary mb-2 block">Min Score</label>
              <input
                type="range"
                min="0"
                max="10"
                step="0.5"
                value={filters.min_score || 0}
                onChange={(e) => setFilters(f => ({ ...f, min_score: Number(e.target.value) }))}
                className="w-full"
              />
              <div className="text-xs text-tertiary mt-1">{filters.min_score || 0}+</div>
            </div>

            {/* Sort */}
            <div>
              <label className="text-xs font-medium text-secondary mb-2 block">Sort By</label>
              <select
                className="w-full px-3 py-2 rounded-lg bg-white border border-black/10 text-sm"
                value={filters.sort_by || 'score'}
                onChange={(e) => setFilters(f => ({ ...f, sort_by: e.target.value as ProductFilters['sort_by'] }))}
              >
                {SORT_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </select>
            </div>
          </div>
        </div>
      )}

      {/* Bulk Actions */}
      {selectedProducts.size > 0 && (
        <div className="glass-card p-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-5 h-5 text-accent" />
            <span className="text-sm font-medium">{selectedProducts.size} products selected</span>
          </div>
          <div className="flex items-center gap-3">
            <button
              className="btn-ghost text-sm"
              onClick={() => setSelectedProducts(new Set())}
            >
              Clear Selection
            </button>
            <button
              className="btn-primary text-sm"
              onClick={handleBulkDeploy}
            >
              <Rocket className="w-4 h-4" />
              <span>Deploy Selected</span>
            </button>
          </div>
        </div>
      )}

      {/* Products Grid/List */}
      {productsError && products.length === 0 ? (
        <div className="glass-card p-12 text-center">
          <X className="w-16 h-16 text-red-500 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-primary mb-2">Connection Error</h3>
          <p className="text-sm text-secondary mb-6">
            {productsErrorObj?.message || 'Unable to fetch products. Backend might be offline.'}
          </p>
          <button
            className="btn-primary"
            onClick={() => refetchProducts()}
            disabled={productsLoading}
          >
            {productsLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
            <span>Retry Connection</span>
          </button>
        </div>
      ) : productsLoading && products.length === 0 ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="w-8 h-8 text-accent animate-spin" />
        </div>
      ) : filteredProducts.length === 0 ? (
        <div className="glass-card p-12 text-center">
          <Package className="w-16 h-16 text-tertiary mx-auto mb-4" />
          <h3 className="text-lg font-medium text-primary mb-2">No Products Found</h3>
          <p className="text-sm text-secondary mb-6">
            Click "Discover Products" to find winning products using AI.
          </p>
          <button
            className="btn-primary"
            onClick={handleDiscover}
            disabled={isDiscovering}
          >
            {isDiscovering ? <Loader2 className="w-4 h-4 animate-spin" /> : <Zap className="w-4 h-4" />}
            <span>Start Discovery</span>
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
              onSelect={() => handleProductClick(product)}
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
