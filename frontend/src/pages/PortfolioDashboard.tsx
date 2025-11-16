import React, { useState, useEffect } from 'react';
import {
  TrendingUp,
  TrendingDown,
  Store,
  Package,
  Target,
  Plus,
  Filter,
  ChevronDown,
  RefreshCw,
  DollarSign
} from 'lucide-react';
import MetricCard from '../components/portfolio/MetricCard';
import StoreRankingsTable from '../components/portfolio/StoreRankingsTable';
import RevenueChart from '../components/portfolio/RevenueChart';
import QuickActions from '../components/portfolio/QuickActions';
import AddStoreModal from '../components/portfolio/AddStoreModal';
import AIChat from '../components/AIChat';

// Types
interface PortfolioOverview {
  total_revenue: number;
  monthly_revenue: number;
  active_stores: number;
  total_stores: number;
  total_products: number;
  active_products: number;
  avg_conversion_rate: number;
  best_performing_store: string | null;
  total_orders: number;
  platforms: Record<string, number>;
}

interface StoreRanking {
  id: number;
  store_name: string;
  platform: string;
  monthly_revenue: number;
  total_revenue: number;
  conversion_rate: number;
  product_count: number;
  active_products: number;
  rank_position: number;
  rank_change: number;
  rank_change_label: string;
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

  // Navigation handler for Quick Actions
  const handleNavigate = (page: string) => {
    // Dispatch custom event to notify App component
    window.dispatchEvent(new CustomEvent('navigate', { detail: { page } }));
  };

  // Add store modal handler
  const handleAddStore = () => {
    setShowAddStoreModal(true);
  };

  // Refresh handler
  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      // Fetch overview
      const overviewRes = await fetch('http://localhost:8000/api/portfolio/overview');
      if (!overviewRes.ok) throw new Error('Failed to fetch portfolio overview');
      const overviewData = await overviewRes.json();
      setOverview(overviewData);

