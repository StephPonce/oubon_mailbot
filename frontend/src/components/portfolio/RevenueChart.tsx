import React from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer
} from 'recharts';
import { TrendingUp } from 'lucide-react';

interface StoreRanking {
  id: number;
  store_name: string;
  platform: string;
  monthly_revenue: number;
  total_revenue: number;
}

interface RevenueChartProps {
  rankings: StoreRanking[];
}

// Generate mock data for last 30 days
const generateMockData = (rankings: StoreRanking[]) => {
  const data = [];
  const today = new Date();

  for (let i = 29; i >= 0; i--) {
    const date = new Date(today);
    date.setDate(date.getDate() - i);

    const dataPoint: any = {
      date: date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
      total: 0
    };

    // Add revenue for each store (mock progressive growth)
    rankings.forEach(store => {
      const baseRevenue = store.monthly_revenue / 30; // Daily average
      const randomVariation = baseRevenue * (0.8 + Math.random() * 0.4); // ±20% variation
      const storeRevenue = Math.round(randomVariation);

      dataPoint[store.store_name] = storeRevenue;
      dataPoint.total += storeRevenue;
    });

    data.push(dataPoint);
  }

  return data;
};

// Platform colors for lines
const platformColors: Record<string, string> = {
  shopify: '#8B5CF6',
  amazon: '#F97316',
  woocommerce: '#3B82F6',
  etsy: '#EC4899',
  ebay: '#EAB308'
};

const RevenueChart: React.FC<RevenueChartProps> = ({ rankings }) => {
  const data = generateMockData(rankings);

  // Custom tooltip
  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-gray-800 border border-gray-700 rounded-lg p-4 shadow-xl">
          <p className="text-white font-medium mb-2">{label}</p>
          {payload.map((entry: any, index: number) => (
            <div key={index} className="flex items-center gap-2 text-sm">
              <div
                className="w-3 h-3 rounded-full"
                style={{ backgroundColor: entry.color }}
              />
              <span className="text-gray-400">{entry.name}:</span>
              <span className="text-white font-medium">
                ${entry.value.toLocaleString()}
              </span>
            </div>
          ))}
        </div>
      );
    }
    return null;
  };

  return (
    <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-xl font-bold text-white">Revenue Trends</h2>
          <p className="text-sm text-gray-400 mt-1">Last 30 days performance</p>
        </div>
        <div className="flex items-center gap-2 px-4 py-2 bg-green-500/10 rounded-lg">
          <TrendingUp className="w-5 h-5 text-green-400" />
          <span className="text-sm font-medium text-green-400">+12.5%</span>
        </div>
      </div>

      {/* Chart */}
      <div className="h-80">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
            <XAxis
              dataKey="date"
              stroke="#9CA3AF"
              tick={{ fill: '#9CA3AF' }}
              tickLine={{ stroke: '#9CA3AF' }}
            />
            <YAxis
              stroke="#9CA3AF"
              tick={{ fill: '#9CA3AF' }}
              tickLine={{ stroke: '#9CA3AF' }}
              tickFormatter={(value) => `$${(value / 1000).toFixed(0)}k`}
            />
            <Tooltip content={<CustomTooltip />} />
            <Legend
              wrapperStyle={{ paddingTop: '20px' }}
              iconType="circle"
            />

            {/* Line for each store */}
            {rankings.map((store) => (
              <Line
                key={store.id}
                type="monotone"
                dataKey={store.store_name}
                stroke={platformColors[store.platform.toLowerCase()] || '#6B7280'}
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 6 }}
              />
            ))}

            {/* Total line */}
            <Line
              type="monotone"
              dataKey="total"
              stroke="#3B82F6"
              strokeWidth={3}
              dot={false}
              activeDot={{ r: 8 }}
              name="Total Revenue"
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Legend Info */}
      <div className="mt-4 pt-4 border-t border-gray-700 grid grid-cols-2 gap-4">
        <div>
          <p className="text-xs text-gray-500 uppercase">Total (30d)</p>
          <p className="text-lg font-bold text-white">
            ${rankings.reduce((sum, store) => sum + store.monthly_revenue, 0).toLocaleString()}
          </p>
        </div>
        <div>
          <p className="text-xs text-gray-500 uppercase">Daily Average</p>
          <p className="text-lg font-bold text-white">
            ${Math.round(rankings.reduce((sum, store) => sum + store.monthly_revenue, 0) / 30).toLocaleString()}
          </p>
        </div>
      </div>
    </div>
  );
};

export default RevenueChart;
