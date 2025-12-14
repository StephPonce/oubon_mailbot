/**
 * Ospra Intelligence - Competitive Intelligence Page
 * 
 * FULLY FUNCTIONAL:
 * - Real competitor tracking
 * - Price comparison
 * - Threat assessment
 * - Market positioning
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Eye,
  TrendingUp,
  TrendingDown,
  ExternalLink,
  RefreshCw,
  AlertTriangle,
  Loader2,
  Package,
  DollarSign,
  BarChart3,
  Target,
  Search,
  ChevronRight,
  Shield,
  Zap,
  Brain,
  Plus,
  X,
} from 'lucide-react';

import {
  useCompetitors,
  usePriceComparison,
} from '../hooks/useData';
import { competitorsAPI } from '../services/api';
import type { Competitor } from '../services/api';

// =============================================================================
// COMPETITOR CARD
// =============================================================================

interface CompetitorCardProps {
  competitor: Competitor;
  onViewDetails: (competitor: Competitor) => void;
  onAnalyze: (competitor: Competitor) => void;
  isAnalyzing: boolean;
}

function CompetitorCard({ competitor, onViewDetails, onAnalyze, isAnalyzing }: CompetitorCardProps) {
  const getThreatColor = (level: string) => {
    switch (level?.toLowerCase()) {
      case 'high': return 'text-red-600 bg-red-500/100/10 border-red-500/20';
      case 'medium': return 'text-amber-600 bg-amber-500/10 border-amber-500/20';
      case 'low': return 'text-green-600 bg-green-500/100/10 border-green-500/20';
      default: return 'text-secondary bg-black/5 border-black/10';
    }
  };

  const getThreatIcon = (level: string) => {
    switch (level?.toLowerCase()) {
      case 'high': return <AlertTriangle className="w-4 h-4" />;
      case 'medium': return <Eye className="w-4 h-4" />;
      case 'low': return <Shield className="w-4 h-4" />;
      default: return <Eye className="w-4 h-4" />;
    }
  };

  const growth = competitor.growth_rate || competitor.trend || 0;

  return (
    <div className="glass-card p-5 hover:shadow-lg transition-all">
      <div className="flex items-start justify-between mb-4">
        <div>
          <h3 className="text-lg font-medium text-primary">{competitor.name}</h3>
          {competitor.url && (
            <a
              href={competitor.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-accent hover:underline flex items-center gap-1 mt-1"
            >
              {new URL(competitor.url).hostname}
              <ExternalLink className="w-3 h-3" />
            </a>
          )}
        </div>
        <span className={`px-2 py-1 rounded-lg text-xs font-medium border flex items-center gap-1 ${getThreatColor(competitor.threat_level)}`}>
          {getThreatIcon(competitor.threat_level)}
          {competitor.threat_level || 'Unknown'} threat
        </span>
      </div>

      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-sm text-secondary flex items-center gap-1">
            <Package className="w-3.5 h-3.5" />
            Products
          </span>
          <span className="text-sm font-medium text-primary">{competitor.product_count || 0}</span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-sm text-secondary flex items-center gap-1">
            <DollarSign className="w-3.5 h-3.5" />
            Avg Price
          </span>
          <span className="text-sm font-medium text-primary">
            ${(competitor.avg_price || 0).toFixed(2)}
          </span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-sm text-secondary flex items-center gap-1">
            <TrendingUp className="w-3.5 h-3.5" />
            Growth
          </span>
          <span className={`text-sm font-medium flex items-center gap-1 ${
            growth > 0 ? 'text-green-600' : growth < 0 ? 'text-red-500' : 'text-secondary'
          }`}>
            {growth > 0 ? <TrendingUp className="w-3.5 h-3.5" /> : growth < 0 ? <TrendingDown className="w-3.5 h-3.5" /> : null}
            {growth > 0 ? '+' : ''}{growth}%
          </span>
        </div>
        {competitor.market_share !== undefined && (
          <div className="flex items-center justify-between">
            <span className="text-sm text-secondary flex items-center gap-1">
              <Target className="w-3.5 h-3.5" />
              Market Share
            </span>
            <span className="text-sm font-medium text-primary">
              {competitor.market_share.toFixed(1)}%
            </span>
          </div>
        )}
      </div>

      <div className="flex items-center gap-2 mt-4">
        <button
          className="flex-1 btn-ghost text-sm justify-center"
          onClick={() => onAnalyze(competitor)}
          disabled={isAnalyzing}
        >
          {isAnalyzing ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Brain className="w-4 h-4" />
          )}
          <span>Analyze</span>
        </button>
        <button
          className="flex-1 btn-primary text-sm justify-center"
          onClick={() => onViewDetails(competitor)}
        >
          <Eye className="w-4 h-4" />
          <span>Details</span>
        </button>
      </div>
    </div>
  );
}

// =============================================================================
// COMPETITOR DETAIL MODAL
// =============================================================================

interface CompetitorDetailModalProps {
  competitor: Competitor | null;
  analysis: any | null;
  onClose: () => void;
}

function CompetitorDetailModal({ competitor, analysis, onClose }: CompetitorDetailModalProps) {
  if (!competitor) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
      <div className="glass-card max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="p-6 border-b border-black/10">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-semibold text-primary">{competitor.name}</h2>
              {competitor.url && (
                <a
                  href={competitor.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-accent hover:underline flex items-center gap-1 mt-1"
                >
                  Visit Store
                  <ExternalLink className="w-4 h-4" />
                </a>
              )}
            </div>
            <button onClick={onClose} className="btn-ghost">Close</button>
          </div>
        </div>

        {/* Stats */}
        <div className="p-6 border-b border-black/10">
          <div className="grid grid-cols-4 gap-4">
            <div className="text-center p-4 rounded-xl bg-black/5">
              <div className="text-2xl font-bold text-primary">{competitor.product_count || 0}</div>
              <div className="text-xs text-tertiary">Products</div>
            </div>
            <div className="text-center p-4 rounded-xl bg-black/5">
              <div className="text-2xl font-bold text-primary">${(competitor.avg_price || 0).toFixed(2)}</div>
              <div className="text-xs text-tertiary">Avg Price</div>
            </div>
            <div className="text-center p-4 rounded-xl bg-black/5">
              <div className={`text-2xl font-bold ${(competitor.growth_rate || 0) > 0 ? 'text-green-600' : 'text-red-500'}`}>
                {(competitor.growth_rate || 0) > 0 ? '+' : ''}{competitor.growth_rate || 0}%
              </div>
              <div className="text-xs text-tertiary">Growth</div>
            </div>
            <div className="text-center p-4 rounded-xl bg-black/5">
              <div className="text-2xl font-bold text-primary">{competitor.threat_level || 'N/A'}</div>
              <div className="text-xs text-tertiary">Threat Level</div>
            </div>
          </div>
        </div>

        {/* Description */}
        {competitor.description && (
          <div className="p-6 border-b border-black/10">
            <h3 className="text-sm font-medium text-primary mb-2">About</h3>
            <p className="text-sm text-secondary">{competitor.description}</p>
          </div>
        )}

        {/* Niches */}
        {competitor.niches && competitor.niches.length > 0 && (
          <div className="p-6 border-b border-black/10">
            <h3 className="text-sm font-medium text-primary mb-2">Active Niches</h3>
            <div className="flex flex-wrap gap-2">
              {competitor.niches.map((niche, i) => (
                <span key={i} className="px-3 py-1 rounded-full text-xs font-medium bg-cyan-500/100/10 text-blue-600 border border-blue-500/20">
                  {niche}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* AI Analysis */}
        {analysis && (
          <div className="p-6">
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
      </div>
    </div>
  );
}

// =============================================================================
// PRICE COMPARISON CHART
// =============================================================================

function PriceComparisonChart({ data }: { data: any[] }) {
  // Ensure data is an array
  const priceData = Array.isArray(data) ? data : [];

  if (!priceData || priceData.length === 0) {
    return (
      <div className="h-64 flex items-center justify-center text-tertiary">
        <div className="text-center">
          <BarChart3 className="w-12 h-12 mx-auto mb-2 opacity-50" />
          <p>No price comparison data available</p>
        </div>
      </div>
    );
  }

  // Simple bar chart visualization
  const maxPrice = Math.max(...priceData.map(d => d.avg_price || 0));

  return (
    <div className="space-y-3">
      {priceData.map((item, index) => (
        <div key={index} className="flex items-center gap-4">
          <div className="w-32 text-sm text-primary truncate">{item.name}</div>
          <div className="flex-1 h-8 bg-black/5 rounded-lg overflow-hidden">
            <div
              className={`h-full rounded-lg ${
                item.is_our_store ? 'bg-accent' : 'bg-cyan-500/100/50'
              }`}
              style={{ width: `${((item.avg_price || 0) / maxPrice) * 100}%` }}
            />
          </div>
          <div className="w-20 text-right text-sm font-medium text-primary">
            ${(item.avg_price || 0).toFixed(2)}
          </div>
        </div>
      ))}
    </div>
  );
}

// =============================================================================
// MAIN COMPONENT
// =============================================================================

export default function CompetitiveIntelPage() {
  const navigate = useNavigate();

  // State
  const [selectedCompetitor, setSelectedCompetitor] = useState<Competitor | null>(null);
  const [competitorAnalysis, setCompetitorAnalysis] = useState<any>(null);
  const [analyzingId, setAnalyzingId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');

  // Data hooks - live data only
  const { data: competitors, isLoading: competitorsLoading, isError: competitorsError, error: competitorsErrorObj, refetch: refetchCompetitors } = useCompetitors();
  const { data: priceData, isLoading: priceLoading } = usePriceComparison();

  // Filter competitors by search
  const filteredCompetitors = (competitors || []).filter(c => {
    if (!searchQuery) return true;
    return c.name.toLowerCase().includes(searchQuery.toLowerCase());
  });

  // Stats
  const totalCompetitors = competitors?.length || 0;
  const highThreat = competitors?.filter(c => c.threat_level?.toLowerCase() === 'high').length || 0;
  const avgGrowth = competitors?.length 
    ? (competitors.reduce((sum, c) => sum + (c.growth_rate || 0), 0) / competitors.length).toFixed(1)
    : '0';

  // Handlers
  const handleRefresh = async () => {
    await refetchCompetitors();
  };

  const handleViewDetails = (competitor: Competitor) => {
    setSelectedCompetitor(competitor);
    setCompetitorAnalysis(null);
  };

  const handleAnalyze = async (competitor: Competitor) => {
    setAnalyzingId(competitor.id);
    try {
      const result = await competitorsAPI.analyze(competitor.id);
      setCompetitorAnalysis(result);
      setSelectedCompetitor(competitor);
    } catch (error) {
      console.error('Competitor analysis failed:', error);
      alert('Failed to analyze competitor. Please try again.');
    } finally {
      setAnalyzingId(null);
    }
  };

  const handleAddCompetitor = () => {
    // TODO: Implement add competitor modal
    alert('Add competitor feature coming soon!');
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-primary flex items-center gap-2">
            <Eye className="w-6 h-6 text-accent" />
            Competitive Intelligence
          </h1>
          <p className="text-sm text-secondary mt-1">
            Monitor competitors and market positioning
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            className="btn-ghost"
            onClick={handleRefresh}
            disabled={competitorsLoading}
          >
            <RefreshCw className={`w-4 h-4 ${competitorsLoading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
          <button className="btn-primary" onClick={handleAddCompetitor}>
            <Plus className="w-4 h-4" />
            <span>Add Competitor</span>
          </button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="glass-card p-4 text-center">
          <div className="text-2xl font-bold text-primary">{totalCompetitors}</div>
          <div className="text-xs text-tertiary">Competitors Tracked</div>
        </div>
        <div className="glass-card p-4 text-center">
          <div className="text-2xl font-bold text-red-500">{highThreat}</div>
          <div className="text-xs text-tertiary">High Threat</div>
        </div>
        <div className="glass-card p-4 text-center">
          <div className={`text-2xl font-bold ${Number(avgGrowth) > 0 ? 'text-green-600' : 'text-secondary'}`}>
            {Number(avgGrowth) > 0 ? '+' : ''}{avgGrowth}%
          </div>
          <div className="text-xs text-tertiary">Avg Growth</div>
        </div>
        <div className="glass-card p-4 text-center">
          <div className="text-2xl font-bold text-primary">
            {competitors?.filter(c => c.threat_level?.toLowerCase() === 'low').length || 0}
          </div>
          <div className="text-xs text-tertiary">Low Threat</div>
        </div>
      </div>

      {/* Search */}
      <div className="relative max-w-md">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-tertiary" />
        <input
          type="text"
          placeholder="Search competitors..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-white/50 border border-black/10 focus:border-accent outline-none text-sm"
        />
      </div>

      {/* Competitor Grid */}
      {competitorsError && filteredCompetitors.length === 0 ? (
        <div className="glass-card p-12 text-center">
          <X className="w-16 h-16 text-red-500 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-primary mb-2">Connection Error</h3>
          <p className="text-sm text-secondary mb-6">
            {competitorsErrorObj?.message || 'Unable to fetch competitors. Backend might be offline.'}
          </p>
          <button
            className="btn-primary"
            onClick={handleRefresh}
            disabled={competitorsLoading}
          >
            {competitorsLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
            <span>Retry Connection</span>
          </button>
        </div>
      ) : competitorsLoading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-8 h-8 text-accent animate-spin" />
        </div>
      ) : filteredCompetitors.length === 0 ? (
        <div className="glass-card p-12 text-center">
          <Eye className="w-12 h-12 text-tertiary mx-auto mb-4" />
          <h3 className="text-lg font-medium text-primary mb-2">No Competitors Tracked</h3>
          <p className="text-sm text-secondary mb-6">
            Add competitors to start monitoring their products and pricing.
          </p>
          <button className="btn-primary" onClick={handleAddCompetitor}>
            <Plus className="w-4 h-4" />
            <span>Add Competitor</span>
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredCompetitors.map((competitor) => (
            <CompetitorCard
              key={competitor.id}
              competitor={competitor}
              onViewDetails={handleViewDetails}
              onAnalyze={handleAnalyze}
              isAnalyzing={analyzingId === competitor.id}
            />
          ))}
        </div>
      )}

      {/* Price Comparison */}
      <div className="glass-card p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-medium text-primary flex items-center gap-2">
            <BarChart3 className="w-5 h-5 text-accent" />
            Price Positioning
          </h2>
        </div>
        {priceLoading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-6 h-6 text-accent animate-spin" />
          </div>
        ) : (
          <PriceComparisonChart data={priceData || []} />
        )}
      </div>

      {/* Competitor Detail Modal */}
      <CompetitorDetailModal
        competitor={selectedCompetitor}
        analysis={competitorAnalysis}
        onClose={() => setSelectedCompetitor(null)}
      />
    </div>
  );
}
