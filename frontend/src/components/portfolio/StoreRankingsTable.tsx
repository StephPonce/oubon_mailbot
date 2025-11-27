import { ArrowUp, ArrowDown, Minus, Store as StoreIcon } from 'lucide-react';

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

interface StoreRankingsTableProps {
  stores: StoreRanking[];
  onStoreClick?: (storeId: number) => void;
}

export default function StoreRankingsTable({ stores, onStoreClick }: StoreRankingsTableProps) {
  const safeStores = stores || [];

  const getPlatformTag = (platform: string) => {
    const baseClasses = 'inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold';
    switch (platform.toLowerCase()) {
      case 'shopify': return `${baseClasses} bg-purple-500/10 text-purple-400`;
      case 'amazon': return `${baseClasses} bg-orange-500/10 text-orange-400`;
      case 'woocommerce': return `${baseClasses} bg-blue-500/10 text-blue-400`;
      default: return `${baseClasses} bg-gray-500/10 text-gray-300`;
    }
  };

  const getRankChangeIcon = (change: number) => {
    if (change > 0) return <ArrowUp className="w-4 h-4 text-success-green" />;
    if (change < 0) return <ArrowDown className="w-4 h-4 text-red-500" />;
    return <Minus className="w-4 h-4 text-gray-500" />;
  };

  return (
    <div>
      {/* Table Header */}
      <div className="grid grid-cols-12 gap-4 px-4 py-2 text-xs font-medium text-gray-400 uppercase">
        <div className="col-span-1">Rank</div>
        <div className="col-span-4">Store</div>
        <div className="col-span-2">Platform</div>
        <div className="col-span-2 text-right">Revenue (30d)</div>
        <div className="col-span-1 text-right">Conv.</div>
        <div className="col-span-1 text-right">Products</div>
        <div className="col-span-1 text-center">Status</div>
      </div>

      {/* Table Body */}
      <div className="space-y-3">
        {safeStores.map((store) => (
          <div
            key={store.id}
            onClick={() => onStoreClick?.(store.id)}
            className="grid grid-cols-12 gap-4 items-center p-4 rounded-lg bg-gray-900/50 backdrop-blur-md border border-gray-800 hover:bg-gray-800/60 hover:border-gray-700 cursor-pointer transition-all"
          >
            <div className="col-span-1 flex items-center gap-2">
              <span className="text-xl font-bold text-gray-200">#{store.rank_position}</span>
              {getRankChangeIcon(store.rank_change)}
            </div>

            <div className="col-span-4">
              <p className="font-semibold text-gray-200">{store.store_name}</p>
              {store.url && <a href={store.url} target="_blank" rel="noopener noreferrer" className="text-xs text-gray-500 hover:text-brand-blue">{store.url}</a>}
            </div>

            <div className="col-span-2">
              <span className={getPlatformTag(store.platform)}>
                {store.platform}
              </span>
            </div>

            <div className="col-span-2 text-right font-semibold text-gray-200">
              ${store.monthly_revenue.toLocaleString()}
            </div>

            <div className="col-span-1 text-right text-gray-300">
              {store.conversion_rate.toFixed(2)}%
            </div>

            <div className="col-span-1 text-right text-gray-300">
              {store.active_products} / {store.product_count}
            </div>

            <div className="col-span-1 text-center">
              <div className={`w-3 h-3 rounded-full mx-auto ${store.isActive ? 'bg-success-green' : 'bg-gray-600'}`} title={store.isActive ? 'Active' : 'Inactive'}></div>
            </div>
          </div>
        ))}
      </div>

      {safeStores.length === 0 && (
        <div className="text-center py-20 bg-gray-900/50 border border-gray-800 rounded-lg">
          <StoreIcon className="w-12 h-12 text-gray-600 mx-auto mb-4" />
          <h3 className="text-lg font-semibold text-gray-400">No stores found</h3>
          <p className="text-sm text-gray-500 mt-1">Add your first store to see its ranking here.</p>
        </div>
      )}
    </div>
  );
}
