import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Sunrise, AlertCircle, TrendingUp, Target, Mail, RefreshCw } from 'lucide-react';
import { cn } from '@/lib/utils';
import { apiClient } from '@/lib/api';

interface DailyBriefData {
  timestamp: string;
  greeting: string;
  summary_text: string;
  pending_actions: {
    count: number;
    high_confidence: number;
    by_type: Record<string, number>;
    actions: Array<{
      id: number;
      type: string;
      title: string;
      confidence: number;
      estimated_impact: string;
    }>;
  };
  performance: {
    today: {
      revenue: number;
      orders: number;
    };
    last_7_days: {
      revenue: number;
      orders: number;
    };
    health_score: number;
  };
  opportunities: {
    count: number;
    top_products: Array<{
      product_name: string;
      niche: string;
      margin: number;
    }>;
  };
  priorities: Array<{
    title: string;
    description: string;
    urgency: 'high' | 'medium' | 'low';
    action_type: string;
  }>;
}

interface DailyBriefProps {
  className?: string;
}

export function DailyBrief({ className }: DailyBriefProps) {
  const [brief, setBrief] = useState<DailyBriefData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchBrief = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await apiClient.get<DailyBriefData>('/daily-brief');
      setBrief(response);
    } catch (err) {
      console.error('Failed to load daily brief:', err);
      setError('Failed to load your daily brief. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchBrief();
  }, []);

  if (loading) {
    return (
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className={cn("glass p-6 rounded-2xl", className)}
      >
        <div className="flex items-center gap-3">
          <RefreshCw className="w-5 h-5 animate-spin text-purple-400" />
          <p className="text-sm text-gray-400">Generating your daily brief...</p>
        </div>
      </motion.div>
    );
  }

  if (error || !brief) {
    return (
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className={cn("glass p-6 rounded-2xl border border-red-500/20", className)}
      >
        <div className="flex items-center gap-3">
          <AlertCircle className="w-5 h-5 text-red-400" />
          <div>
            <p className="text-sm text-red-400">{error || 'Failed to load brief'}</p>
            <button
              onClick={fetchBrief}
              className="text-xs text-purple-400 hover:text-purple-300 mt-1 underline"
            >
              Try again
            </button>
          </div>
        </div>
      </motion.div>
    );
  }

  const urgencyColors = {
    high: 'bg-red-500/20 text-red-300 border-red-500/30',
    medium: 'bg-yellow-500/20 text-yellow-300 border-yellow-500/30',
    low: 'bg-blue-500/20 text-blue-300 border-blue-500/30',
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      className={cn("glass p-6 rounded-2xl", className)}
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-gradient-to-br from-orange-500/20 to-pink-500/20">
            <Sunrise className="w-6 h-6 text-orange-400" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-white">{brief.greeting}</h2>
            <p className="text-xs text-gray-400">
              {new Date(brief.timestamp).toLocaleDateString('en-US', {
                weekday: 'long',
                month: 'long',
                day: 'numeric'
              })}
            </p>
          </div>
        </div>

        {/* Quick stats */}
        <div className="flex gap-2">
          <div className="px-3 py-1.5 rounded-lg bg-purple-500/20 text-purple-300 text-xs font-medium border border-purple-500/30">
            {brief.pending_actions.count} Actions
          </div>
          <div className="px-3 py-1.5 rounded-lg bg-blue-500/20 text-blue-300 text-xs font-medium border border-blue-500/30">
            {brief.performance.health_score.toFixed(0)}% Health
          </div>
        </div>
      </div>

      {/* AI Summary */}
      <div className="mb-6">
        <p className="text-sm text-gray-300 leading-relaxed whitespace-pre-line">
          {brief.summary_text}
        </p>
      </div>

      {/* Key Metrics Grid */}
      <div className="grid grid-cols-3 gap-3 mb-6">
        {/* Pending Actions */}
        <div className="p-4 rounded-lg bg-white/5 border border-white/10">
          <div className="flex items-center gap-2 mb-2">
            <Target className="w-4 h-4 text-purple-400" />
            <p className="text-xs text-gray-400">Pending</p>
          </div>
          <p className="text-2xl font-bold text-white">{brief.pending_actions.count}</p>
          <p className="text-xs text-purple-300 mt-1">
            {brief.pending_actions.high_confidence} high confidence
          </p>
        </div>

        {/* Opportunities */}
        <div className="p-4 rounded-lg bg-white/5 border border-white/10">
          <div className="flex items-center gap-2 mb-2">
            <TrendingUp className="w-4 h-4 text-green-400" />
            <p className="text-xs text-gray-400">Opportunities</p>
          </div>
          <p className="text-2xl font-bold text-white">{brief.opportunities.count}</p>
          <p className="text-xs text-green-300 mt-1">
            New products
          </p>
        </div>

        {/* Health Score */}
        <div className="p-4 rounded-lg bg-white/5 border border-white/10">
          <div className="flex items-center gap-2 mb-2">
            <AlertCircle className="w-4 h-4 text-blue-400" />
            <p className="text-xs text-gray-400">Health</p>
          </div>
          <p className="text-2xl font-bold text-white">
            {brief.performance.health_score.toFixed(0)}%
          </p>
          <p className="text-xs text-blue-300 mt-1">
            Overall score
          </p>
        </div>
      </div>

      {/* Priority Items */}
      {brief.priorities.length > 0 && (
        <div className="space-y-2">
          <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
            Today's Priorities
          </h3>
          {brief.priorities.slice(0, 3).map((priority, index) => (
            <div
              key={index}
              className="p-3 rounded-lg bg-white/5 border border-white/10 hover:bg-white/10 transition-colors cursor-pointer"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <span className={cn(
                      "px-2 py-0.5 rounded text-[10px] font-medium border uppercase",
                      urgencyColors[priority.urgency]
                    )}>
                      {priority.urgency}
                    </span>
                    <p className="text-sm font-medium text-white">
                      {priority.title}
                    </p>
                  </div>
                  <p className="text-xs text-gray-400">
                    {priority.description}
                  </p>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Action Button */}
      <button
        onClick={fetchBrief}
        className="w-full mt-6 px-4 py-2.5 rounded-lg bg-gradient-to-r from-purple-500/20 to-pink-500/20
                   hover:from-purple-500/30 hover:to-pink-500/30 text-white text-sm font-medium
                   border border-purple-500/30 hover:border-purple-500/50 transition-all
                   flex items-center justify-center gap-2"
      >
        <Mail className="w-4 h-4" />
        Send Brief via Email
      </button>
    </motion.div>
  );
}