      // Fetch rankings
      const rankingsRes = await fetch('http://localhost:8000/api/portfolio/rankings');
      if (!rankingsRes.ok) throw new Error('Failed to fetch store rankings');
      const rankingsData = await rankingsRes.json();
      setRankings(rankingsData);
    } catch (err) {
      console.error('Error refreshing data:', err);
    } finally {
      setRefreshing(false);
    }
  };

  // Fetch portfolio data function (reusable)
  const fetchData = async () => {
    try {
      setLoading(true);
      setError(null);

      // Fetch overview
      const overviewRes = await fetch('http://localhost:8000/api/portfolio/overview');
      if (!overviewRes.ok) throw new Error('Failed to fetch portfolio overview');
      const overviewData = await overviewRes.json();
      setOverview(overviewData);

      // Fetch rankings
      const rankingsRes = await fetch('http://localhost:8000/api/portfolio/rankings');
      if (!rankingsRes.ok) throw new Error('Failed to fetch store rankings');
      const rankingsData = await rankingsRes.json();
      setRankings(rankingsData);

    } catch (err) {
      console.error('Error fetching portfolio data:', err);
      setError(err instanceof Error ? err.message : 'An error occurred');

      // Set default empty state so the page can still render
      setOverview({
        total_revenue: 0,
        monthly_revenue: 0,
        active_stores: 0,
        total_stores: 0,
        total_products: 0,
        active_products: 0,
        avg_conversion_rate: 0,
        best_performing_store: null,
        total_orders: 0,
        platforms: {}
      });
      setRankings([]);
    } finally {
      setLoading(false);
    }
  };

  // Fetch on mount
  useEffect(() => {
    fetchData();
  }, []);

  // Filter rankings by platform
  const filteredRankings = selectedPlatform === 'all'
    ? rankings
    : rankings.filter(store => store.platform.toLowerCase() === selectedPlatform);

  // Calculate metrics changes (mock data for now - would come from API)
  const metrics = overview ? {
    revenue: {
      value: overview.monthly_revenue,
      change: 12.5, // Mock % change
      trend: 'up' as const
    },
    stores: {
      value: overview.active_stores,
      total: overview.total_stores,
      change: overview.active_stores - overview.total_stores + 1, // Mock change
      trend: overview.active_stores >= overview.total_stores ? 'up' as const : 'down' as const
    },
    products: {
      value: overview.total_products,
      active: overview.active_products,
      change: 23, // Mock weekly change
      trend: 'up' as const
    },
    conversion: {
      value: overview.avg_conversion_rate,
      change: 0.8, // Mock % change
      trend: 'up' as const
    }
  } : null;

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-900 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto"></div>
          <p className="mt-4 text-gray-400">Loading portfolio...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-900 flex items-center justify-center">
        <div className="bg-red-900/20 border border-red-500 rounded-lg p-6 max-w-md">
          <h2 className="text-red-500 text-xl font-bold mb-2">Error</h2>
          <p className="text-gray-300">{error}</p>
          <button
            onClick={() => window.location.reload()}
            className="mt-4 px-4 py-2 bg-red-500 text-white rounded hover:bg-red-600 transition"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-900 text-white p-6">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold mb-2 bg-gradient-to-r from-blue-400 to-purple-500 bg-clip-text text-transparent">
          Portfolio Dashboard
        </h1>
        <p className="text-gray-400">
          Managing {overview?.total_stores} store{overview?.total_stores !== 1 ? 's' : ''} across{' '}
          {overview?.platforms ? Object.keys(overview.platforms).length : 0} platform{Object.keys(overview?.platforms || {}).length !== 1 ? 's' : ''}
        </p>
      </div>

      {/* Store & Platform Selectors */}
      <div className="flex flex-wrap gap-4 mb-6">
        {/* Store Selector */}
        <div className="flex-1 min-w-[200px]">
          <label className="block text-sm text-gray-400 mb-2">Store View</label>
          <div className="relative">
            <select
              value={selectedStore}
              onChange={(e) => setSelectedStore(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 pr-10 text-white appearance-none cursor-pointer hover:border-blue-500 transition"
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
          <label className="block text-sm text-gray-400 mb-2">Platform Filter</label>
          <div className="flex gap-2">
            {['all', 'shopify', 'amazon', 'woocommerce'].map(platform => (
              <button
                key={platform}
                onClick={() => setSelectedPlatform(platform)}
                className={`px-4 py-2 rounded-lg font-medium transition ${
                  selectedPlatform === platform
                    ? 'bg-blue-500 text-white'
                    : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
                }`}
              >
                {platform.charAt(0).toUpperCase() + platform.slice(1)}
              </button>
            ))}
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex items-end gap-3">
          {/* Refresh Button */}
          <button
            onClick={handleRefresh}
            disabled={refreshing}
            className="px-6 py-2 bg-gray-800 border border-gray-700 text-white rounded-lg font-medium hover:bg-gray-700 disabled:bg-gray-900 disabled:cursor-not-allowed transition flex items-center gap-2"
          >
            <RefreshCw className={`w-5 h-5 ${refreshing ? 'animate-spin' : ''}`} />
            {refreshing ? 'Refreshing...' : 'Refresh'}
          </button>

          {/* Add Store Button */}
          <button
            onClick={handleAddStore}
            className="px-6 py-2 bg-gradient-to-r from-blue-500 to-purple-600 text-white rounded-lg font-medium hover:from-blue-600 hover:to-purple-700 transition flex items-center gap-2"
          >
            <Plus className="w-5 h-5" />
            Add Store
          </button>
        </div>
      </div>

      {/* Overview Metrics */}
      {metrics && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          <MetricCard
            title="Total Revenue"
            value={`$${metrics.revenue.value.toLocaleString()}`}
            change={metrics.revenue.change}
            trend={metrics.revenue.trend}
            icon={TrendingUp}
            subtitle="This month"
          />
          <MetricCard
            title="Active Stores"
            value={metrics.stores.value.toString()}
            change={metrics.stores.change}
            trend={metrics.stores.trend}
            icon={Store}
            subtitle={`${metrics.stores.total} total stores`}
          />
          <MetricCard
            title="Total Products"
            value={metrics.products.value.toString()}
            change={metrics.products.change}
            trend={metrics.products.trend}
            icon={Package}
            subtitle={`${metrics.products.active} active`}
          />
          <MetricCard
            title="Avg Conversion"
            value={`${metrics.conversion.value.toFixed(2)}%`}
            change={metrics.conversion.change}
            trend={metrics.conversion.trend}
            icon={Target}
            subtitle="Across all stores"
          />
        </div>
      )}

      {/* Revenue Chart & Quick Actions */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
        <div className="lg:col-span-2">
          <RevenueChart rankings={rankings} />
        </div>
        <div>
          <QuickActions
            onNavigate={handleNavigate}
            onAddStore={handleAddStore}
          />
        </div>
      </div>

      {/* Store Rankings Table */}
      <StoreRankingsTable stores={filteredRankings} />

      {/* Best Performer Badge */}
      {overview?.best_performing_store && (
        <div className="mt-8 p-4 bg-gradient-to-r from-yellow-900/30 to-yellow-800/30 border border-yellow-500/50 rounded-lg">
          <div className="flex items-center gap-3">
            <div className="text-3xl">🏆</div>
            <div>
              <h3 className="text-lg font-bold text-yellow-400">Best Performing Store</h3>
              <p className="text-gray-300">{overview.best_performing_store}</p>
            </div>
          </div>
        </div>
      )}

      {/* Add Store Modal */}
      {showAddStoreModal && (
        <AddStoreModal
          onClose={() => setShowAddStoreModal(false)}
          onSuccess={() => {
            fetchData(); // Refresh portfolio data
          }}
        />
      )}

      {/* AI Chat Assistant - Always available */}
      <AIChat dashboardContext={overview} />
    </div>
  );
};

export default PortfolioDashboard;
