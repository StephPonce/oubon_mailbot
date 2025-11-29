import { useState } from 'react';
import { Search, Package, ShoppingCart, TrendingUp } from 'lucide-react';

// Import existing page components
import { ProductsPage } from './ProductsPage';
import { InventoryPage } from './InventoryPage';
import { OrdersPage } from './OrdersPage';

export const UnifiedProductsPage = () => {
  const [activeTab, setActiveTab] = useState('discovery');

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Tabs - Glass design with light theme */}
      <div className="sticky top-0 z-20 bg-white/80 backdrop-blur-lg border-b border-gray-200">
        <div className="px-6 pt-6">
          <div className="flex gap-2">
            <button
              onClick={() => setActiveTab('discovery')}
              className={`flex items-center gap-2 px-3 py-2 rounded-lg font-light text-sm transition ${
                activeTab === 'discovery'
                  ? 'bg-gray-900 text-white shadow-lg'
                  : 'text-gray-700 hover:bg-gray-200/50'
              }`}
            >
              <Search className="w-4 h-4" />
              Product Discovery
            </button>
            <button
              onClick={() => setActiveTab('inventory')}
              className={`flex items-center gap-2 px-3 py-2 rounded-lg font-light text-sm transition ${
                activeTab === 'inventory'
                  ? 'bg-gray-900 text-white shadow-lg'
                  : 'text-gray-700 hover:bg-gray-200/50'
              }`}
            >
              <Package className="w-4 h-4" />
              Inventory
            </button>
            <button
              onClick={() => setActiveTab('orders')}
              className={`flex items-center gap-2 px-3 py-2 rounded-lg font-light text-sm transition ${
                activeTab === 'orders'
                  ? 'bg-gray-900 text-white shadow-lg'
                  : 'text-gray-700 hover:bg-gray-200/50'
              }`}
            >
              <ShoppingCart className="w-4 h-4" />
              Orders
            </button>
          </div>
        </div>
      </div>

      {/* Tab Content - Keep all mounted, just hide inactive (persistence) */}
      <div className="relative">
        <div style={{ display: activeTab === 'discovery' ? 'block' : 'none' }}>
          <ProductsPage />
        </div>
        <div style={{ display: activeTab === 'inventory' ? 'block' : 'none' }}>
          <InventoryPage />
        </div>
        <div style={{ display: activeTab === 'orders' ? 'block' : 'none' }}>
          <OrdersPage />
        </div>
      </div>
    </div>
  );
};
