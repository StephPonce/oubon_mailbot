import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';

// Types
interface StoreData {
  id: number;
  store_name: string;
  store_url: string;
  platform: string;
  total_revenue: number;
  monthly_revenue: number;
  total_orders: number;
  conversion_rate: number;
  product_count: number;
  is_active: boolean;
  rank_position: number;
  rank_change: number;
  rank_change_label: string;
  last_sync: string | null;
  niche?: string;
  brand_voice?: string;
  notifications_enabled?: boolean;
  auto_deploy_enabled?: boolean;
}

interface StoreContextType {
  // State
  activeStore: StoreData | null;
  stores: StoreData[];
  loading: boolean;

  // Actions
  switchStore: (storeId: number) => Promise<void>;
  refreshStores: () => Promise<void>;
  setActiveStoreById: (storeId: number) => void;
}

// Create context
const StoreContext = createContext<StoreContextType | undefined>(undefined);

// Provider component
export function StoreProvider({ children }: { children: ReactNode }) {
  const [activeStore, setActiveStore] = useState<StoreData | null>(null);
  const [stores, setStores] = useState<StoreData[]>([]);
  const [loading, setLoading] = useState(true);

  // Fetch stores on mount
  useEffect(() => {
    fetchStores();
  }, []);

  // Restore active store from localStorage after stores are fetched
  useEffect(() => {
    if (stores.length > 0 && !activeStore) {
      const savedStoreId = localStorage.getItem('activeStoreId');

      if (savedStoreId) {
        const savedStore = stores.find(s => s.id === parseInt(savedStoreId));
        if (savedStore) {
          setActiveStore(savedStore);
          return;
        }
      }

      // Fallback to first active store (rank 1) or first store
      const primaryStore = stores.find(s => s.is_active) || stores[0];
      if (primaryStore) {
        setActiveStore(primaryStore);
        localStorage.setItem('activeStoreId', primaryStore.id.toString());
      }
    }
  }, [stores, activeStore]);

  const fetchStores = async () => {
    try {
      const response = await fetch('http://localhost:8001/api/portfolio/rankings');
      if (response.ok) {
        const data = await response.json();
        setStores(data);
      }
    } catch (error) {
      console.error('Failed to fetch stores:', error);
    } finally {
      setLoading(false);
    }
  };

  const switchStore = async (storeId: number) => {
    try {
      // Call backend to mark as active/primary
      const response = await fetch(`http://localhost:8001/api/portfolio/stores/${storeId}/switch`, {
        method: 'POST',
      });

      if (response.ok) {
        // Find the store in current list
        const store = stores.find(s => s.id === storeId);
        if (store) {
          setActiveStore(store);
          localStorage.setItem('activeStoreId', storeId.toString());

          // Refresh store list to get updated rankings
          await fetchStores();

          // Notify other parts of the app about the store change
          window.dispatchEvent(new CustomEvent('store-changed', {
            detail: { storeId }
          }));
        }
      } else {
        throw new Error('Failed to switch store');
      }
    } catch (error) {
      console.error('Failed to switch store:', error);
      throw error;
    }
  };

  const refreshStores = async () => {
    await fetchStores();
  };

  const setActiveStoreById = (storeId: number) => {
    const store = stores.find(s => s.id === storeId);
    if (store) {
      setActiveStore(store);
      localStorage.setItem('activeStoreId', storeId.toString());
    }
  };

  const value: StoreContextType = {
    activeStore,
    stores,
    loading,
    switchStore,
    refreshStores,
    setActiveStoreById
  };

  return (
    <StoreContext.Provider value={value}>
      {children}
    </StoreContext.Provider>
  );
}

// Custom hook for using the store context
export function useStore() {
  const context = useContext(StoreContext);
  if (context === undefined) {
    throw new Error('useStore must be used within a StoreProvider');
  }
  return context;
}

// Helper hook for active store ID only (lighter weight)
export function useActiveStoreId(): number | null {
  const { activeStore } = useStore();
  return activeStore?.id || null;
}

// Helper hook to get platform-specific details
export function useStorePlatform(): {
  platform: string | null;
  isShopify: boolean;
  isAmazon: boolean;
  isWooCommerce: boolean;
} {
  const { activeStore } = useStore();
  const platform = activeStore?.platform.toLowerCase() || null;

  return {
    platform,
    isShopify: platform === 'shopify',
    isAmazon: platform === 'amazon',
    isWooCommerce: platform === 'woocommerce'
  };
}
