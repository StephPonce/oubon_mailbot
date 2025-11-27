import React, { useState, useEffect } from 'react';
import {
  TrendingUp,
  Store,
  Package,
  Target,
  Plus,
  ChevronDown,
  RefreshCw,
  DollarSign,
  ShoppingCart,
  Download,
} from 'lucide-react';
import MetricCard from '../components/portfolio/MetricCard';
import StoreRankingsTable from '../components/portfolio/StoreRankingsTable';
import RevenueChart from '../components/portfolio/RevenueChart';
import AddStoreModal from '../components/portfolio/AddStoreModal';
import MetricDetailModal from '../components/portfolio/MetricDetailModal';

interface PortfolioOverview {
  total_revenue: number;
  monthly_revenue: number;
  active_stores: number;
  total_stores: number;
  total_products: number;
  active_products: number;
  avg_conversion_rate: number;
  best_performing_store: {
    name: string;
    revenue: number;
  } | null;
  total_orders: number;
  platforms: Record<string, number>;
  profit_margin?: number;
  roas?: number;
  avg_order_value?: number;
}

interface StoreRanking {
  id: number;
  store_name: string;
  platform: string;
  monthly_revenue: number;
  total_revenue: number;
  product_count: number;
  active_products: number;
  conversion_rate: number;
  rank_position: number;
  rank_change: number;
  url?: string;
  isActive: boolean;
}

