import React, { useState, useEffect, useRef } from 'react';
import { Store, ChevronDown, Check, Plus } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

interface StoreData {
  id: number;
  store_name: string;
  platform: string;
  monthly_revenue: number;
  is_active: boolean;
  product_count: number;
}

interface StoreSwitcherProps {
  onStoreChange?: (storeId: number) => void;
}

export default function StoreSwitcher({ onStoreChange }: StoreSwitcherProps) {
  const [stores, setStores] = useState<StoreData[]>([]);
  const [activeStore, setActiveStore] = useState<StoreData | null>(null);
  const [isOpen, setIsOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();

  useEffect(() => {
    fetchStores();
  }, []);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const fetchStores = async () => {
    try {
      const response = await fetch('http://localhost:8001/api/portfolio/rankings');
      if (response.ok) {
        const data = await response.json();
        setStores(data);

        // Set first store as active (rank 1)
        const primaryStore = data.find((s: StoreData) => s.is_active);
        if (primaryStore) {
          setActiveStore(primaryStore);

          // Store in localStorage
          localStorage.setItem('activeStoreId', primaryStore.id.toString());
        }
      }
    } catch (error) {
      console.error('Failed to fetch stores:', error);
    } finally {
      setLoading(false);
    }
  };

  const switchStore = async (store: StoreData) => {
    try {
      const response = await fetch(`http://localhost:8001/api/portfolio/stores/${store.id}/switch`, {
        method: 'POST',
      });

      if (response.ok) {
        setActiveStore(store);
        setIsOpen(false);

        // Store in localStorage
        localStorage.setItem('activeStoreId', store.id.toString());

        // Notify parent
        if (onStoreChange) {
          onStoreChange(store.id);
        }

        // Refresh page to update all data
        window.location.reload();
      }
    } catch (error) {
      console.error('Failed to switch store:', error);
    }
  };

  const getPlatformIcon = (platform: string) => {
    const platformLower = platform.toLowerCase();

    if (platformLower === 'shopify') {
      return (
        <div className="w-5 h-5 rounded bg-green-500/10 flex items-center justify-center">
          <span className="text-green-600 text-xs font-bold">S</span>
        </div>
      );
    } else if (platformLower === 'amazon') {
      return (
        <div className="w-5 h-5 rounded bg-orange-500/10 flex items-center justify-center">
          <span className="text-orange-600 text-xs font-bold">A</span>
        </div>
      );
    } else if (platformLower === 'woocommerce') {
      return (
        <div className="w-5 h-5 rounded bg-purple-500/10 flex items-center justify-center">
          <span className="text-purple-600 text-xs font-bold">W</span>
        </div>
      );
    }

    return (
      <div className="w-5 h-5 rounded bg-blue-500/10 flex items-center justify-center">
        <Store className="w-3 h-3 text-blue-600" />
      </div>
    );
  };

  if (loading) {
    return (
      <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-black/5">
        <div className="w-5 h-5 rounded bg-gray-300 animate-pulse" />
        <div className="w-24 h-4 bg-gray-300 rounded animate-pulse" />
      </div>
    );
  }

  if (!activeStore) {
    return (
      <button
        onClick={() => navigate('/stores')}
        className="flex items-center gap-2 px-3 py-2 rounded-lg bg-blue-500/10 text-blue-600 hover:bg-blue-500/20 transition-colors"
      >
        <Plus className="w-4 h-4" />
        <span className="text-sm font-medium">Add Store</span>
      </button>
    );
  }

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 px-3 py-2 rounded-lg bg-black/5 hover:bg-black/10 transition-colors min-w-[180px]"
      >
        {getPlatformIcon(activeStore.platform)}

        <div className="flex-1 text-left">
          <div className="text-sm font-medium text-primary">{activeStore.store_name}</div>
          <div className="text-xs text-tertiary capitalize">{activeStore.platform}</div>
        </div>

        <ChevronDown className={`w-4 h-4 text-secondary transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      {isOpen && (
        <div className="absolute top-full left-0 mt-2 w-80 bg-white rounded-xl shadow-2xl border border-black/10 py-2 z-50">
          <div className="px-3 py-2 border-b border-black/10">
            <div className="text-xs font-medium text-tertiary uppercase tracking-wide">Your Stores</div>
          </div>

          <div className="max-h-96 overflow-y-auto">
            {stores.map((store) => (
              <button
                key={store.id}
                onClick={() => switchStore(store)}
                className="w-full px-3 py-3 flex items-center gap-3 hover:bg-black/5 transition-colors"
              >
                {getPlatformIcon(store.platform)}

                <div className="flex-1 text-left">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-primary">{store.store_name}</span>
                    {activeStore.id === store.id && (
                      <div className="w-1.5 h-1.5 rounded-full bg-green-500" />
                    )}
                  </div>
                  <div className="text-xs text-tertiary capitalize">
                    {store.platform} • {store.product_count} products • ${store.monthly_revenue.toLocaleString()}/mo
                  </div>
                </div>

                {activeStore.id === store.id && (
                  <Check className="w-4 h-4 text-green-600 flex-shrink-0" />
                )}
              </button>
            ))}
          </div>

          <div className="px-3 py-2 border-t border-black/10">
            <button
              onClick={() => {
                setIsOpen(false);
                navigate('/stores');
              }}
              className="w-full flex items-center gap-2 px-3 py-2 rounded-lg bg-blue-500/10 text-blue-600 hover:bg-blue-500/20 transition-colors"
            >
              <Plus className="w-4 h-4" />
              <span className="text-sm font-medium">Add New Store</span>
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
