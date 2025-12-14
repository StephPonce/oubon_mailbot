import type { LucideIcon } from 'lucide-react';

interface KPICardProps {
  title: string;
  value: string | number;
  change?: number;
  trend?: 'up' | 'down' | 'neutral';
  icon: LucideIcon;
  subtitle?: string;
  loading?: boolean;
}

export default function KPICard({ title, value, change, trend, icon: Icon, subtitle, loading = false }: KPICardProps) {
  const trendColor = trend === 'up' ? 'text-green-400' : trend === 'down' ? 'text-red-400' : 'text-tertiary';
  const trendSymbol = trend === 'up' ? '↑' : trend === 'down' ? '↓' : '→';

  return (
    <div className="bg-gray-900/50 backdrop-blur-lg border border-gray-800 rounded-xl p-6 hover:border-gray-700 transition-all">
      {loading ? (
        <div className="space-y-3 animate-pulse">
          <div className="flex items-center justify-between">
            <div className="p-2 bg-gray-800 rounded-lg w-10 h-10" />
            <div className="h-4 bg-gray-800 rounded w-16" />
          </div>
          <div className="h-3 bg-gray-800 rounded w-24" />
          <div className="h-8 bg-gray-800 rounded w-32" />
        </div>
      ) : (
        <>
          <div className="flex items-center justify-between mb-4">
            <div className="p-2 bg-cyan-500/100/10 rounded-lg">
              <Icon className="w-5 h-5 text-blue-400" />
            </div>
            {change !== undefined && (
              <span className={`text-sm font-medium ${trendColor}`}>
                {trendSymbol} {Math.abs(change).toFixed(1)}%
              </span>
            )}
          </div>
          <h3 className="text-sm font-medium text-tertiary mb-1">{title}</h3>
          <p className="text-2xl font-bold text-white mb-1">{value}</p>
          {subtitle && <p className="text-xs text-tertiary">{subtitle}</p>}
        </>
      )}
    </div>
  );
}
