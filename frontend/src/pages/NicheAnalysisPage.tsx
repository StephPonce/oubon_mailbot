/**
 * Ospra Intelligence - Niche Analysis Page
 * 
 * FULLY FUNCTIONAL:
 * - Real niche data from API
 * - Niche scoring and analysis
 * - Saturation tracking
 * - AI-powered recommendations
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Target,
  TrendingUp,
  TrendingDown,
  Activity,
  RefreshCw,
  ChevronRight,
  Brain,
  Loader2,
  Package,
  BarChart3,
  Zap,
  AlertCircle,
  CheckCircle2,
  X,
} from 'lucide-react';

import {
  useNiches,
  useNicheProducts,
  useAnalyzeProduct,
} from '../hooks/useData';
import { nichesAPI, intelligenceAPI } from '../services/api';
import type { Niche } from '../services/api';
import { ExplainTooltip } from '../components/ui/ExplainTooltip';

// =============================================================================
// RATIONALE GENERATOR
// =============================================================================

function generateNicheRationale(niche: Niche) {
  const score = niche.score || niche.overall_score || 0;
  const saturation = niche.saturation || niche.saturation_level || 'medium';
  const growth = niche.growth_rate || 0;
  const avgProfit = niche.avg_profit || 0;
  const competition = niche.competition_level || 'medium';
  const productCount = niche.product_count || 0;

  const factors = [];
  const parts = [];
  let confidenceBoost = 0;

  // Saturation analysis
  if (saturation === 'low') {
    factors.push({ label: "Low competition opportunity", value: 15, icon: "success" as const });
    parts.push("low market saturation");
    confidenceBoost += 15;
  } else if (saturation === 'medium') {
    factors.push({ label: "Moderate competition", value: 5, icon: "trend" as const });
    parts.push("moderate competition");
    confidenceBoost += 5;
  } else {
    factors.push({ label: "High competition", value: -10, icon: "warning" as const });
    parts.push("high saturation market");
    confidenceBoost -= 10;
  }

  // Growth analysis
  if (growth > 10) {
    factors.push({ label: "Rapid growth trend", value: 15, icon: "trend" as const });
    parts.push(`${growth}% growth momentum`);
    confidenceBoost += 15;
  } else if (growth > 0) {
    factors.push({ label: "Positive growth", value: 8, icon: "success" as const });
    parts.push("upward trend");
    confidenceBoost += 8;
  } else if (growth < -5) {
    factors.push({ label: "Declining interest", value: -12, icon: "warning" as const });
    parts.push("declining trend");
    confidenceBoost -= 12;
  }

  // Profit analysis
  if (avgProfit > 30) {
    factors.push({ label: "Excellent profit margins", value: 12, icon: "success" as const });
    parts.push(`$${avgProfit.toFixed(0)} average profit`);
    confidenceBoost += 12;
  } else if (avgProfit > 15) {
    factors.push({ label: "Good profit potential", value: 8, icon: "success" as const });
    parts.push("solid margins");
    confidenceBoost += 8;
  }

  // Product count analysis
  if (productCount > 50) {
    factors.push({ label: "Proven product diversity", value: 8, icon: "success" as const });
    parts.push(`${productCount} validated products`);
    confidenceBoost += 8;
  }

  const rationaleText = parts.length > 0
    ? `This niche shows ${parts.slice(0, 3).join(", ")}. ${score >= 8 ? "Strong opportunity for market entry." : score >= 6 ? "Good potential with moderate risk." : "Consider testing with caution."}`
    : "Meets baseline criteria for niche exploration.";

  const confidence = Math.min(95, Math.max(35, Math.round(score * 10 + confidenceBoost)));

  return { rationale: rationaleText, confidence, factors: factors.slice(0, 4) };
}

// =============================================================================
// NICHE CARD
// =============================================================================

interface NicheCardProps {
  niche: Niche;
  onExplore: (niche: Niche) => void;
  onAnalyze: (niche: Niche) => void;
  isAnalyzing: boolean;
}

function NicheCard({ niche, onExplore, onAnalyze, isAnalyzing }: NicheCardProps) {
  const score = niche.score || niche.overall_score || 0;
  const trend = niche.trend || 'stable';
  const trendValue = niche.trend_value || niche.growth_rate || 0;
  const saturation = niche.saturation || niche.saturation_level || 'medium';

  const getSaturationColor = (level: string) => {
    switch (level) {
      case 'low': return 'text-green-600 bg-green-500/10 border-green-500/20';
      case 'medium': return 'text-amber-600 bg-amber-500/10 border-amber-500/20';
      case 'high': return 'text-red-600 bg-red-500/10 border-red-500/20';
      default: return 'text-secondary bg-black/5 border-black/10';
    }
  };

  const getScoreColor = (s: number) => {
    if (s >= 8) return 'bg-green-500';
    if (s >= 6) return 'bg-amber-500';
    return 'bg-red-500';
  };

  const explanation = generateNicheRationale(niche);

  return (
    <div className="glass-card p-5 hover:shadow-lg transition-all">
      <div className="flex items-center gap-6">
        {/* Score with Explain Tooltip */}
        <div className="relative">
          <div className={`w-16 h-16 rounded-xl flex items-center justify-center font-bold text-xl text-white ${getScoreColor(score)}`}>
            {score.toFixed(1)}
          </div>
          <div className="absolute -top-1 -right-1">
            <ExplainTooltip
              rationale={explanation.rationale}
              confidence={explanation.confidence}
              factors={explanation.factors}
              position="right"
            />
          </div>
        </div>

        {/* Info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3 mb-2">
            <h3 className="text-lg font-medium text-primary">{niche.name}</h3>
            <span className={`px-2 py-0.5 rounded-full text-xs font-medium border ${getSaturationColor(saturation)}`}>
              {saturation.charAt(0).toUpperCase() + saturation.slice(1)} Saturation
            </span>
          </div>
          <div className="flex items-center gap-6 text-sm text-secondary">
            <span className="flex items-center gap-1">
              <Package className="w-3.5 h-3.5" />
              {niche.product_count || 0} products
            </span>
            <span>Avg Profit: ${(niche.avg_profit || 0).toFixed(2)}</span>
            <span>Competition: {niche.competition_level || 'Unknown'}</span>
          </div>
          {niche.description && (
            <p className="text-xs text-tertiary mt-2 line-clamp-1">{niche.description}</p>
          )}
        </div>

        {/* Trend */}
        <div className="text-right flex-shrink-0">
          <div className={`flex items-center gap-1 justify-end text-lg font-semibold ${
            trend === 'up' ? 'text-green-600' : 
            trend === 'down' ? 'text-red-500' : 'text-secondary'
          }`}>
            {trend === 'up' ? <TrendingUp className="w-5 h-5" /> : 
             trend === 'down' ? <TrendingDown className="w-5 h-5" /> : 
             <Activity className="w-5 h-5" />}
            {typeof trendValue === 'number' ? `${trendValue > 0 ? '+' : ''}${trendValue}%` : trendValue}
          </div>
          <div className="text-xs text-tertiary mt-1">30-day trend</div>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2 flex-shrink-0">
          <button
            className="btn-ghost text-sm"
            onClick={() => onAnalyze(niche)}
            disabled={isAnalyzing}
          >
            {isAnalyzing ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Brain className="w-4 h-4" />
            )}
          </button>
          <button
            className="btn-primary text-sm"
            onClick={() => onExplore(niche)}
          >
            Explore
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// NICHE DETAIL MODAL
// =============================================================================