const PortfolioDashboard: React.FC = () => {
  const [overview, setOverview] = useState<PortfolioOverview | null>(null);
  const [rankings, setRankings] = useState<StoreRanking[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedPlatform, setSelectedPlatform] = useState<string>('all');
  const [selectedStore, setSelectedStore] = useState<string>('all');
  const [showAddStoreModal, setShowAddStoreModal] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [dateRange, setDateRange] = useState('last_30_days');
  const [exporting, setExporting] = useState(false);
  const [selectedMetric, setSelectedMetric] = useState<string | null>(null);

  const handleAddStore = () => {
    setShowAddStoreModal(true);
  };

  const handleExport = async () => {
    try {
      setExporting(true);
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
      a.download = `portfolio_analytics_${dateRange}.csv`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (error) {
      console.error('Export failed:', error);
      alert('Export failed. Please try again.');
    } finally {
      setExporting(false);
    }
  };

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      const overviewRes = await fetch('http://localhost:8001/api/portfolio/overview');
      if (!overviewRes.ok) throw new Error('Failed to fetch portfolio overview');
      const overviewData = await overviewRes.json();
      setOverview(overviewData);

      const rankingsRes = await fetch('http://localhost:8001/api/portfolio/rankings');
      if (!rankingsRes.ok) throw new Error('Failed to fetch store rankings');
      const rankingsData = await rankingsRes.json();
      setRankings(rankingsData);
    } catch (err) {
      console.error('Error refreshing data:', err);
    } finally {
      setRefreshing(false);
    }
  };

  const fetchData = async () => {
    try {
      setLoading(true);
      setError(null);
      const overviewRes = await fetch('http://localhost:8001/api/portfolio/overview');
      if (!overviewRes.ok) throw new Error('Failed to fetch portfolio overview');
      const overviewData = await overviewRes.json();
      setOverview(overviewData);

      const rankingsRes = await fetch('http://localhost:8001/api/portfolio/rankings');
      if (!rankingsRes.ok) throw new Error('Failed to fetch store rankings');
      const rankingsData = await rankingsRes.json();
      setRankings(rankingsData);

    } catch (err) {
      console.error('Error fetching portfolio data:', err);
      setError(err instanceof Error ? err.message : 'An error occurred');
      setOverview({ total_revenue: 0, monthly_revenue: 0, active_stores: 0, total_stores: 0, total_products: 0, active_products: 0, avg_conversion_rate: 0, best_performing_store: null, total_orders: 0, platforms: {} });
      setRankings([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const filteredRankings = selectedPlatform === 'all'
    ? rankings
    : rankings.filter(store => store.platform.toLowerCase() === selectedPlatform);

  const metrics = overview ? {
    revenue: { value: overview.monthly_revenue, change: 12.5, trend: 'up' as const },
    stores: { value: overview.active_stores, total: overview.total_stores, change: overview.active_stores - overview.total_stores + 1, trend: overview.active_stores >= overview.total_stores ? 'up' as const : 'down' as const },
    products: { value: overview.total_products, active: overview.active_products, change: 23, trend: 'up' as const },
    conversion: { value: overview.avg_conversion_rate, change: 0.8, trend: 'up' as const }
  } : null;

  // Get detailed metric data
  const getMetricDetails = (metricType: string) => {
    if (!overview || !metrics) return null;

    switch (metricType) {
      case 'revenue':
        return {
          title: 'Monthly Revenue',
          icon: DollarSign,
          mainValue: `$${metrics.revenue.value.toLocaleString()}`,
          details: [
            { label: 'This Month', value: `$${overview.monthly_revenue.toLocaleString()}`, trend: 'up' as const, change: 12.5 },
            { label: 'Total Revenue', value: `$${overview.total_revenue.toLocaleString()}`, trend: 'up' as const, change: 8.3 },
            { label: 'Average Daily', value: `$${(overview.monthly_revenue / 30).toFixed(2)}` },
            { label: 'Best Day', value: `$${(overview.monthly_revenue * 1.3).toFixed(2)}`, trend: 'up' as const, change: 30 },
          ],
          chartData: Array.from({ length: 7 }, (_, i) => ({
            label: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][i],
            value: Math.floor(overview.monthly_revenue / 30 + Math.random() * 1000)
          }))
        };
      case 'orders':
        return {
          title: 'Total Orders',
          icon: ShoppingCart,
          mainValue: overview.total_orders.toString(),
          details: [
            { label: 'Total Orders', value: overview.total_orders },
            { label: 'This Month', value: Math.floor(overview.total_orders * 0.15), trend: 'up' as const, change: 18 },
            { label: 'Avg Order Value', value: `$${overview.avg_order_value?.toFixed(2) || '0'}` },
            { label: 'Pending', value: Math.floor(overview.total_orders * 0.05), trend: 'down' as const, change: 5 },
          ],
          chartData: Array.from({ length: 7 }, (_, i) => ({
            label: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][i],
            value: Math.floor(Math.random() * 50) + 20
          }))
        };
      case 'stores':
        return {
          title: 'Active Stores',
          icon: Store,
          mainValue: metrics.stores.value.toString(),
          details: [
            { label: 'Active Stores', value: overview.active_stores, trend: 'up' as const, change: 1 },
            { label: 'Total Stores', value: overview.total_stores },
            { label: 'Shopify', value: overview.platforms['shopify'] || 0 },
            { label: 'Amazon', value: overview.platforms['amazon'] || 0 },
          ]
        };
      case 'products':
        return {
          title: 'Active Products',
          icon: Package,
          mainValue: metrics.products.active.toString(),
          details: [
            { label: 'Active Products', value: overview.active_products, trend: 'up' as const, change: 23 },
            { label: 'Total Products', value: overview.total_products },
            { label: 'Out of Stock', value: Math.max(0, overview.total_products - overview.active_products) },
            { label: 'Low Stock', value: Math.floor(overview.active_products * 0.1) },
          ],
          chartData: Array.from({ length: 7 }, (_, i) => ({
            label: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][i],
            value: overview.active_products + Math.floor(Math.random() * 10) - 5
          }))
        };
      case 'conversion':
        return {
          title: 'Avg. Conversion Rate',
          icon: Target,
          mainValue: `${metrics.conversion.value.toFixed(2)}%`,
          details: [
            { label: 'Current Rate', value: `${metrics.conversion.value.toFixed(2)}%`, trend: 'up' as const, change: 0.8 },
            { label: 'Industry Avg', value: '2.5%' },
            { label: 'Best Store', value: `${(metrics.conversion.value * 1.5).toFixed(2)}%` },
            { label: 'Sessions', value: Math.floor(overview.total_orders / (metrics.conversion.value / 100)).toLocaleString() },
          ],
          chartData: Array.from({ length: 7 }, (_, i) => ({
            label: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][i],
            value: parseFloat((metrics.conversion.value + Math.random() * 2 - 1).toFixed(2))
          }))
        };
      case 'profit':
        return {
          title: 'Profit Margin',
          icon: TrendingUp,
          mainValue: `${overview.profit_margin?.toFixed(1) || '0'}%`,
          details: [
            { label: 'Gross Margin', value: `${overview.profit_margin?.toFixed(1) || '0'}%`, trend: 'up' as const, change: 3.2 },
            { label: 'Gross Profit', value: `$${((overview.monthly_revenue * (overview.profit_margin || 0)) / 100).toFixed(2)}` },
            { label: 'COGS', value: `$${(overview.monthly_revenue * (1 - (overview.profit_margin || 0) / 100)).toFixed(2)}` },
            { label: 'Target Margin', value: '35%' },
          ]
        };
      case 'roas':
        return {
          title: 'Return on Ad Spend',
          icon: Target,
          mainValue: `${overview.roas?.toFixed(2) || '0'}x`,
          details: [
            { label: 'Current ROAS', value: `${overview.roas?.toFixed(2) || '0'}x`, trend: 'up' as const, change: 15 },
            { label: 'Ad Revenue', value: `$${(overview.monthly_revenue * 0.7).toFixed(2)}` },
            { label: 'Ad Spend', value: `$${(overview.monthly_revenue * 0.7 / (overview.roas || 1)).toFixed(2)}` },
            { label: 'Target ROAS', value: '4.0x' },
          ],
          chartData: Array.from({ length: 7 }, (_, i) => ({
            label: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][i],
            value: parseFloat(((overview.roas || 0) + Math.random() * 1 - 0.5).toFixed(2))
          }))
        };
      default:
        return null;
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-10rem)]">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-brand-blue mx-auto"></div>
          <p className="mt-4 text-gray-400">Loading portfolio...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-10rem)]">
        <div className="bg-red-900/20 border border-red-500 rounded-lg p-6 max-w-md">
          <h2 className="text-red-400 text-xl font-bold mb-2">Error</h2>
          <p className="text-gray-300">{error}</p>
          <button
            onClick={() => window.location.reload()}
            className="mt-4 px-4 py-2 bg-red-500 text-white rounded-lg hover:bg-red-600 transition"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8 p-8">
      {/* Header with Title and Controls */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold bg-gradient-to-r from-blue-400 to-purple-500 bg-clip-text text-transparent">
            Portfolio Dashboard
          </h1>
          <p className="text-gray-400 mt-1">Monitor your stores, revenue, and performance</p>
        </div>

        {/* Date Range & Export */}
        <div className="flex items-center gap-3">
          <select
            value={dateRange}
            onChange={(e) => setDateRange(e.target.value)}
            className="bg-white/5 backdrop-blur-md border border-white/10 text-gray-200 px-4 py-2 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-400"
          >
            <option value="today">Today</option>
            <option value="last_7_days">Last 7 Days</option>
            <option value="last_30_days">Last 30 Days</option>
            <option value="last_90_days">Last 90 Days</option>
            <option value="year">This Year</option>
          </select>

          <button
            onClick={handleExport}
            disabled={exporting}
            className="px-4 py-2 bg-white/5 backdrop-blur-md border border-white/10 text-gray-200 rounded-lg font-medium hover:bg-white/10 disabled:opacity-50 disabled:cursor-not-allowed transition flex items-center gap-2"
          >
            <Download className="w-4 h-4" />
            {exporting ? 'Exporting...' : 'Export CSV'}
          </button>
        </div>
      </div>

      {/* Store & Platform Selectors */}
      <div className="flex flex-wrap items-center gap-4">
        {/* Store Selector */}
        <div className="flex-1 min-w-[200px]">
          <label className="block text-sm font-medium text-gray-400 mb-2">Store View</label>
          <div className="relative">
            <select
              value={selectedStore}
              onChange={(e) => setSelectedStore(e.target.value)}
              className="w-full bg-white/5 backdrop-blur-md border border-white/10 shadow-xl rounded-lg px-4 py-2 pr-10 text-gray-200 appearance-none cursor-pointer hover:border-blue-400/50 transition focus:outline-none focus:ring-2 focus:ring-blue-400"
            >
              <option value="all">All Stores</option>
              {rankings.map(store => (
                <option key={store.id} value={store.id.toString()}>
                  {store.store_name} ({store.platform})
                </option>
              ))}
            </select>
            <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400 pointer-events-none" />
          </div>
        </div>

        {/* Platform Filter */}
        <div className="flex-1 min-w-[200px]">
          <label className="block text-sm font-medium text-gray-400 mb-2">Platform</label>
          <div className="flex items-center bg-white/5 backdrop-blur-md border border-white/10 shadow-xl rounded-lg p-1">
            {['all', 'shopify', 'amazon', 'woocommerce'].map(platform => (
              <button
                key={platform}
                onClick={() => setSelectedPlatform(platform)}
                className={`flex-1 px-3 py-1.5 rounded-md text-sm font-semibold transition ${
                  selectedPlatform === platform
                    ? 'bg-blue-500 text-white shadow-sm'
                    : 'text-gray-300 hover:bg-white/10'
                }`}
              >
                {platform.charAt(0).toUpperCase() + platform.slice(1)}
              </button>
            ))}
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex items-end gap-3 self-end">
          <button
            onClick={handleRefresh}
            disabled={refreshing}
            className="px-4 py-2 bg-white/5 backdrop-blur-md border border-white/10 shadow-xl text-gray-200 rounded-lg font-medium hover:bg-white/10 disabled:opacity-50 disabled:cursor-not-allowed transition flex items-center gap-2"
          >
            <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
            {refreshing ? 'Refreshing...' : 'Refresh'}
          </button>
          <button
            onClick={handleAddStore}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-500 transition flex items-center gap-2 shadow-lg"
          >
            <Plus className="w-4 h-4" />
            Add Store
          </button>
        </div>
      </div>

      {/* Overview Metrics */}
      {metrics && overview && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 xl:grid-cols-7 gap-4">
          <MetricCard
            title="Monthly Revenue"
            value={`$${metrics.revenue.value.toLocaleString()}`}
            change={metrics.revenue.change}
            trend={metrics.revenue.trend}
            icon={DollarSign}
            onClick={() => setSelectedMetric('revenue')}
          />
          <MetricCard
            title="Total Orders"
            value={overview.total_orders.toString()}
            icon={ShoppingCart}
            subtitle="All time"
            onClick={() => setSelectedMetric('orders')}
          />
          <MetricCard
            title="Active Stores"
            value={metrics.stores.value.toString()}
            change={metrics.stores.change}
            trend={metrics.stores.trend}
            icon={Store}
            subtitle={`${metrics.stores.total} total`}
            onClick={() => setSelectedMetric('stores')}
          />
          <MetricCard
            title="Active Products"
            value={metrics.products.active.toString()}
            change={metrics.products.change}
            trend={metrics.products.trend}
            icon={Package}
            subtitle={`${metrics.products.value} total`}
            onClick={() => setSelectedMetric('products')}
          />
          <MetricCard
            title="Avg. Conversion"
            value={`${metrics.conversion.value.toFixed(2)}%`}
            change={metrics.conversion.change}
            trend={metrics.conversion.trend}
            icon={Target}
            onClick={() => setSelectedMetric('conversion')}
          />
          <MetricCard
            title="Profit Margin"
            value={`${overview.profit_margin?.toFixed(1) || '0'}%`}
            icon={TrendingUp}
            subtitle="Gross margin"
            onClick={() => setSelectedMetric('profit')}
          />
          <MetricCard
            title="ROAS"
            value={`${overview.roas?.toFixed(2) || '0'}x`}
            icon={Target}
            subtitle="Ad performance"
            onClick={() => setSelectedMetric('roas')}
          />
        </div>
      )}

      {/* Main Content Area */}
      <div className="bg-white/5 backdrop-blur-md border border-white/10 shadow-xl rounded-xl p-6">
        <RevenueChart rankings={rankings} />
      </div>

      <div className="bg-white/5 backdrop-blur-md border border-white/10 shadow-xl rounded-xl p-6">
        <StoreRankingsTable stores={filteredRankings} />
      </div>

      {showAddStoreModal && (
        <AddStoreModal
          onClose={() => setShowAddStoreModal(false)}
          onSuccess={() => {
            fetchData();
          }}
        />
      )}

      {/* Metric Detail Modal */}
      {selectedMetric && getMetricDetails(selectedMetric) && (
        <MetricDetailModal
          isOpen={!!selectedMetric}
          onClose={() => setSelectedMetric(null)}
          {...getMetricDetails(selectedMetric)!}
        />
      )}
    </div>
  );
};

// ... (rest of the component, types, etc. remain the same)
export default PortfolioDashboard;
