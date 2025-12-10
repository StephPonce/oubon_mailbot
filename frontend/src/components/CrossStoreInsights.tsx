import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Lightbulb,
  TrendingUp,
  Store,
  X,
  Check,
  ChevronRight,
  AlertCircle,
  Sparkles,
  RefreshCw
} from 'lucide-react';
import { apiClient } from '@/lib/api';
import { cn } from '@/lib/utils';

interface CrossStoreInsight {
  id: number;
  learning_type: string;
  source_store_name: string;
  source_store_niche: string | null;
  product_name: string;
  product_category: string | null;
  source_conversion_rate: number;
  source_revenue: number;
  source_orders: number;
  niche_match_score: number;
  insight: string;
  recommendation: string;
  confidence_score: number;
  projected_conversion_rate: number | null;
  projected_monthly_revenue: number | null;
  projected_roi: number | null;
  status: string;
  created_at: string;
}

interface CrossStoreInsightsProps {
  storeId?: number | null;
  limit?: number;
  className?: string;
}

export function CrossStoreInsights({ storeId, limit = 5, className }: CrossStoreInsightsProps) {
  const [insights, setInsights] = useState<CrossStoreInsight[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const [actioningId, setActioningId] = useState<number | null>(null);

  useEffect(() => {
    if (storeId) {
      fetchInsights();
    } else {
      setLoading(false);
    }
  }, [storeId, limit]);

  const fetchInsights = async () => {
    if (!storeId) return;

    try {
      setLoading(true);
      setError(null);
      const data = await apiClient.get<CrossStoreInsight[]>(
        `/api/stores/${storeId}/insights?limit=${limit}`
      );
      setInsights(data);
    } catch (err: any) {
      console.error('Failed to load insights:', err);
      setError(err.response?.data?.detail || 'Failed to load insights');
    } finally {
      setLoading(false);
    }
  };

  const generateInsights = async () => {
    try {
      setGenerating(true);
      setError(null);
      const result = await apiClient.post<{ learnings_generated: number }>(
        '/api/stores/generate-learnings',
        {}
      );

      // Refresh insights after generation
      await fetchInsights();

      // Show success message (you could use a toast notification here)
      console.log(`Generated ${result.learnings_generated} new insights`);
    } catch (err: any) {
      console.error('Failed to generate insights:', err);
      setError(err.response?.data?.detail || 'Failed to generate insights');
    } finally {
      setGenerating(false);
    }
  };

  const applyInsight = async (insightId: number) => {
    try {
      setActioningId(insightId);
      await apiClient.post(`/api/stores/insights/${insightId}/apply`, {});

      // Remove from list
      setInsights(insights.filter(i => i.id !== insightId));
    } catch (err: any) {
      console.error('Failed to apply insight:', err);
      alert(err.response?.data?.detail || 'Failed to apply insight');
    } finally {
      setActioningId(null);
    }
  };

  const dismissInsight = async (insightId: number) => {
    try {
      setActioningId(insightId);
      await apiClient.post(`/api/stores/insights/${insightId}/dismiss`, {});

      // Remove from list
      setInsights(insights.filter(i => i.id !== insightId));
    } catch (err: any) {
      console.error('Failed to dismiss insight:', err);
      alert(err.response?.data?.detail || 'Failed to dismiss insight');
    } finally {
      setActioningId(null);
    }
  };

  const getConfidenceColor = (score: number): string => {
    if (score >= 80) return 'text-green-600 bg-green-500/10';
    if (score >= 60) return 'text-yellow-600 bg-yellow-500/10';
    return 'text-orange-600 bg-orange-500/10';
  };

  const getNicheMatchColor = (score: number): string => {
    if (score >= 80) return 'text-blue-600';
    if (score >= 60) return 'text-purple-600';
    return 'text-gray-600';
  };

  if (!storeId) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className={cn("glass p-6 rounded-2xl", className)}
      >
        <div className="flex items-center gap-3">
          <Lightbulb className="w-5 h-5 text-purple-400" />
          <div>
            <p className="text-sm font-medium text-white">No Store Selected</p>
            <p className="text-xs text-gray-400 mt-1">
              Select a store to view cross-store insights
            </p>
          </div>
        </div>
      </motion.div>
    );
  }

  if (loading && insights.length === 0) {
    return (
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className={cn("glass p-6 rounded-2xl", className)}
      >
        <div className="flex items-center gap-3">
          <Lightbulb className="w-5 h-5 animate-pulse text-purple-400" />
          <p className="text-sm text-gray-400">Loading insights...</p>
        </div>
      </motion.div>
    );
  }

  if (error) {
    return (
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className={cn("glass p-6 rounded-2xl border border-red-500/20", className)}
      >
        <div className="flex items-center gap-3">
          <AlertCircle className="w-5 h-5 text-red-400" />
          <div className="flex-1">
            <p className="text-sm text-red-400">{error}</p>
            <button
              onClick={fetchInsights}
              className="text-xs text-purple-400 hover:text-purple-300 mt-1 underline"
            >
              Try again
            </button>
          </div>
        </div>
      </motion.div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      className={cn("glass p-6 rounded-2xl", className)}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-gradient-to-br from-purple-500/20 to-pink-500/20">
            <Lightbulb className="w-6 h-6 text-purple-400" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-white">Cross-Store Insights</h2>
            <p className="text-xs text-gray-400">
              AI-powered recommendations from your other stores
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={generateInsights}
            disabled={generating}
            className="px-3 py-1.5 rounded-lg bg-purple-500/20 hover:bg-purple-500/30 text-purple-300 text-xs font-medium border border-purple-500/30 hover:border-purple-500/50 transition-all disabled:opacity-50 flex items-center gap-1"
          >
            <RefreshCw className={cn("w-3 h-3", generating && "animate-spin")} />
            {generating ? 'Generating...' : 'Generate'}
          </button>
        </div>
      </div>

      {/* Insights List */}
      {insights.length === 0 ? (
        <div className="text-center py-12">
          <Sparkles className="w-12 h-12 text-gray-600 mx-auto mb-3" />
          <p className="text-sm text-gray-400 mb-2">No insights available yet</p>
          <p className="text-xs text-gray-500 mb-4">
            Generate insights to discover winning products from your other stores
          </p>
          <button
            onClick={generateInsights}
            disabled={generating}
            className="px-4 py-2 rounded-lg bg-purple-500/20 hover:bg-purple-500/30 text-purple-300 text-sm font-medium border border-purple-500/30 hover:border-purple-500/50 transition-all disabled:opacity-50"
          >
            Generate Insights
          </button>
        </div>
      ) : (
        <div className="space-y-4">
          <AnimatePresence mode="popLayout">
            {insights.map((insight) => (
              <motion.div
                key={insight.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                transition={{ duration: 0.2 }}
                className="p-4 rounded-lg bg-white/5 border border-white/10 hover:bg-white/10 transition-colors"
              >
                {/* Header */}
                <div className="flex items-start justify-between gap-3 mb-3">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <Store className="w-4 h-4 text-purple-400" />
                      <span className="text-sm font-medium text-white">
                        {insight.source_store_name}
                      </span>
                      {insight.source_store_niche && (
                        <span className="px-2 py-0.5 rounded-full bg-blue-500/20 text-blue-300 text-[10px] font-medium">
                          {insight.source_store_niche}
                        </span>
                      )}
                    </div>
                    <h3 className="text-base font-semibold text-white">
                      {insight.product_name}
                    </h3>
                    {insight.product_category && (
                      <p className="text-xs text-gray-400 mt-1">{insight.product_category}</p>
                    )}
                  </div>

                  <div className="flex items-center gap-2">
                    <span className={cn(
                      "px-2 py-1 rounded-lg text-xs font-medium",
                      getConfidenceColor(insight.confidence_score)
                    )}>
                      {insight.confidence_score}% confidence
                    </span>
                  </div>
                </div>

                {/* Metrics */}
                <div className="grid grid-cols-3 gap-3 mb-3">
                  <div className="p-2 rounded-lg bg-black/20">
                    <div className="text-[10px] text-gray-400 uppercase tracking-wide mb-1">
                      Conversion Rate
                    </div>
                    <div className="text-sm font-semibold text-green-400">
                      {insight.source_conversion_rate.toFixed(1)}%
                    </div>
                  </div>
                  <div className="p-2 rounded-lg bg-black/20">
                    <div className="text-[10px] text-gray-400 uppercase tracking-wide mb-1">
                      Revenue
                    </div>
                    <div className="text-sm font-semibold text-blue-400">
                      ${insight.source_revenue.toLocaleString()}
                    </div>
                  </div>
                  <div className="p-2 rounded-lg bg-black/20">
                    <div className="text-[10px] text-gray-400 uppercase tracking-wide mb-1">
                      Niche Match
                    </div>
                    <div className={cn(
                      "text-sm font-semibold",
                      getNicheMatchColor(insight.niche_match_score)
                    )}>
                      {insight.niche_match_score.toFixed(0)}%
                    </div>
                  </div>
                </div>

                {/* Insight & Recommendation */}
                <div className="mb-3">
                  <div className="p-3 rounded-lg bg-purple-500/10 border border-purple-500/20 mb-2">
                    <div className="text-[10px] text-purple-300 uppercase tracking-wide mb-1 flex items-center gap-1">
                      <Sparkles className="w-3 h-3" />
                      Insight
                    </div>
                    <p className="text-xs text-white">{insight.insight}</p>
                  </div>

                  <div className="p-3 rounded-lg bg-blue-500/10 border border-blue-500/20">
                    <div className="text-[10px] text-blue-300 uppercase tracking-wide mb-1 flex items-center gap-1">
                      <TrendingUp className="w-3 h-3" />
                      Recommendation
                    </div>
                    <p className="text-xs text-white">{insight.recommendation}</p>
                  </div>
                </div>

                {/* Projections */}
                {(insight.projected_conversion_rate || insight.projected_monthly_revenue || insight.projected_roi) && (
                  <div className="grid grid-cols-3 gap-2 mb-3">
                    {insight.projected_conversion_rate && (
                      <div className="p-2 rounded-lg bg-green-500/10">
                        <div className="text-[10px] text-gray-400 uppercase tracking-wide">
                          Projected CVR
                        </div>
                        <div className="text-sm font-semibold text-green-400">
                          {insight.projected_conversion_rate.toFixed(1)}%
                        </div>
                      </div>
                    )}
                    {insight.projected_monthly_revenue && (
                      <div className="p-2 rounded-lg bg-blue-500/10">
                        <div className="text-[10px] text-gray-400 uppercase tracking-wide">
                          Projected Revenue
                        </div>
                        <div className="text-sm font-semibold text-blue-400">
                          ${insight.projected_monthly_revenue.toLocaleString()}
                        </div>
                      </div>
                    )}
                    {insight.projected_roi && (
                      <div className="p-2 rounded-lg bg-yellow-500/10">
                        <div className="text-[10px] text-gray-400 uppercase tracking-wide">
                          ROI
                        </div>
                        <div className="text-sm font-semibold text-yellow-400">
                          {insight.projected_roi.toFixed(0)}%
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* Actions */}
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => applyInsight(insight.id)}
                    disabled={actioningId === insight.id}
                    className="flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-lg bg-green-500/20 hover:bg-green-500/30 text-green-300 text-xs font-medium border border-green-500/30 hover:border-green-500/50 transition-all disabled:opacity-50"
                  >
                    <Check className="w-3 h-3" />
                    {actioningId === insight.id ? 'Applying...' : 'Apply'}
                  </button>
                  <button
                    onClick={() => dismissInsight(insight.id)}
                    disabled={actioningId === insight.id}
                    className="flex items-center justify-center gap-2 px-3 py-2 rounded-lg bg-gray-500/20 hover:bg-gray-500/30 text-gray-300 text-xs font-medium border border-gray-500/30 hover:border-gray-500/50 transition-all disabled:opacity-50"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </div>
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
      )}
    </motion.div>
  );
}
