import React, { lazy, Suspense } from 'react';
import { TrendingUp } from 'lucide-react';

// Dynamically import recharts components
const LazyLineChart = lazy(() => import('recharts').then(module => ({ default: module.LineChart })));
const LazyLine = lazy(() => import('recharts').then(module => ({ default: module.Line })));
const LazyXAxis = lazy(() => import('recharts').then(module => ({ default: module.XAxis })));
const LazyYAxis = lazy(() => import('recharts').then(module => ({ default: module.YAxis })));
const LazyCartesianGrid = lazy(() => import('recharts').then(module => ({ default: module.CartesianGrid })));
const LazyTooltip = lazy(() => import('recharts').then(module => ({ default: module.Tooltip })));
const LazyLegend = lazy(() => import('recharts').then(module => ({ default: module.Legend })));
const LazyResponsiveContainer = lazy(() => import('recharts').then(module => ({ default: module.ResponsiveContainer })));

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

interface ChartDataPoint {
  date: string;
  total: number;
  [key: string]: number | string; // For dynamic store revenue properties
}

// Generate mock data for last 30 days
const generateMockData = (rankings: StoreRanking[]) => {
  const data = [];
  const today = new Date();

  for (let i = 29; i >= 0; i--) {
    const date = new Date(today);
    date.setDate(date.getDate() - i);

    const dataPoint: ChartDataPoint = {
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

// Fallback component for Suspense
const LoadingChart = () => (
  <div className="flex items-center justify-center h-full text-tertiary">
    <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-blue-500"></div>
    <span className="ml-3">Loading Chart...</span>
  </div>
);

const RevenueChart: React.FC<RevenueChartProps> = ({ rankings }) => {
  const data = generateMockData(rankings);

  // Custom tooltip
  interface CustomTooltipProps {
  active?: boolean;
  payload?: Array<{
    name: string;
    value: number;
    color: string;
    dataKey: string;
    payload: ChartDataPoint;
  }>;
  label?: string;
}

const CustomTooltip = ({ active, payload, label }: CustomTooltipProps) => {
  if (active && payload && payload.length) {
    return (
      <div className="bg-gray-800 border border-gray-700 rounded-lg p-4 shadow-xl">
        <p className="text-white font-medium mb-2">{label}</p>
        {payload.map((entry, index: number) => (
          <div key={index} className="flex items-center gap-2 text-sm">
            <div
              className="w-3 h-3 rounded-full"
              style={{ backgroundColor: entry.color }}
            />
            <span className="text-tertiary">{entry.name}:</span>
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
          <p className="text-sm text-tertiary mt-1">Last 30 days performance</p>
        </div>
        <div className="flex items-center gap-2 px-4 py-2 bg-green-500/100/10 rounded-lg">
          <TrendingUp className="w-5 h-5 text-green-400" />
          <span className="text-sm font-medium text-green-400">+12.5%</span>
        </div>
      </div>

      {/* Chart */}
      <div className="h-80">
        <Suspense fallback={<LoadingChart />}>
          <LazyResponsiveContainer width="100%" height="100%">
            <LazyLineChart data={data}>
              <LazyCartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <LazyXAxis
                dataKey="date"
                stroke="#9CA3AF"
                tick={{ fill: '#9CA3AF' }}
                tickLine={{ stroke: '#9CA3AF' }}
              />
              <LazyYAxis
                stroke="#9CA3AF"
                tick={{ fill: '#9CA3AF' }}
                tickLine={{ stroke: '#9CA3AF' }}
                tickFormatter={(value) => `$${(value / 1000).toFixed(0)}k`}
              />
              <LazyTooltip content={<CustomTooltip />} />
              <LazyLegend
                wrapperStyle={{ paddingTop: '20px' }}
                iconType="circle"
              />

              {/* Line for each store */}
              {rankings.map((store) => (
                <LazyLine
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
              <LazyLine
                type="monotone"
                dataKey="total"
                stroke="#3B82F6"
                strokeWidth={3}
                dot={false}
                activeDot={{ r: 8 }}
                name="Total Revenue"
              />
            </LazyLineChart>
          </LazyResponsiveContainer>
        </Suspense>
      </div>

      {/* Legend Info */}
      <div className="mt-4 pt-4 border-t border-gray-700 grid grid-cols-2 gap-4">
        <div>
          <p className="text-xs text-tertiary uppercase">Total (30d)</p>
          <p className="text-lg font-bold text-white">
            ${rankings.reduce((sum, store) => sum + store.monthly_revenue, 0).toLocaleString()}
          </p>
        </div>
        <div>
          <p className="text-xs text-tertiary uppercase">Daily Average</p>
          <p className="text-lg font-bold text-white">
            ${Math.round(rankings.reduce((sum, store) => sum + store.monthly_revenue, 0) / 30).toLocaleString()}
          </p>
        </div>
      </div>
    </div>
  );
};

export default RevenueChart;
