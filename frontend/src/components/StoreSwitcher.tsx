import React, { useState, useEffect, useRef } from 'react';
import { Store, ChevronDown, Check, Plus, AlertCircle } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import api from '@/lib/api';

interface StoreData {
  id: number;
  store_name: string;
  store_url: string;
  platform: string;
  status: 'setup' | 'active' | 'paused' | 'disconnected' | 'error';
  niche: string | null;
  pending_actions_count: number;
  total_revenue: number;
  monthly_revenue: number;
  total_orders: number;
  conversion_rate: number;
  total_products: number;
  last_sync: string | null;
  sync_error: string | null;
  created_at: string;
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
      const response = await api.get<{ stores: StoreData[] }>('/api/stores');
      const data = response.data.stores || response.data || [];
      setStores(data);

      // Get active store from localStorage, or use first active store
      const savedStoreId = localStorage.getItem('activeStoreId');
      let primaryStore: StoreData | undefined;

      if (savedStoreId) {
        primaryStore = data.find((s: StoreData) => s.id.toString() === savedStoreId);
      }

      // Fallback to first active store
      if (!primaryStore) {
        primaryStore = data.find((s: StoreData) => s.status === 'active');
      }

      if (primaryStore) {
        setActiveStore(primaryStore);
        localStorage.setItem('activeStoreId', primaryStore.id.toString());
      }
    } catch (error) {
      console.error('Failed to fetch stores:', error);
    } finally {
      setLoading(false);
    }
  };

  const switchStore = (store: StoreData) => {
    setActiveStore(store);
    setIsOpen(false);

    // Store in localStorage
    localStorage.setItem('activeStoreId', store.id.toString());

    // Notify parent
    if (onStoreChange) {
      onStoreChange(store.id);
    }

    // Refresh page to update all data with new store context
    window.location.reload();
  };

  const getPlatformIcon = (platform: string) => {
    const platformLower = platform.toLowerCase();

    if (platformLower === 'shopify') {
      return (
        <div className="w-5 h-5 rounded bg-green-500/100/10 flex items-center justify-center">
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
      <div className="w-5 h-5 rounded bg-cyan-500/100/10 flex items-center justify-center">
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
        className="flex items-center gap-2 px-3 py-2 rounded-lg bg-cyan-500/100/10 text-blue-600 hover:bg-cyan-500/100/20 transition-colors"
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
        className="flex items-center gap-2 px-3 py-2 rounded-lg bg-black/5 hover:bg-black/10 transition-colors min-w-[200px]"
      >
        {getPlatformIcon(activeStore.platform)}

        <div className="flex-1 text-left">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-primary">{activeStore.store_name}</span>
            {activeStore.status === 'error' && (
              <AlertCircle className="w-3 h-3 text-red-500" />
            )}
            {activeStore.pending_actions_count > 0 && (
              <span className="px-1.5 py-0.5 rounded-full bg-orange-500/20 text-orange-600 text-[10px] font-medium">
                {activeStore.pending_actions_count}
              </span>
            )}
          </div>
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
                      <div className="w-1.5 h-1.5 rounded-full bg-green-500/100" />
                    )}
                    {store.status === 'error' && (
                      <AlertCircle className="w-3 h-3 text-red-500" />
                    )}
                    {store.pending_actions_count > 0 && (
                      <span className="px-1.5 py-0.5 rounded-full bg-orange-500/20 text-orange-600 text-[10px] font-medium">
                        {store.pending_actions_count}
                      </span>
                    )}
                  </div>
                  <div className="text-xs text-tertiary capitalize flex items-center gap-1">
                    <span>{store.platform}</span>
                    <span>•</span>
                    <span className={`
                      ${store.status === 'active' ? 'text-green-600' : ''}
                      ${store.status === 'paused' ? 'text-yellow-600' : ''}
                      ${store.status === 'error' ? 'text-red-600' : ''}
                      ${store.status === 'setup' ? 'text-blue-600' : ''}
                      ${store.status === 'disconnected' ? 'text-secondary' : ''}
                    `}>
                      {store.status}
                    </span>
                    <span>•</span>
                    <span>{store.total_products} products</span>
                    <span>•</span>
                    <span>${store.monthly_revenue.toLocaleString()}/mo</span>
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
              className="w-full flex items-center gap-2 px-3 py-2 rounded-lg bg-cyan-500/100/10 text-blue-600 hover:bg-cyan-500/100/20 transition-colors"
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
