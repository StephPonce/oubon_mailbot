import { Trophy, TrendingUp, TrendingDown, Minus, RefreshCw } from 'lucide-react';
import { useTop20Rankings } from '../../hooks/useData';
import { formatDistanceToNow } from 'date-fns';

interface Top20RankingsProps {
  niche?: string;
  compact?: boolean;
}

export function Top20Rankings({ niche, compact = false }: Top20RankingsProps) {
  const { data, isLoading, isError, refetch, lastUpdated } = useTop20Rankings(niche);

  if (isLoading) {
    return (
      <div className="glass-card p-6">
        <div className="flex items-center justify-center py-12">
          <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-accent"></div>
        </div>
      </div>
    );
  }

  if (isError || !data?.success) {
    return (
      <div className="glass-card p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Trophy className="w-5 h-5 text-accent" />
            <h3 className="text-lg font-semibold text-primary">Top 20 Rankings</h3>
          </div>
        </div>
        <div className="text-center py-8 text-tertiary">
          <p className="text-sm">Unable to load rankings</p>
          <button
            onClick={() => refetch()}
            className="mt-4 btn-ghost text-xs"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Retry</span>
          </button>
        </div>
      </div>
    );
  }

  const rankings = data.rankings || [];
  const displayRankings = compact ? rankings.slice(0, 10) : rankings;

  // Get movement indicator icon
  const getMovementIcon = (change: number, direction: string) => {
    if (direction === 'up' || change > 0) {
      return <TrendingUp className="w-3.5 h-3.5 text-green-600" />;
    } else if (direction === 'down' || change < 0) {
      return <TrendingDown className="w-3.5 h-3.5 text-red-600" />;
    } else {
      return <Minus className="w-3.5 h-3.5 text-tertiary" />;
    }
  };

  return (
    <div className="glass-card p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <Trophy className="w-5 h-5 text-accent" />
          <div>
            <h3 className="text-lg font-semibold text-primary">
              Top {displayRankings.length} Products
            </h3>
            <p className="text-xs text-tertiary">
              {niche ? `${niche} niche` : 'All niches'}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {lastUpdated && (
            <span className="text-xs text-tertiary">
              {formatDistanceToNow(lastUpdated, { addSuffix: true })}
            </span>
          )}
          <button
            onClick={() => refetch()}
            className="p-2 hover:bg-black/5 rounded-lg transition-colors"
            title="Refresh rankings"
          >
            <RefreshCw className="w-4 h-4 text-tertiary" />
          </button>
        </div>
      </div>

      {/* Rankings List */}
      <div className="space-y-2">
        {displayRankings.map((item: any) => {
          const tier = item.tier || {};
          const tierColor = tier.color || '#808080';

          return (
            <div
              key={item.product_id}
              className="flex items-center gap-3 p-3 rounded-lg hover:bg-black/5 transition-colors cursor-pointer group"
              style={{
                borderLeft: `3px solid ${tierColor}20`,
              }}
            >
              {/* Rank & Tier */}
              <div className="flex flex-col items-center min-w-[60px]">
                <div
                  className="text-2xl font-bold mb-1"
                  style={{ color: tierColor }}
                >
                  #{item.rank}
                </div>
                <div className="flex items-center gap-1">
                  <span className="text-lg">{tier.emoji || '📊'}</span>
                  <span className="text-[10px] font-medium uppercase" style={{ color: tierColor }}>
                    {tier.name || 'N/A'}
                  </span>
                </div>
              </div>

              {/* Product Info */}
              <div className="flex-1 min-w-0">
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1 min-w-0">
                    <h4 className="text-sm font-medium text-primary truncate group-hover:text-accent transition-colors">
                      {item.product_name}
                    </h4>
                    <div className="flex items-center gap-2 mt-1">
                      <span className="text-xs px-2 py-0.5 rounded-full bg-black/5 text-secondary">
                        {item.niche}
                      </span>
                      {item.price && (
                        <span className="text-xs text-tertiary">
                          ${item.price.toFixed(2)}
                        </span>
                      )}
                      {item.profit_margin != null && (
                        <span className={`text-xs ${item.profit_margin > 0 ? 'text-green-600' : 'text-red-600'}`}>
                          {item.profit_margin > 0 ? '+' : ''}{item.profit_margin.toFixed(1)}%
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Score & Movement */}
                  <div className="flex flex-col items-end gap-1">
                    <div className="flex items-center gap-1">
                      <span className="text-lg font-bold text-accent">
                        {item.composite_score.toFixed(0)}
                      </span>
                      <span className="text-xs text-tertiary">pts</span>
                    </div>
                    {item.rank_change !== 0 && (
                      <div className="flex items-center gap-1">
                        {getMovementIcon(item.rank_change, item.rank_direction)}
                        <span className={`text-xs font-medium ${
                          item.rank_change > 0 ? 'text-green-600' :
                          item.rank_change < 0 ? 'text-red-600' :
                          'text-tertiary'
                        }`}>
                          {Math.abs(item.rank_change)}
                        </span>
                      </div>
                    )}
                  </div>
                </div>

                {/* Score Breakdown (optional, for non-compact mode) */}
                {!compact && item.score_breakdown && (
                  <div className="mt-2 grid grid-cols-4 gap-2 text-[10px]">
                    <div>
                      <span className="text-tertiary">AI:</span>{' '}
                      <span className="font-medium">{item.score_breakdown.ai_score?.toFixed(0) || 0}</span>
                    </div>
                    <div>
                      <span className="text-tertiary">Vel:</span>{' '}
                      <span className="font-medium">{item.score_breakdown.velocity_score?.toFixed(0) || 0}</span>
                    </div>
                    <div>
                      <span className="text-tertiary">Margin:</span>{' '}
                      <span className="font-medium">{item.score_breakdown.profit_margin?.toFixed(0) || 0}%</span>
                    </div>
                    <div>
                      <span className="text-tertiary">Rate:</span>{' '}
                      <span className="font-medium">{item.score_breakdown.rating?.toFixed(1) || 0}</span>
                    </div>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Footer */}
      {compact && rankings.length > 10 && (
        <div className="mt-4 pt-4 border-t border-black/5 text-center">
          <p className="text-xs text-tertiary">
            Showing top 10 of {rankings.length} products
          </p>
        </div>
      )}

      {data.last_updated && (
        <div className="mt-4 pt-4 border-t border-black/5 text-xs text-tertiary text-center">
          Last updated: {new Date(data.last_updated).toLocaleString()}
        </div>
      )}
    </div>
  );
}