interface NicheDetailModalProps {
  niche: Niche | null;
  products: any[];
  isLoadingProducts: boolean;
  analysis: any | null;
  onClose: () => void;
  onViewProduct: (productId: string) => void;
}

function NicheDetailModal({
  niche,
  products,
  isLoadingProducts,
  analysis,
  onClose,
  onViewProduct,
}: NicheDetailModalProps) {
  if (!niche) return null;

  const score = niche.score || niche.overall_score || 0;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
      <div className="glass-card max-w-3xl w-full max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="p-6 border-b border-black/10">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className={`w-14 h-14 rounded-xl flex items-center justify-center font-bold text-xl text-white ${
                score >= 8 ? 'bg-green-500' : score >= 6 ? 'bg-amber-500' : 'bg-red-500'
              }`}>
                {score.toFixed(1)}
              </div>
              <div>
                <h2 className="text-xl font-semibold text-primary">{niche.name}</h2>
                <p className="text-sm text-secondary">{niche.product_count || 0} products tracked</p>
              </div>
            </div>
            <button onClick={onClose} className="btn-ghost">Close</button>
          </div>
        </div>

        {/* Stats */}
        <div className="p-6 border-b border-black/10">
          <div className="grid grid-cols-4 gap-4">
            <div className="text-center p-4 rounded-xl bg-black/5">
              <div className="text-2xl font-bold text-green-600">${(niche.avg_profit || 0).toFixed(2)}</div>
              <div className="text-xs text-tertiary">Avg Profit</div>
            </div>
            <div className="text-center p-4 rounded-xl bg-black/5">
              <div className="text-2xl font-bold text-primary">{niche.competition_level || 'N/A'}</div>
              <div className="text-xs text-tertiary">Competition</div>
            </div>
            <div className="text-center p-4 rounded-xl bg-black/5">
              <div className="text-2xl font-bold text-primary">{niche.saturation_level || 'N/A'}</div>
              <div className="text-xs text-tertiary">Saturation</div>
            </div>
            <div className="text-center p-4 rounded-xl bg-black/5">
              <div className={`text-2xl font-bold ${
                (niche.growth_rate || 0) > 0 ? 'text-green-600' : 'text-red-500'
              }`}>
                {(niche.growth_rate || 0) > 0 ? '+' : ''}{niche.growth_rate || 0}%
              </div>
              <div className="text-xs text-tertiary">Growth Rate</div>
            </div>
          </div>
        </div>

        {/* AI Analysis */}
        {analysis && (
          <div className="p-6 border-b border-black/10">
            <div className="flex items-center gap-2 mb-3">
              <Brain className="w-5 h-5 text-purple-600" />
              <h3 className="text-sm font-medium text-primary">AI Analysis</h3>
            </div>
            <div className="p-4 rounded-xl bg-purple-500/8 border border-purple-500/15">
              <p className="text-sm text-secondary whitespace-pre-wrap">
                {typeof analysis === 'string' ? analysis : JSON.stringify(analysis, null, 2)}
              </p>
            </div>
          </div>
        )}

        {/* Top Products */}
        <div className="p-6">
          <h3 className="text-sm font-medium text-primary mb-4">Top Products in this Niche</h3>
          {isLoadingProducts ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="w-6 h-6 text-accent animate-spin" />
            </div>
          ) : products.length === 0 ? (
            <div className="text-center py-8 text-tertiary">
              No products found in this niche.
            </div>
          ) : (
            <div className="space-y-2">
              {products.slice(0, 5).map((product) => (
                <div
                  key={product.id}
                  className="flex items-center gap-3 p-3 rounded-xl bg-black/5 hover:bg-black/10 cursor-pointer transition-colors"
                  onClick={() => onViewProduct(product.id)}
                >
                  <div className="w-12 h-12 rounded-lg bg-black/10 overflow-hidden flex-shrink-0">
                    {product.image_url ? (
                      <img src={product.image_url} alt={product.name} className="w-full h-full object-cover" />
                    ) : (
                      <Package className="w-full h-full p-2 text-tertiary" />
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-primary line-clamp-1">{product.name}</div>
                    <div className="text-xs text-tertiary">{product.source}</div>
                  </div>
                  <div className="text-sm font-semibold text-green-600">
                    ${(product.profit || product.estimated_profit || 0).toFixed(2)}
                  </div>
                  <ChevronRight className="w-4 h-4 text-tertiary" />
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// MAIN COMPONENT
// =============================================================================

export default function NicheAnalysisPage() {
  const navigate = useNavigate();

  // State
  const [selectedNiche, setSelectedNiche] = useState<Niche | null>(null);
  const [analyzingNicheId, setAnalyzingNicheId] = useState<string | null>(null);
  const [nicheAnalysis, setNicheAnalysis] = useState<any>(null);
  const [isDiscovering, setIsDiscovering] = useState(false);

  // Data hooks - live data only
  const { data: niches, isLoading: nichesLoading, isError: nichesError, error: nichesErrorObj, refetch: refetchNiches } = useNiches();
  const { data: nicheProducts, isLoading: productsLoading } = useNicheProducts(selectedNiche?.id || '');

  // Calculate stats
  const totalNiches = niches?.length || 0;
  const trendingNiches = niches?.filter(n => n.trend === 'up' || (n.growth_rate && n.growth_rate > 0)).length || 0;
  const lowSaturation = niches?.filter(n => n.saturation === 'low' || n.saturation_level === 'low').length || 0;

  // Handlers
  const handleRefresh = async () => {
    setIsDiscovering(true);
    try {
      await refetchNiches();
    } finally {
      setIsDiscovering(false);
    }
  };

  const handleExplore = (niche: Niche) => {
    setSelectedNiche(niche);
    setNicheAnalysis(null);
  };

  const handleAnalyze = async (niche: Niche) => {
    setAnalyzingNicheId(niche.id);
    try {
      const result = await nichesAPI.analyze(niche.id);
      setNicheAnalysis(result);
      setSelectedNiche(niche);
    } catch (error) {
      console.error('Niche analysis failed:', error);
      alert('Failed to analyze niche. Please try again.');
    } finally {
      setAnalyzingNicheId(null);
    }
  };

  const handleViewProduct = (productId: string) => {
    setSelectedNiche(null);
    navigate(`/products?id=${productId}`);
  };

  const handleAskOi = async () => {
    // Navigate to intelligence page with context
    navigate('/intelligence');
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-primary flex items-center gap-2">
            <Target className="w-6 h-6 text-accent" />
            Niche Analysis
          </h1>
          <p className="text-sm text-secondary mt-1">
            Discover profitable niches with low saturation
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            className="btn-ghost"
            onClick={handleRefresh}
            disabled={isDiscovering}
          >
            <RefreshCw className={`w-4 h-4 ${isDiscovering ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
          <button className="btn-primary" onClick={handleAskOi}>
            <Brain className="w-4 h-4" />
            <span>Ask Ospra</span>
          </button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="glass-card p-4 text-center">
          <div className="text-2xl font-bold text-primary">{totalNiches}</div>
          <div className="text-xs text-tertiary">Total Niches</div>
        </div>
        <div className="glass-card p-4 text-center">
          <div className="text-2xl font-bold text-green-600">{trendingNiches}</div>
          <div className="text-xs text-tertiary">Trending Up</div>
        </div>
        <div className="glass-card p-4 text-center">
          <div className="text-2xl font-bold text-blue-600">{lowSaturation}</div>
          <div className="text-xs text-tertiary">Low Saturation</div>
        </div>
        <div className="glass-card p-4 text-center">
          <div className="text-2xl font-bold text-amber-600">
            {niches?.filter(n => n.saturation === 'high' || n.saturation_level === 'high').length || 0}
          </div>
          <div className="text-xs text-tertiary">High Saturation</div>
        </div>
      </div>

      {/* Recommendations */}
      {niches && niches.length > 0 && (
        <div className="glass-card p-4">
          <div className="flex items-center gap-2 mb-3">
            <Zap className="w-5 h-5 text-amber-500" />
            <span className="text-sm font-medium text-primary">Top Recommendation</span>
          </div>
          {(() => {
            const bestNiche = [...(niches || [])].sort((a, b) =>
              (b.score || b.overall_score || 0) - (a.score || a.overall_score || 0)
            )[0];

            if (!bestNiche) return null;

            const bestNicheExplanation = generateNicheRationale(bestNiche);

            return (
              <div className="flex items-center gap-4">
                <div className="flex-1 flex items-center gap-2">
                  <div>
                    <span className="text-primary font-medium">{bestNiche.name}</span>
                    <span className="text-secondary"> - Score: {(bestNiche.score || bestNiche.overall_score || 0).toFixed(1)}</span>
                    <span className="text-tertiary ml-2">({bestNiche.saturation || bestNiche.saturation_level} saturation)</span>
                  </div>
                  <ExplainTooltip
                    rationale={bestNicheExplanation.rationale}
                    confidence={bestNicheExplanation.confidence}
                    factors={bestNicheExplanation.factors}
                    position="bottom"
                  />
                </div>
                <button
                  className="btn-primary text-sm"
                  onClick={() => handleExplore(bestNiche)}
                >
                  Explore
                </button>
              </div>
            );
          })()}
        </div>
      )}

      {/* Niche List */}
      {nichesError && (!niches || niches.length === 0) ? (
        <div className="glass-card p-12 text-center">
          <X className="w-16 h-16 text-red-500 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-primary mb-2">Connection Error</h3>
          <p className="text-sm text-secondary mb-6">
            {nichesErrorObj?.message || 'Unable to fetch niches. Backend might be offline.'}
          </p>
          <button
            className="btn-primary"
            onClick={handleRefresh}
            disabled={nichesLoading}
          >
            {nichesLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
            <span>Retry Connection</span>
          </button>
        </div>
      ) : nichesLoading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-8 h-8 text-accent animate-spin" />
        </div>
      ) : !niches || niches.length === 0 ? (
        <div className="glass-card p-12 text-center">
          <Target className="w-12 h-12 text-tertiary mx-auto mb-4" />
          <h3 className="text-lg font-medium text-primary mb-2">No Niches Found</h3>
          <p className="text-sm text-secondary mb-6">
            Niche data will appear once the system starts tracking trends.
          </p>
          <button className="btn-primary" onClick={handleRefresh}>
            <RefreshCw className="w-4 h-4" />
            <span>Refresh Data</span>
          </button>
        </div>
      ) : (
        <div className="space-y-4">
          {niches.map((niche, index) => (
            <NicheCard
              key={niche.id}
              niche={niche}
              onExplore={handleExplore}
              onAnalyze={handleAnalyze}
              isAnalyzing={analyzingNicheId === niche.id}
            />
          ))}
        </div>
      )}

      {/* Niche Detail Modal */}
      <NicheDetailModal
        niche={selectedNiche}
        products={nicheProducts || []}
        isLoadingProducts={productsLoading}
        analysis={nicheAnalysis}
        onClose={() => setSelectedNiche(null)}
        onViewProduct={handleViewProduct}
      />
    </div>
  );
}
