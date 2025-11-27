import React from 'react';
import { X, TrendingUp, TrendingDown, Calendar, DollarSign } from 'lucide-react';

interface MetricDetail {
  label: string;
  value: string | number;
  trend?: 'up' | 'down' | 'neutral';
  change?: number;
}

interface MetricDetailModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  icon: React.ComponentType<{ className?: string }>;
  mainValue: string;
  details: MetricDetail[];
  chartData?: Array<{ label: string; value: number }>;
}

const MetricDetailModal: React.FC<MetricDetailModalProps> = ({
  isOpen,
  onClose,
  title,
  icon: Icon,
  mainValue,
  details,
  chartData
}) => {
  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4"
      onClick={onClose}
    >
      <div
        className="bg-gray-900/95 backdrop-blur-xl border border-gray-700 rounded-2xl p-8 max-w-2xl w-full shadow-2xl animate-fadeIn"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-4">
            <div className="p-3 bg-blue-500/10 rounded-xl">
              <Icon className="w-8 h-8 text-blue-400" />
            </div>
            <div>
              <h2 className="text-2xl font-bold text-white">{title}</h2>
              <p className="text-3xl font-bold text-blue-400 mt-1">{mainValue}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-full hover:bg-white/10 text-gray-400 hover:text-white transition"
          >
            <X className="w-6 h-6" />
          </button>
        </div>

        {/* Details Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
          {details.map((detail, index) => (
            <div
              key={index}
              className="bg-gray-800/50 rounded-xl p-4 border border-gray-700"
            >
              <p className="text-sm text-gray-400 mb-2">{detail.label}</p>
              <div className="flex items-center justify-between">
                <p className="text-xl font-semibold text-white">{detail.value}</p>
                {detail.trend && detail.change !== undefined && (
                  <div className={`flex items-center gap-1 ${
                    detail.trend === 'up' ? 'text-green-400' :
                    detail.trend === 'down' ? 'text-red-400' : 'text-gray-400'
                  }`}>
                    {detail.trend === 'up' ? (
                      <TrendingUp className="w-4 h-4" />
                    ) : detail.trend === 'down' ? (
                      <TrendingDown className="w-4 h-4" />
                    ) : null}
                    <span className="text-sm font-medium">
                      {Math.abs(detail.change)}%
                    </span>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>

        {/* Simple Bar Chart */}
        {chartData && chartData.length > 0 && (
          <div className="bg-gray-800/30 rounded-xl p-6 border border-gray-700">
            <h3 className="text-sm font-medium text-gray-400 mb-4 flex items-center gap-2">
              <Calendar className="w-4 h-4" />
              Last 7 Days Trend
            </h3>
            <div className="flex items-end justify-between gap-2 h-32">
              {chartData.map((item, index) => {
                const maxValue = Math.max(...chartData.map(d => d.value));
                const height = (item.value / maxValue) * 100;
                return (
                  <div key={index} className="flex-1 flex flex-col items-center gap-2">
                    <div className="w-full relative group">
                      <div
                        className="w-full bg-gradient-to-t from-blue-600 to-blue-400 rounded-t-lg hover:from-blue-500 hover:to-blue-300 transition-all"
                        style={{ height: `${height}%`, minHeight: '4px' }}
                      >
                        {/* Tooltip */}
                        <div className="absolute bottom-full mb-2 left-1/2 -translate-x-1/2 bg-gray-800 text-white text-xs rounded px-2 py-1 opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap pointer-events-none">
                          {item.value}
                        </div>
                      </div>
                    </div>
                    <span className="text-xs text-gray-500">{item.label}</span>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Footer */}
        <div className="mt-6 pt-6 border-t border-gray-700">
          <button
            onClick={onClose}
            className="w-full px-6 py-3 bg-blue-600 hover:bg-blue-500 text-white rounded-lg font-semibold transition"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};

export default MetricDetailModal;
