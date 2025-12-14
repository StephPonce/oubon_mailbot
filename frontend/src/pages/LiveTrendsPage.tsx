/**
 * Ospra Intelligence - Live Trends Page
 * 
 * FULLY FUNCTIONAL:
 * - Real-time trending products
 * - Momentum tracking
 * - Breakout detection
 * - Ranking changes
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  TrendingUp,
  TrendingDown,
  Activity,
  Zap,
  ArrowUp,
  ArrowDown,
  Flame,
  RefreshCw,
  Loader2,
  Package,
  Clock,
  ChevronRight,
  BarChart3,
  Rocket,
  X,
} from 'lucide-react';

import {
  useLiveTrends,
  useTrendMovers,
  useBreakoutProducts,
  useProductRankings,
  useDeployToShopify,
} from '../hooks/useData';
import type { Product } from '../services/api';

// =============================================================================
// TREND PRODUCT CARD
// =============================================================================

interface TrendCardProps {
  product: Product;
  rank?: number;
  previousRank?: number;
  onDeploy: (product: Product) => void;
  onViewDetails: (product: Product) => void;
  isDeploying: boolean;
}

function TrendCard({ product, rank, previousRank, onDeploy, onViewDetails, isDeploying }: TrendCardProps) {
  const rankChange = previousRank && rank ? previousRank - rank : 0;
  const velocity = product.velocity_score || product.trend_score || 0;

  const getVelocityColor = (v: number) => {
    if (v >= 80) return 'text-green-600 bg-green-500/100/10';
    if (v >= 50) return 'text-amber-600 bg-amber-500/10';
    return 'text-red-500 bg-red-500/100/10';
  };

  return (
    <div className="glass-card p-4 hover:shadow-lg transition-all">
      <div className="flex items-start gap-4">
        {/* Rank */}
        {rank && (
          <div className="flex flex-col items-center">
            <div className="text-2xl font-bold text-primary">#{rank}</div>
            {rankChange !== 0 && (
              <div className={`flex items-center text-xs font-medium ${
                rankChange > 0 ? 'text-green-600' : 'text-red-500'
              }`}>
                {rankChange > 0 ? <ArrowUp className="w-3 h-3" /> : <ArrowDown className="w-3 h-3" />}
                <span>{Math.abs(rankChange)}</span>
              </div>
            )}
          </div>
        )}

        {/* Image */}
        <div className="w-16 h-16 rounded-lg bg-black/5 flex-shrink-0 overflow-hidden">
          {product.image_url ? (
            <img src={product.image_url} alt={product.name} className="w-full h-full object-cover" />
          ) : (
            <div className="w-full h-full flex items-center justify-center">
              <Package className="w-6 h-6 text-tertiary" />
            </div>
          )}
        </div>

        {/* Info */}
        <div className="flex-1 min-w-0">
          <h3 className="text-sm font-medium text-primary line-clamp-1">{product.name}</h3>
          <div className="flex items-center gap-2 mt-1">
            <span className="badge badge-blue">{product.niche}</span>
            <span className="text-xs text-tertiary">{product.source}</span>
          </div>
          
          {/* Momentum Bar */}
          <div className="mt-2">
            <div className="flex items-center justify-between text-xs mb-1">
              <span className="text-tertiary">Momentum</span>
              <span className={`font-medium ${getVelocityColor(velocity)}`}>
                {velocity}%
              </span>
            </div>
            <div className="h-1.5 bg-black/10 rounded-full overflow-hidden">
              <div 
                className={`h-full rounded-full transition-all ${
                  velocity >= 80 ? 'bg-green-500/100' : 
                  velocity >= 50 ? 'bg-amber-500' : 'bg-red-500/100'
                }`}
                style={{ width: `${Math.min(velocity, 100)}%` }}
              />
            </div>
          </div>
        </div>

        {/* Stats */}
        <div className="flex flex-col items-end gap-2 flex-shrink-0">
          <div className={`flex items-center gap-1 px-2 py-1 rounded-lg ${getVelocityColor(velocity)}`}>
            {product.trend === 'up' ? (
              <TrendingUp className="w-4 h-4" />
            ) : product.trend === 'down' ? (
              <TrendingDown className="w-4 h-4" />
            ) : (
              <Activity className="w-4 h-4" />
            )}
            <span className="text-sm font-medium">{product.trend_value || `${velocity}%`}</span>
          </div>
          <div className="text-sm font-semibold text-green-600">
            ${(product.profit || product.estimated_profit || 0).toFixed(2)}
          </div>
        </div>

        {/* Actions */}
        <div className="flex flex-col gap-2 flex-shrink-0">
          <button
            className="btn-ghost text-xs"
            onClick={() => onViewDetails(product)}
          >
            <ChevronRight className="w-4 h-4" />
          </button>
          <button
            className="btn-primary text-xs"
            onClick={() => onDeploy(product)}
            disabled={isDeploying}
          >
            {isDeploying ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Rocket className="w-4 h-4" />
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// BREAKOUT CARD
// =============================================================================

function BreakoutCard({ product, onDeploy, isDeploying }: { 
  product: Product; 
  onDeploy: (p: Product) => void;
  isDeploying: boolean;
}) {
  return (
    <div className="glass-card p-4 border-2 border-amber-500/30 bg-gradient-to-br from-amber-500/5 to-transparent">
      <div className="flex items-center gap-2 mb-3">
        <Flame className="w-5 h-5 text-amber-500" />
        <span className="text-xs font-medium text-amber-600">BREAKOUT</span>
      </div>
      
      <div className="flex items-start gap-3">
        <div className="w-14 h-14 rounded-lg bg-black/5 overflow-hidden flex-shrink-0">
          {product.image_url ? (
            <img src={product.image_url} alt={product.name} className="w-full h-full object-cover" />
          ) : (
            <Package className="w-full h-full p-3 text-tertiary" />
          )}
        </div>
        <div className="flex-1 min-w-0">
          <h4 className="text-sm font-medium text-primary line-clamp-1">{product.name}</h4>
          <p className="text-xs text-tertiary mt-1">{product.niche}</p>
          <div className="flex items-center gap-2 mt-2">
            <span className="text-green-600 font-semibold text-sm">
              +{product.velocity_score || 0}%
            </span>
            <span className="text-xs text-tertiary">momentum</span>
          </div>
        </div>
        <button
          className="btn-primary text-xs"
          onClick={() => onDeploy(product)}
          disabled={isDeploying}
        >
          {isDeploying ? <Loader2 className="w-4 h-4 animate-spin" /> : <Rocket className="w-4 h-4" />}
        </button>
      </div>
    </div>
  );
}

// =============================================================================
// MOVER CARD
// =============================================================================

function MoverCard({ product, direction }: { product: Product; direction: 'up' | 'down' }) {
  const isUp = direction === 'up';
  
  return (
    <div className={`p-3 rounded-xl ${isUp ? 'bg-green-500/100/8' : 'bg-red-500/100/8'}`}>
      <div className="flex items-center gap-3">
        <div className={`p-2 rounded-lg ${isUp ? 'bg-green-500/100/20 text-green-600' : 'bg-red-500/100/20 text-red-500'}`}>
          {isUp ? <ArrowUp className="w-4 h-4" /> : <ArrowDown className="w-4 h-4" />}
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-sm font-medium text-primary line-clamp-1">{product.name}</div>
          <div className="text-xs text-tertiary">{product.niche}</div>
        </div>
        <div className={`text-sm font-semibold ${isUp ? 'text-green-600' : 'text-red-500'}`}>
          {isUp ? '+' : ''}{product.velocity_score || 0}%
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// MAIN COMPONENT
// =============================================================================

export default function LiveTrendsPage() {
  const navigate = useNavigate();

  // State
  const [deployingProductId, setDeployingProductId] = useState<string | null>(null);
  const [selectedTab, setSelectedTab] = useState<'rankings' | 'breakouts'>('rankings');

  // Data hooks
  const { data: liveTrends, isLoading: trendsLoading, isError: trendsError, error: trendsErrorObj, refetch: refetchTrends } = useLiveTrends();
  const { data: upMovers, isLoading: upMoversLoading } = useTrendMovers('up', 5);
  const { data: downMovers, isLoading: downMoversLoading } = useTrendMovers('down', 5);
  const { data: breakouts, isLoading: breakoutsLoading } = useBreakoutProducts();
  const { data: rankingsData, isLoading: rankingsLoading, isError: rankingsError, error: rankingsErrorObj, refetch: refetchRankings } = useProductRankings(20);

  // Deploy hook
  const { deploy } = useDeployToShopify();

  // Get live data only
  const rankings = rankingsData?.rankings || [];
  const breakoutProducts = breakouts || [];
  const risers = upMovers || [];
  const fallers = downMovers || [];

  // Handlers
  const handleDeploy = async (product: Product) => {
    if (!confirm(`Deploy "${product.name}" to Shopify?`)) return;
    
    setDeployingProductId(product.id);
    try {
      const result = await deploy(product.id, product);
      if (result.success) {
        alert(`✅ Deployed successfully!\n\nShopify URL: ${result.shopify_url || 'Check admin'}`);
      } else {
        alert(`❌ Deploy failed: ${result.error}`);
      }
    } catch (error) {
      console.error('Deploy failed:', error);
      alert('Deploy failed. Check Shopify connection.');
    } finally {
      setDeployingProductId(null);
    }
  };

  const handleViewDetails = (product: Product) => {
    navigate(`/products?id=${product.id}`);
  };

  const handleRefresh = () => {
    refetchTrends();
    refetchRankings();
  };

  const isLoading = trendsLoading || rankingsLoading;
  const hasError = (trendsError && !rankings.length) || (rankingsError && !rankings.length);

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-primary flex items-center gap-2">
            <Zap className="w-6 h-6 text-amber-500" />
            Live Trends
          </h1>
          <p className="text-sm text-secondary mt-1">
            Real-time product momentum and ranking changes
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1 px-3 py-1.5 rounded-full bg-green-500/100/10 border border-green-500/20">
            <div className="w-2 h-2 rounded-full bg-green-500/100 animate-pulse" />
            <span className="text-xs text-green-600 font-medium">Live Data</span>
          </div>
          <button
            className="btn-ghost"
            onClick={handleRefresh}
            disabled={isLoading}
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Error State */}
      {hasError ? (
        <div className="glass-card p-12 text-center">
          <X className="w-16 h-16 text-red-500 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-primary mb-2">Connection Error</h3>
          <p className="text-sm text-secondary mb-6">
            {trendsErrorObj?.message || rankingsErrorObj?.message || 'Unable to fetch live trends. Backend might be offline.'}
          </p>
          <button
            className="btn-primary"
            onClick={handleRefresh}
            disabled={isLoading}
          >
            {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
            <span>Retry Connection</span>
          </button>
        </div>
      ) : null}

      {/* Stats Row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="glass-card p-4 text-center">
          <div className="text-2xl font-bold text-primary">{rankings.length}</div>
          <div className="text-xs text-tertiary">Tracked Products</div>
        </div>
        <div className="glass-card p-4 text-center">
          <div className="text-2xl font-bold text-green-600">{risers.length}</div>
          <div className="text-xs text-tertiary">Rising</div>
        </div>
        <div className="glass-card p-4 text-center">
          <div className="text-2xl font-bold text-amber-500">{breakoutProducts.length}</div>
          <div className="text-xs text-tertiary">Breakouts</div>
        </div>
        <div className="glass-card p-4 text-center">
          <div className="text-2xl font-bold text-red-500">{fallers.length}</div>
          <div className="text-xs text-tertiary">Falling</div>
        </div>
      </div>

      {/* Main Content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Rankings - Main Column */}
        <div className="lg:col-span-2 space-y-4">
          {/* Tabs */}
          <div className="flex items-center gap-2 p-1 rounded-xl bg-black/5 w-fit">
            <button
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                selectedTab === 'rankings' ? 'bg-white shadow-sm text-primary' : 'text-secondary hover:text-primary'
              }`}
              onClick={() => setSelectedTab('rankings')}
            >
              <BarChart3 className="w-4 h-4 inline mr-2" />
              Top Rankings
            </button>
            <button
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                selectedTab === 'breakouts' ? 'bg-white shadow-sm text-primary' : 'text-secondary hover:text-primary'
              }`}
              onClick={() => setSelectedTab('breakouts')}
            >
              <Flame className="w-4 h-4 inline mr-2" />
              Breakouts
            </button>
          </div>

          {/* Content */}
          {selectedTab === 'rankings' && (
            <div className="space-y-3">
              {rankingsLoading ? (
                <div className="flex items-center justify-center py-12">
                  <Loader2 className="w-8 h-8 text-accent animate-spin" />
                </div>
              ) : rankings.length === 0 ? (
                <div className="glass-card p-12 text-center">
                  <BarChart3 className="w-12 h-12 text-tertiary mx-auto mb-4" />
                  <h3 className="text-lg font-medium text-primary mb-2">No Rankings Yet</h3>
                  <p className="text-sm text-secondary">
                    Product rankings will appear once trend data is collected.
                  </p>
                </div>
              ) : (
                rankings.map((product, index) => (
                  <TrendCard
                    key={product.id}
                    product={product}
                    rank={index + 1}
                    previousRank={product.previous_rank}
                    onDeploy={handleDeploy}
                    onViewDetails={handleViewDetails}
                    isDeploying={deployingProductId === product.id}
                  />
                ))
              )}
            </div>
          )}

          {selectedTab === 'breakouts' && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {breakoutsLoading ? (
                <div className="col-span-2 flex items-center justify-center py-12">
                  <Loader2 className="w-8 h-8 text-accent animate-spin" />
                </div>
              ) : breakoutProducts.length === 0 ? (
                <div className="col-span-2 glass-card p-12 text-center">
                  <Flame className="w-12 h-12 text-tertiary mx-auto mb-4" />
                  <h3 className="text-lg font-medium text-primary mb-2">No Breakouts Detected</h3>
                  <p className="text-sm text-secondary">
                    Products with explosive momentum will appear here.
                  </p>
                </div>
              ) : (
                breakoutProducts.map((product) => (
                  <BreakoutCard
                    key={product.id}
                    product={product}
                    onDeploy={handleDeploy}
                    isDeploying={deployingProductId === product.id}
                  />
                ))
              )}
            </div>
          )}
        </div>

        {/* Sidebar - Movers */}
        <div className="space-y-6">
          {/* Risers */}
          <div className="glass-card-static p-5">
            <div className="flex items-center gap-2 mb-4">
              <TrendingUp className="w-5 h-5 text-green-600" />
              <h3 className="text-sm font-medium text-primary">Biggest Risers</h3>
            </div>
            {upMoversLoading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="w-6 h-6 text-accent animate-spin" />
              </div>
            ) : risers.length === 0 ? (
              <div className="text-sm text-tertiary text-center py-4">No risers yet</div>
            ) : (
              <div className="space-y-2">
                {risers.map((product) => (
                  <MoverCard key={product.id} product={product} direction="up" />
                ))}
              </div>
            )}
          </div>

          {/* Fallers */}
          <div className="glass-card-static p-5">
            <div className="flex items-center gap-2 mb-4">
              <TrendingDown className="w-5 h-5 text-red-500" />
              <h3 className="text-sm font-medium text-primary">Biggest Fallers</h3>
            </div>
            {downMoversLoading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="w-6 h-6 text-accent animate-spin" />
              </div>
            ) : fallers.length === 0 ? (
              <div className="text-sm text-tertiary text-center py-4">No fallers yet</div>
            ) : (
              <div className="space-y-2">
                {fallers.map((product) => (
                  <MoverCard key={product.id} product={product} direction="down" />
                ))}
              </div>
            )}
          </div>

          {/* Last Updated */}
          <div className="flex items-center justify-center gap-2 text-xs text-tertiary">
            <Clock className="w-3.5 h-3.5" />
            <span>Auto-refreshes every 30 seconds</span>
          </div>
        </div>
      </div>
    </div>
  );
}
