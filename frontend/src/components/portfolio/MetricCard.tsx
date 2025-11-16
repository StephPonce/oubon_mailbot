import React from 'react';
import { TrendingUp, TrendingDown } from 'lucide-react';

interface MetricCardProps {
  title: string;
  value: string;
  change: number;
  trend: 'up' | 'down';
  icon: React.ComponentType<{ className?: string }>;
  subtitle?: string;
}

const MetricCard: React.FC<MetricCardProps> = ({
  title,
  value,
  change,
  trend,
  icon: Icon,
  subtitle
}) => {
  const isPositive = trend === 'up';
  const changeColor = isPositive ? 'text-green-400' : 'text-red-400';
  const bgColor = isPositive ? 'bg-green-500/10' : 'bg-red-500/10';
  const TrendIcon = isPositive ? TrendingUp : TrendingDown;

  return (
    <div className="bg-gray-800 rounded-lg p-6 border border-gray-700 hover:border-blue-500 transition-all duration-200 hover:shadow-lg hover:shadow-blue-500/20">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-medium text-gray-400">{title}</h3>
        <div className="p-2 bg-blue-500/10 rounded-lg">
          <Icon className="w-5 h-5 text-blue-400" />
        </div>
      </div>

      {/* Value */}
      <div className="mb-2">
        <p className="text-3xl font-bold text-white">{value}</p>
      </div>

      {/* Change & Subtitle */}
      <div className="flex items-center justify-between">
        <div className={`flex items-center gap-1 px-2 py-1 rounded ${bgColor}`}>
          <TrendIcon className={`w-4 h-4 ${changeColor}`} />
          <span className={`text-sm font-medium ${changeColor}`}>
            {Math.abs(change)}{typeof change === 'number' && change % 1 !== 0 ? '%' : ''}
          </span>
        </div>
        {subtitle && (
          <span className="text-xs text-gray-500">{subtitle}</span>
        )}
      </div>
    </div>
  );
};

export default MetricCard;
