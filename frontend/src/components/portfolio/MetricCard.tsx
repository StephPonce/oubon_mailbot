import React from 'react';
import { TrendingUp, TrendingDown } from 'lucide-react';

interface MetricCardProps {
  title: string;
  value: string;
  change?: number;
  trend?: 'up' | 'down';
  icon: React.ComponentType<{ className?: string }>;
  subtitle?: string;
  onClick?: () => void;
}

const MetricCard: React.FC<MetricCardProps> = ({
  title,
  value,
  change,
  trend,
  icon: Icon,
  subtitle,
  onClick
}) => {
  const isPositive = trend === 'up';
  const changeColor = isPositive ? 'text-success-green' : 'text-red-400';
  const bgColor = isPositive ? 'bg-success-green/10' : 'bg-red-500/100/10';
  const TrendIcon = isPositive ? TrendingUp : TrendingDown;

  return (
    <div
      onClick={onClick}
      className={`bg-cyan-500/5 backdrop-blur-lg border border-cyan-500/20 shadow-xl rounded-xl p-5 transition-all duration-300 hover:border-cyan-400/40 hover:bg-cyan-500/10 group ${
        onClick ? 'cursor-pointer hover:scale-105 hover:shadow-2xl hover:shadow-cyan-500/10' : ''
      }`}
    >
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-light text-cyan-300">{title}</h3>
        <div className="p-2 bg-black/30 rounded-lg border border-cyan-500/20">
          <Icon className="w-5 h-5 text-cyan-400" />
        </div>
      </div>

      <div className="mb-3">
        <p className="text-3xl font-light text-white">{value}</p>
      </div>

      <div className="flex items-center justify-between text-xs">
        {change !== undefined && trend ? (
          <div className={`flex items-center gap-1 px-2 py-1 rounded-full ${bgColor}`}>
            <TrendIcon className={`w-3 h-3 ${changeColor}`} />
            <span className={`font-semibold ${changeColor}`}>
              {Math.abs(change)}{typeof change === 'number' && change % 1 !== 0 ? '%' : ''}
            </span>
          </div>
        ) : (
          <div></div>
        )}
        {subtitle && (
          <span className="text-cyan-400/60">{subtitle}</span>
        )}
      </div>

      {onClick && (
        <div className="mt-2 text-xs text-cyan-400 opacity-0 group-hover:opacity-100 transition-opacity">
          Click for details →
        </div>
      )}
    </div>
  );
};

export default MetricCard;

