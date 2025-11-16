/**
 * EXAMPLE: Integrating StoreSelector into Portfolio Dashboard
 *
 * This file shows how to integrate the StoreSelector component
 * into your existing Portfolio Dashboard.
 *
 * Location: This is just an example file for reference
 */

import React, { useState, useEffect } from 'react';
import StoreSelector from './components/StoreSelector';
import MetricCard from './components/portfolio/MetricCard';
import StoreRankingsTable from './components/portfolio/StoreRankingsTable';
import RevenueChart from './components/portfolio/RevenueChart';
import QuickActions from './components/portfolio/QuickActions';

interface Store {
  id: number;
  store_name: string;
  platform: string;
  monthly_revenue: number;
  total_revenue: number;
  product_count: number;
  active_products: number;
  conversion_rate: number;
  status: 'active' | 'inactive';
}

interface PortfolioOverview {
  total_revenue: number;
  monthly_revenue: number;
  active_stores: number;
  total_stores: number;
  total_products: number;
  active_products: number;
  avg_conversion_rate: number;
  best_performing_store: string | null;
}

export default function PortfolioDashboardWithSelector() {
  // State
  const [stores, setStores] = useState<Store[]>([]);
  const [activeStore, setActiveStore] = useState<Store | null>(null);
  const [overview, setOverview] = useState<PortfolioOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Fetch data on mount
  useEffect(() => {
    fetchData();
  }, []);

  // Fetch portfolio data
  const fetchData = async () => {
    try {
      setLoading(true);
      setError(null);

      // Fetch overview
      const overviewRes = await fetch('http://localhost:8001/api/portfolio/overview');
      if (!overviewRes.ok) throw new Error('Failed to fetch overview');
      const overviewData = await overviewRes.json();
      setOverview(overviewData);

      // Fetch stores (rankings)
      const storesRes = await fetch('http://localhost:8001/api/portfolio/rankings');
      if (!storesRes.ok) throw new Error('Failed to fetch stores');
      const storesData = await storesRes.json();

      // Transform to Store interface with status
      const transformedStores: Store[] = storesData.map((store: any) => ({
        ...store,
        status: 'active' as const // You can add logic to determine status
      }));

      setStores(transformedStores);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  // Handle store switch
  const handleStoreSwitch = (store: Store | null) => {
    setActiveStore(store);
    console.log('Switched to:', store ? store.store_name : 'All Stores');

    // Optional: Fetch store-specific data here
    if (store) {
      fetchStoreData(store.id);
    }
  };

  // Fetch individual store data (optional)
  const fetchStoreData = async (storeId: number) => {
    try {
      // Example: Fetch store-specific analytics
      const response = await fetch(`http://localhost:8001/api/store/${storeId}/analytics`);
      const data = await response.json();
      console.log('Store analytics:', data);
    } catch (err) {
      console.error('Failed to fetch store data:', err);
    }
  };

  // Handle add store
  const handleAddStore = () => {
    console.log('Opening add store modal...');
    // TODO: Open add store modal
    // setShowAddStoreModal(true);
  };

  // Filter data based on active store
  const getFilteredData = () => {
    if (!activeStore) {
      // Show all stores (portfolio view)
      return {
        stores,
        metrics: overview ? {
          revenue: overview.monthly_revenue,
          products: overview.total_products,
          conversion: overview.avg_conversion_rate
        } : null
      };
    } else {
      // Show single store data
      return {
        stores: [activeStore],
        metrics: {
          revenue: activeStore.monthly_revenue,
          products: activeStore.product_count,
          conversion: activeStore.conversion_rate
        }
      };
    }
  };

  const filteredData = getFilteredData();

  // Loading state
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

  // Error state
  if (error) {
    return (
      <div className="min-h-screen bg-gray-900 flex items-center justify-center">
        <div className="bg-red-900/20 border border-red-500 rounded-lg p-6 max-w-md">
          <h2 className="text-red-500 text-xl font-bold mb-2">Error</h2>
          <p className="text-gray-300">{error}</p>
          <button
            onClick={fetchData}
            className="mt-4 px-4 py-2 bg-red-500 text-white rounded hover:bg-red-600"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-900 text-white">
      {/* Store Selector - Sticky Header */}
      <StoreSelector
        stores={stores}
        activeStore={activeStore}
        onSwitch={handleStoreSwitch}
        onAddStore={handleAddStore}
      />

      {/* Dashboard Content */}
      <div className="p-6">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold mb-2 bg-gradient-to-r from-blue-400 to-purple-500 bg-clip-text text-transparent">
            {activeStore ? `${activeStore.store_name} Dashboard` : 'Portfolio Dashboard'}
          </h1>
          <p className="text-gray-400">
            {activeStore
              ? `Viewing individual store on ${activeStore.platform}`
              : `Managing ${stores.length} store${stores.length !== 1 ? 's' : ''}`
            }
          </p>
        </div>

        {/* Metrics - Adjusted based on view */}
        {filteredData.metrics && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
            <MetricCard
              title="Revenue"
              value={`$${filteredData.metrics.revenue.toLocaleString()}`}
              change={12.5}
              trend="up"
              icon={() => <span>💰</span>}
              subtitle="This month"
            />
            <MetricCard
              title="Products"
              value={filteredData.metrics.products.toString()}
              change={23}
              trend="up"
              icon={() => <span>📦</span>}
              subtitle="Active products"
            />
            <MetricCard
              title="Conversion"
              value={`${filteredData.metrics.conversion.toFixed(2)}%`}
              change={0.8}
              trend="up"
              icon={() => <span>🎯</span>}
              subtitle="Average rate"
            />
          </div>
        )}

        {/* Charts & Actions */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
          <div className="lg:col-span-2">
            <RevenueChart rankings={filteredData.stores} />
          </div>
          <div>
            <QuickActions />
          </div>
        </div>

        {/* Store Rankings Table */}
        {!activeStore && (
          <div className="mb-8">
            <h2 className="text-xl font-bold mb-4 text-white">All Stores</h2>
            <StoreRankingsTable rankings={filteredData.stores} />
          </div>
        )}

        {/* Single Store View */}
        {activeStore && (
          <div className="space-y-6">
            {/* Store Details */}
            <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
              <h2 className="text-xl font-bold mb-4 text-white">Store Details</h2>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div>
                  <p className="text-xs text-gray-500 uppercase">Store ID</p>
                  <p className="text-lg font-bold text-white">{activeStore.id}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-500 uppercase">Platform</p>
                  <p className="text-lg font-bold text-white capitalize">{activeStore.platform}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-500 uppercase">Total Revenue</p>
                  <p className="text-lg font-bold text-white">
                    ${activeStore.total_revenue.toLocaleString()}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-gray-500 uppercase">Status</p>
                  <p className="text-lg font-bold text-green-400 capitalize">
                    {activeStore.status}
                  </p>
                </div>
              </div>
            </div>

            {/* Store-specific content */}
            <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
              <h3 className="text-lg font-bold mb-4 text-white">Recent Activity</h3>
              <p className="text-gray-400">Store-specific data would go here...</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * INTEGRATION NOTES:
 *
 * 1. Import StoreSelector at the top of your PortfolioDashboard
 * 2. Add state for activeStore: useState<Store | null>(null)
 * 3. Add StoreSelector before your main content
 * 4. Filter data based on activeStore value
 * 5. Handle onSwitch and onAddStore callbacks
 *
 * BENEFITS:
 * - Sticky header that stays visible when scrolling
 * - Quick store switching without navigation
 * - Platform filtering for easier management
 * - Store stats always visible
 * - Search functionality for many stores
 *
 * CUSTOMIZATION:
 * - Adjust styling to match your theme
 * - Add more metrics to stats panel
 * - Customize platform colors
 * - Add keyboard shortcuts
 * - Integrate with routing if needed
 */
