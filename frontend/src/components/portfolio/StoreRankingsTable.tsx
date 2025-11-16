import React from 'react';
import { ArrowUp, ArrowDown, Minus, Store as StoreIcon } from 'lucide-react';

interface Store {
  id: number;
  store_name: string;
  platform: string;
  niche?: string;
  monthly_revenue: number;
  total_revenue: number;
  conversion_rate: number;
  product_count: number;
  active_products: number;
  rank_position: number;
  rank_change: number;
  rank_change_label: string;
  isActive?: boolean;
  url?: string;
}

interface StoreRankingsTableProps {
  stores?: Store[];
  onStoreClick?: (storeId: number) => void;
}

export default function StoreRankingsTable({ stores, onStoreClick }: StoreRankingsTableProps) {
  // Safety check - handle undefined or null stores
  const safeStores = stores || [];

  const getPlatformColor = (platform: string) => {
    switch (platform.toLowerCase()) {
      case 'shopify': return 'bg-purple-500/20 text-purple-400 border-purple-500/30';
      case 'amazon': return 'bg-orange-500/20 text-orange-400 border-orange-500/30';
      case 'woocommerce': return 'bg-blue-500/20 text-blue-400 border-blue-500/30';
      default: return 'bg-gray-500/20 text-gray-400 border-gray-500/30';
    }
  };

  const getRankChangeIcon = (change: number) => {
    if (change > 0) return <ArrowUp className="w-4 h-4 text-green-500" />;
    if (change < 0) return <ArrowDown className="w-4 h-4 text-red-500" />;
    return <Minus className="w-4 h-4 text-gray-500" />;
  };

  return (
    <div className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead className="bg-gray-900/50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                Rank
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                Store
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                Platform
              </th>
              <th className="px-6 py-3 text-right text-xs font-medium text-gray-400 uppercase tracking-wider">
                Revenue (30d)
              </th>
              <th className="px-6 py-3 text-right text-xs font-medium text-gray-400 uppercase tracking-wider">
                Conversion
              </th>
              <th className="px-6 py-3 text-right text-xs font-medium text-gray-400 uppercase tracking-wider">
                Products
              </th>
              <th className="px-6 py-3 text-center text-xs font-medium text-gray-400 uppercase tracking-wider">
                Status
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-700">
            {safeStores.map((store) => (
              <tr
                key={store.id}
                onClick={() => onStoreClick?.(store.id)}
                className="hover:bg-gray-700/50 cursor-pointer transition-colors"
              >
                <td className="px-6 py-4 whitespace-nowrap">
                  <div className="flex items-center gap-2">
                    <span className="text-2xl font-bold text-white">#{store.rank_position}</span>
                    {getRankChangeIcon(store.rank_change)}
                  </div>
                </td>

                <td className="px-6 py-4">
                  <div>
                    <p className="text-sm font-medium text-white">{store.store_name}</p>
                    {store.niche && (
                      <p className="text-xs text-gray-400 mt-1">{store.niche}</p>
                    )}
                  </div>
                </td>

                <td className="px-6 py-4">
                  <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${getPlatformColor(store.platform)}`}>
                    {store.platform}
                  </span>
                </td>

                <td className="px-6 py-4 text-right">
                  <p className="text-sm font-semibold text-white">
                    ${store.monthly_revenue.toLocaleString()}
                  </p>
                </td>

                <td className="px-6 py-4 text-right">
                  <p className="text-sm text-gray-300">
                    {store.conversion_rate.toFixed(2)}%
                  </p>
                </td>

                <td className="px-6 py-4 text-right">
                  <p className="text-sm text-gray-300">
                    {store.product_count}
                  </p>
                </td>

                <td className="px-6 py-4 text-center">
                  <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                    store.isActive
                      ? 'bg-green-500/20 text-green-400 border border-green-500/30'
                      : 'bg-gray-500/20 text-gray-400 border border-gray-500/30'
                  }`}>
                    {store.isActive ? 'Active' : 'Inactive'}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {safeStores.length === 0 && (
        <div className="text-center py-12">
          <StoreIcon className="w-12 h-12 text-gray-600 mx-auto mb-4" />
          <p className="text-gray-400 text-lg mb-2">No stores yet</p>
          <p className="text-gray-500 text-sm">Add your first store to get started!</p>
        </div>
      )}
    </div>
  );
}
