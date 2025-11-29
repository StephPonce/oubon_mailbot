import React, { useState, useMemo } from 'react';
import {
  Store as StoreIcon,
  ChevronDown,
  Plus,
  Search,
  TrendingUp,
  Package,
  DollarSign,
  Filter,
  X
} from 'lucide-react';

// Types
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

interface StoreSelectorProps {
  stores: Store[];
  activeStore: Store | null;
  onSwitch: (store: Store | null) => void;
  onAddStore: () => void;
}

// Platform configuration
const PLATFORMS = [
  { id: 'all', name: 'All Platforms', color: 'blue' },
  { id: 'shopify', name: 'Shopify Only', color: 'purple' },
  { id: 'amazon', name: 'Amazon Only', color: 'orange' },
  { id: 'woocommerce', name: 'WooCommerce Only', color: 'blue' }
] as const;

const PLATFORM_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  shopify: {
    bg: 'bg-purple-500/20',
    text: 'text-purple-400',
    border: 'border-purple-500/50'
  },
  amazon: {
    bg: 'bg-orange-500/20',
    text: 'text-orange-400',
    border: 'border-orange-500/50'
  },
  woocommerce: {
    bg: 'bg-blue-500/20',
    text: 'text-blue-400',
    border: 'border-blue-500/50'
  },
  etsy: {
    bg: 'bg-pink-500/20',
    text: 'text-pink-400',
    border: 'border-pink-500/50'
  },
  ebay: {
    bg: 'bg-yellow-500/20',
    text: 'text-yellow-400',
    border: 'border-yellow-500/50'
  }
};

