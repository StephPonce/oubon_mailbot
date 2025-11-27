import { useMemo } from 'react';

interface RevenueDataPoint {
  date: string;
  revenue: number;
  orders: number;
}

interface RevenueChartProps {
  data: RevenueDataPoint[];
  loading?: boolean;
}

export default function RevenueChart({ data, loading = false }: RevenueChartProps) {
  const maxRevenue = useMemo(() => {
    return Math.max(...data.map(d => d.revenue), 1);
  }, [data]);

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  };

  return (
    <div className="bg-gray-900/50 backdrop-blur-lg border border-gray-800 rounded-xl p-6">
      <h3 className="text-lg font-semibold text-white mb-6">Revenue Over Time</h3>

      <div className="space-y-4">
        {loading ? (
          <div className="h-64 flex items-center justify-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
          </div>
        ) : data.length === 0 ? (
          <div className="text-center py-12 text-gray-500">
            No revenue data available
          </div>
        ) : (
          <div className="relative h-64">
            {/* Y-axis labels */}
            <div className="absolute left-0 top-0 bottom-0 w-16 flex flex-col justify-between text-xs text-gray-500">
              <span>${maxRevenue.toFixed(0)}</span>
              <span>${(maxRevenue * 0.5).toFixed(0)}</span>
              <span>$0</span>
            </div>

            {/* Chart area */}
            <div className="ml-16 h-full flex items-end justify-around gap-2">
              {data.map((point, index) => {
                const heightPercentage = (point.revenue / maxRevenue) * 100;
                return (
                  <div key={index} className="flex-1 flex flex-col items-center gap-2">
                    {/* Bar */}
                    <div
                      className="w-full bg-gradient-to-t from-blue-600 to-blue-400 rounded-t-lg hover:from-blue-500 hover:to-blue-300 transition-all cursor-pointer relative group"
                      style={{ height: `${heightPercentage}%` }}
                    >
                      {/* Tooltip */}
                      <div className="absolute bottom-full mb-2 left-1/2 -translate-x-1/2 bg-gray-800 text-white text-xs rounded px-2 py-1 opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap">
                        ${point.revenue.toFixed(2)}
                        <br />
                        {point.orders} orders
                      </div>
                    </div>
                    {/* Date label */}
                    <span className="text-xs text-gray-500 rotate-0 text-center">
                      {formatDate(point.date)}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Legend */}
        {data.length > 0 && (
          <div className="flex items-center justify-center gap-4 pt-4 border-t border-gray-800">
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 bg-gradient-to-t from-blue-600 to-blue-400 rounded"></div>
              <span className="text-xs text-gray-400">Revenue</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
