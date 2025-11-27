import { useState } from 'react';
import { Search, Package, ShoppingCart } from 'lucide-react';

// Import existing page components
import { ProductsPage } from './ProductsPage';
import { InventoryPage } from './InventoryPage';
import { OrdersPage } from './OrdersPage';

export const UnifiedProductsPage = () => {
  const [activeTab, setActiveTab] = useState('discovery');

  return (
    <div className="min-h-screen">
      {/* Tabs - No extra padding, let child pages control their layout */}
      <div className="sticky top-0 z-20 bg-gray-950/95 backdrop-blur-sm border-b border-gray-800">
        <div className="px-6 pt-6">
          <div className="flex gap-2">
            <button
              onClick={() => setActiveTab('discovery')}
              className={`flex items-center gap-2 px-6 py-3 font-medium transition-all rounded-t-lg ${
                activeTab === 'discovery'
                  ? 'bg-gray-900/50 text-blue-400 border-b-2 border-blue-400'
                  : 'text-gray-400 hover:text-gray-300 hover:bg-gray-900/30'
              }`}
            >
              <Search className="w-4 h-4" />
              Product Discovery
            </button>
            <button
              onClick={() => setActiveTab('inventory')}
              className={`flex items-center gap-2 px-6 py-3 font-medium transition-all rounded-t-lg ${
                activeTab === 'inventory'
                  ? 'bg-gray-900/50 text-blue-400 border-b-2 border-blue-400'
                  : 'text-gray-400 hover:text-gray-300 hover:bg-gray-900/30'
              }`}
            >
              <Package className="w-4 h-4" />
              Inventory
            </button>
            <button
              onClick={() => setActiveTab('orders')}
              className={`flex items-center gap-2 px-6 py-3 font-medium transition-all rounded-t-lg ${
                activeTab === 'orders'
                  ? 'bg-gray-900/50 text-blue-400 border-b-2 border-blue-400'
                  : 'text-gray-400 hover:text-gray-300 hover:bg-gray-900/30'
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
