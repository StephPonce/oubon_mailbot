import { useState, useEffect, useCallback } from 'react';
import KPICard from '../components/analytics/KPICard';
import RevenueChart from '../components/analytics/RevenueChart';
import { DollarSign, ShoppingCart, TrendingUp, Target } from 'lucide-react';

interface AnalyticsData {
  revenue: {
    total: number;
    change_percentage: number;
    trend: 'up' | 'down' | 'neutral';
  };
  profit: {
    total: number;
    margin_percentage: number;
  };
  orders: {
    total: number;
    average_order_value: number;
    conversion_rate: number;
  };
  ad_spend: {
    roi: number;
    roas: number;
  };
}

interface RevenueTimeSeriesData {
  data: Array<{
    date: string;
    revenue: number;
    orders: number;
  }>;
}

export const AnalyticsPage: React.FC = () => {
  const [analytics, setAnalytics] = useState<AnalyticsData | null>(null);
  const [revenueData, setRevenueData] = useState<RevenueTimeSeriesData | null>(null);
  const [loading, setLoading] = useState(true);
  const [dateRange, setDateRange] = useState('last_30_days');

  const fetchAnalytics = useCallback(async () => {
    try {
      setLoading(true);

      // Fetch overview data
      const overviewResponse = await fetch(
        `http://localhost:8001/api/analytics/overview?date_range=${dateRange}&user_id=1`
      );

      if (!overviewResponse.ok) {
        throw new Error('Failed to fetch analytics overview');
      }

      const overviewData = await overviewResponse.json();
      setAnalytics(overviewData);

      // Fetch revenue time series
      const revenueResponse = await fetch(
        `http://localhost:8001/api/analytics/revenue?date_range=${dateRange}&granularity=day&user_id=1`
      );

      if (revenueResponse.ok) {
        const revenueTimeSeries = await revenueResponse.json();
        setRevenueData(revenueTimeSeries);
      }
    } catch (error) {
      console.error('Failed to fetch analytics:', error);
    } finally {
      setLoading(false);
    }
  }, [dateRange, setAnalytics, setRevenueData, setLoading]);

  useEffect(() => {
    fetchAnalytics();
  }, [fetchAnalytics]);

  const handleExport = async () => {
    try {
      const response = await fetch(
        `http://localhost:8001/api/analytics/export?format=csv&date_range=${dateRange}&user_id=1`
      );

      if (!response.ok) {
        throw new Error('Export failed');
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `analytics_${dateRange}.csv`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (error) {
      console.error('Export failed:', error);
    }
  };

  return (
    <div className="space-y-8 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white">Analytics Dashboard</h1>
          <p className="text-gray-400 mt-1">Revenue, profit, and performance tracking</p>
        </div>

        <div className="flex items-center gap-4">
          {/* Date Range Selector */}
          <select
            value={dateRange}
            onChange={(e) => setDateRange(e.target.value)}
            className="bg-gray-800 border border-gray-700 text-white px-4 py-2 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="today">Today</option>
            <option value="last_7_days">Last 7 Days</option>
            <option value="last_30_days">Last 30 Days</option>
            <option value="last_90_days">Last 90 Days</option>
            <option value="year">This Year</option>
          </select>

          {/* Export Button */}
          <button
            onClick={handleExport}
            disabled={loading}
            className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Export CSV
          </button>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <KPICard
          title="Total Revenue"
          value={analytics ? `$${analytics.revenue.total.toFixed(2)}` : '$0.00'}
          change={analytics?.revenue.change_percentage}
          trend={analytics?.revenue.trend}
          icon={DollarSign}
          loading={loading}
        />

        <KPICard
          title="Total Orders"
          value={analytics?.orders.total || 0}
          icon={ShoppingCart}
          loading={loading}
        />

        <KPICard
          title="Profit Margin"
          value={analytics ? `${analytics.profit.margin_percentage.toFixed(1)}%` : '0%'}
          icon={TrendingUp}
          loading={loading}
        />

        <KPICard
          title="ROAS"
          value={analytics ? `${analytics.ad_spend.roas.toFixed(2)}x` : '0x'}
          icon={Target}
          loading={loading}
        />
      </div>

      {/* Revenue Chart */}
      <RevenueChart
        data={revenueData?.data || []}
        loading={loading}
      />

      {/* Additional Metrics Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Profit Breakdown */}
        <div className="bg-gradient-to-br from-gray-900 to-gray-800 border border-gray-700 rounded-xl p-6">
          <h3 className="text-lg font-semibold text-white mb-4">Profit Overview</h3>
          {loading ? (
            <div className="space-y-3">
              <div className="h-4 bg-gray-700 animate-pulse rounded" />
              <div className="h-4 bg-gray-700 animate-pulse rounded w-3/4" />
            </div>
          ) : analytics ? (
            <div className="space-y-4">
              <div className="flex justify-between items-center">
                <span className="text-gray-400">Total Profit</span>
                <span className="text-xl font-bold text-green-400">
                  ${analytics.profit.total.toFixed(2)}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-gray-400">Profit Margin</span>
                <span className="text-lg font-semibold text-white">
                  {analytics.profit.margin_percentage.toFixed(1)}%
                </span>
              </div>
            </div>
          ) : (
            <p className="text-gray-500">No data available</p>
          )}
        </div>

        {/* Order Metrics */}
        <div className="bg-gradient-to-br from-gray-900 to-gray-800 border border-gray-700 rounded-xl p-6">
          <h3 className="text-lg font-semibold text-white mb-4">Order Metrics</h3>
          {loading ? (
            <div className="space-y-3">
              <div className="h-4 bg-gray-700 animate-pulse rounded" />
              <div className="h-4 bg-gray-700 animate-pulse rounded w-3/4" />
            </div>
          ) : analytics ? (
            <div className="space-y-4">
              <div className="flex justify-between items-center">
                <span className="text-gray-400">Average Order Value</span>
                <span className="text-xl font-bold text-blue-400">
                  ${analytics.orders.average_order_value.toFixed(2)}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-gray-400">Conversion Rate</span>
                <span className="text-lg font-semibold text-white">
                  {analytics.orders.conversion_rate.toFixed(2)}%
                </span>
              </div>
            </div>
          ) : (
            <p className="text-gray-500">No data available</p>
          )}
        </div>
      </div>

      {/* Empty State */}
      {!loading && !analytics && (
        <div className="text-center py-20 bg-gray-900/50 border-2 border-dashed border-gray-800 rounded-xl">
          <TrendingUp className="w-16 h-16 text-gray-600 mx-auto mb-4" />
          <h3 className="text-xl font-semibold text-gray-400">No Analytics Data</h3>
          <p className="text-gray-500 mt-1">Data will appear here once you have stores and products.</p>
        </div>
      )}
    </div>
  );
};

export default AnalyticsPage;