const StoreSelector: React.FC<StoreSelectorProps> = ({
  stores,
  activeStore,
  onSwitch,
  onAddStore
}) => {
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const [selectedPlatform, setSelectedPlatform] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');

  // Filter stores by platform and search query
  const filteredStores = useMemo(() => {
    let filtered = stores;

    // Filter by platform
    if (selectedPlatform !== 'all') {
      filtered = filtered.filter(
        store => store.platform.toLowerCase() === selectedPlatform
      );
    }

    // Filter by search query
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter(store =>
        store.store_name.toLowerCase().includes(query)
      );
    }

    return filtered;
  }, [stores, selectedPlatform, searchQuery]);

  // Count stores per platform
  const platformCounts = useMemo(() => {
    const counts: Record<string, number> = { all: stores.length };
    stores.forEach(store => {
      const platform = store.platform.toLowerCase();
      counts[platform] = (counts[platform] || 0) + 1;
    });
    return counts;
  }, [stores]);

  // Get platform badge styling
  const getPlatformBadge = (platform: string) => {
    const platformKey = platform.toLowerCase();
    const colors = PLATFORM_COLORS[platformKey] || {
      bg: 'bg-gray-500/20',
      text: 'text-gray-400',
      border: 'border-gray-500/50'
    };

    return (
      <span
        className={`px-2 py-0.5 rounded-full text-xs font-medium border ${colors.bg} ${colors.text} ${colors.border}`}
      >
        {platform.toUpperCase()}
      </span>
    );
  };

  // Handle store selection
  const handleSelectStore = (store: Store | null) => {
    onSwitch(store);
    setIsDropdownOpen(false);
    setSearchQuery('');
  };

  // Handle platform filter
  const handlePlatformFilter = (platformId: string) => {
    setSelectedPlatform(platformId);
  };

  return (
    <div className="sticky top-0 z-40 bg-gray-900/95 backdrop-blur-sm border-b border-gray-800 shadow-lg">
      <div className="px-6 py-4">
        {/* Top Row: Store Selector & Add Button */}
        <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4 mb-4">
          {/* Store Dropdown */}
          <div className="flex-1 max-w-md">
            <label className="block text-xs font-medium text-gray-400 mb-2 uppercase tracking-wider">
              Active Store
            </label>
            <div className="relative">
              <button
                onClick={() => setIsDropdownOpen(!isDropdownOpen)}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-left text-white hover:border-blue-500 transition-all duration-200 flex items-center justify-between group"
              >
                <div className="flex items-center gap-3">
                  <StoreIcon className="w-5 h-5 text-blue-400" />
                  <div>
                    <div className="font-medium">
                      {activeStore ? activeStore.store_name : 'All Stores (Portfolio View)'}
                    </div>
                    {activeStore && (
                      <div className="text-xs text-gray-500 mt-0.5">
                        ID: {activeStore.id}
                      </div>
                    )}
                  </div>
                  {activeStore && (
                    <div className="ml-2">
                      {getPlatformBadge(activeStore.platform)}
                    </div>
                  )}
                </div>
                <ChevronDown
                  className={`w-5 h-5 text-gray-400 transition-transform duration-200 ${
                    isDropdownOpen ? 'rotate-180' : ''
                  }`}
                />
              </button>

              {/* Dropdown Menu */}
              {isDropdownOpen && (
                <div className="absolute top-full mt-2 w-full bg-gray-800 border border-gray-700 rounded-lg shadow-2xl overflow-hidden z-50">
                  {/* Search */}
                  <div className="p-3 border-b border-gray-700">
                    <div className="relative">
                      <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
                      <input
                        type="text"
                        placeholder="Search stores..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        className="w-full bg-gray-900 border border-gray-700 rounded-lg pl-10 pr-8 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-blue-500 transition"
                        autoFocus
                      />
                      {searchQuery && (
                        <button
                          onClick={() => setSearchQuery('')}
                          className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300"
                        >
                          <X className="w-4 h-4" />
                        </button>
                      )}
                    </div>
                  </div>

                  {/* Store List */}
                  <div className="max-h-80 overflow-y-auto">
                    {/* All Stores Option */}
                    <button
                      onClick={() => handleSelectStore(null)}
                      className={`w-full px-4 py-3 text-left hover:bg-gray-700/50 transition-colors border-b border-gray-700/50 ${
                        !activeStore ? 'bg-blue-500/10' : ''
                      }`}
                    >
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
                          <StoreIcon className="w-5 h-5 text-white" />
                        </div>
                        <div className="flex-1">
                          <div className="font-medium text-white">All Stores</div>
                          <div className="text-xs text-gray-400">Portfolio View</div>
                        </div>
                        <div className="text-xs text-gray-500">
                          {stores.length} {stores.length === 1 ? 'store' : 'stores'}
                        </div>
                      </div>
                    </button>

                    {/* Individual Stores */}
                    {filteredStores.length > 0 ? (
                      filteredStores.map((store) => (
                        <button
                          key={store.id}
                          onClick={() => handleSelectStore(store)}
                          className={`w-full px-4 py-3 text-left hover:bg-gray-700/50 transition-colors border-b border-gray-700/50 last:border-b-0 ${
                            activeStore?.id === store.id ? 'bg-blue-500/10' : ''
                          }`}
                        >
                          <div className="flex items-center gap-3">
                            <div className="w-10 h-10 rounded-lg bg-gray-700 flex items-center justify-center">
                              <StoreIcon className="w-5 h-5 text-gray-400" />
                            </div>
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2">
                                <span className="font-medium text-white truncate">
                                  {store.store_name}
                                </span>
                                {getPlatformBadge(store.platform)}
                              </div>
                              <div className="flex items-center gap-3 mt-1 text-xs text-gray-400">
                                <span>${store.monthly_revenue.toLocaleString()}/mo</span>
                                <span>•</span>
                                <span>{store.active_products} products</span>
                              </div>
                            </div>
                            {store.status === 'active' && (
                              <div className="w-2 h-2 rounded-full bg-green-400"></div>
                            )}
                          </div>
                        </button>
                      ))
                    ) : (
                      <div className="px-4 py-8 text-center text-gray-500">
                        <StoreIcon className="w-12 h-12 mx-auto mb-2 opacity-50" />
                        <p className="text-sm">No stores found</p>
                        {searchQuery && (
                          <p className="text-xs mt-1">Try a different search term</p>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Add Store Button */}
          <div className="lg:self-end">
            <button
              onClick={onAddStore}
              className="w-full lg:w-auto px-6 py-3 bg-gradient-to-r from-blue-500 to-purple-600 text-white rounded-lg font-medium hover:from-blue-600 hover:to-purple-700 transition-all duration-200 flex items-center justify-center gap-2 shadow-lg hover:shadow-blue-500/50 hover:scale-105"
            >
              <Plus className="w-5 h-5" />
              <span>Add Store</span>
            </button>
          </div>
        </div>

        {/* Platform Filter Buttons */}
        <div className="flex flex-wrap gap-2">
          {PLATFORMS.map((platform) => (
            <button
              key={platform.id}
              onClick={() => handlePlatformFilter(platform.id)}
              className={`w-full flex justify-between items-center px-3 py-2 rounded-lg font-light text-sm transition ${
                selectedPlatform === platform.id
                  ? 'bg-gray-900 text-white shadow-lg'
                  : 'text-gray-700 hover:bg-gray-200/50'
              }`}
            >
              <Filter className="w-4 h-4" />
              <span>{platform.name}</span>
              <span
                className={`px-2 py-0.5 rounded-full text-xs font-bold ${
                  selectedPlatform === platform.id
                    ? 'bg-white/20'
                    : 'bg-gray-700'
                }`}
              >
                {platformCounts[platform.id] || 0}
              </span>
            </button>
          ))}
        </div>

        {/* Current Store Stats (when a store is selected) */}
        {activeStore && (
          <div className="mt-4 p-4 bg-gray-800/50 border border-gray-700 rounded-lg">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-medium text-gray-400 uppercase tracking-wider">
                Current Store Stats
              </h3>
              {getPlatformBadge(activeStore.platform)}
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="flex items-center gap-2">
                <div className="p-2 bg-green-500/10 rounded-lg">
                  <DollarSign className="w-4 h-4 text-green-400" />
                </div>
                <div>
                  <p className="text-xs text-gray-500">Monthly Revenue</p>
                  <p className="text-sm font-bold text-white">
                    ${activeStore.monthly_revenue.toLocaleString()}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <div className="p-2 bg-blue-500/10 rounded-lg">
                  <Package className="w-4 h-4 text-blue-400" />
                </div>
                <div>
                  <p className="text-xs text-gray-500">Active Products</p>
                  <p className="text-sm font-bold text-white">
                    {activeStore.active_products}/{activeStore.product_count}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <div className="p-2 bg-purple-500/10 rounded-lg">
                  <TrendingUp className="w-4 h-4 text-purple-400" />
                </div>
                <div>
                  <p className="text-xs text-gray-500">Conversion Rate</p>
                  <p className="text-sm font-bold text-white">
                    {activeStore.conversion_rate.toFixed(2)}%
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <div className="p-2 bg-yellow-500/10 rounded-lg">
                  <DollarSign className="w-4 h-4 text-yellow-400" />
                </div>
                <div>
                  <p className="text-xs text-gray-500">Total Revenue</p>
                  <p className="text-sm font-bold text-white">
                    ${activeStore.total_revenue.toLocaleString()}
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Close dropdown when clicking outside */}
      {isDropdownOpen && (
        <div
          className="fixed inset-0 z-30"
          onClick={() => setIsDropdownOpen(false)}
        />
      )}
    </div>
  );
};

export default StoreSelector;
