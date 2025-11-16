/**
 * EXAMPLE: Integrating AddStoreModal with StoreSelector
 *
 * This file demonstrates how to integrate the AddStoreModal component
 * with the StoreSelector to create a complete store management experience.
 */

import React, { useState, useEffect } from 'react';
import StoreSelector from './components/StoreSelector';
import AddStoreModal from './components/AddStoreModal';

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

export default function PortfolioWithAddStore() {
  const [stores, setStores] = useState<Store[]>([]);
  const [activeStore, setActiveStore] = useState<Store | null>(null);
  const [showAddModal, setShowAddModal] = useState(false);
  const [loading, setLoading] = useState(false);

  // Fetch stores on mount
  useEffect(() => {
    fetchStores();
  }, []);

  // Fetch stores from API
  const fetchStores = async () => {
    try {
      setLoading(true);
      const response = await fetch('http://localhost:8001/api/portfolio/rankings');
      const data = await response.json();

      // Transform to Store interface with status
      const transformedStores: Store[] = data.map((store: any) => ({
        ...store,
        status: 'active' as const
      }));

      setStores(transformedStores);
    } catch (error) {
      console.error('Failed to fetch stores:', error);
    } finally {
      setLoading(false);
    }
  };

  // Handle store switch
  const handleStoreSwitch = (store: Store | null) => {
    setActiveStore(store);
    console.log('Switched to:', store ? store.store_name : 'All Stores');
  };

  // Handle add store button click
  const handleAddStoreClick = () => {
    console.log('Opening add store modal...');
    setShowAddModal(true);
  };

  // Handle store successfully added
  const handleStoreAdded = async (newStore: any) => {
    console.log('New store added:', newStore);

    // Option 1: Add to existing array (optimistic update)
    setStores((prevStores) => [
      ...prevStores,
      {
        ...newStore,
        status: 'active' as const
      }
    ]);

    // Option 2: Refetch all stores (more reliable)
    // await fetchStores();

    // Close modal
    setShowAddModal(false);

    // Optionally switch to the new store
    setActiveStore({
      ...newStore,
      status: 'active' as const
    });

    // Show success notification (if using a toast library)
    // toast.success(`${newStore.store_name} added successfully!`);
  };

  // Handle modal close
  const handleModalClose = () => {
    console.log('Modal closed');
    setShowAddModal(false);
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-900 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto"></div>
          <p className="mt-4 text-gray-400">Loading stores...</p>
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
        onAddStore={handleAddStoreClick}
      />

      {/* Dashboard Content */}
      <div className="p-6">
        <h1 className="text-3xl font-bold mb-4">
          {activeStore ? activeStore.store_name : 'Portfolio Dashboard'}
        </h1>

        <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
          <h2 className="text-xl font-bold mb-4">Store Information</h2>
          {activeStore ? (
            <div className="space-y-2 text-gray-300">
              <p>Store: {activeStore.store_name}</p>
              <p>Platform: {activeStore.platform}</p>
              <p>Monthly Revenue: ${activeStore.monthly_revenue.toLocaleString()}</p>
              <p>Products: {activeStore.active_products}/{activeStore.product_count}</p>
              <p>Conversion: {activeStore.conversion_rate.toFixed(2)}%</p>
            </div>
          ) : (
            <div className="space-y-2 text-gray-300">
              <p>Total Stores: {stores.length}</p>
              <p>Total Revenue: ${stores.reduce((sum, s) => sum + s.monthly_revenue, 0).toLocaleString()}</p>
              <p>Total Products: {stores.reduce((sum, s) => sum + s.product_count, 0)}</p>
            </div>
          )}
        </div>

        {/* Empty State - No Stores */}
        {stores.length === 0 && (
          <div className="mt-8 bg-gray-800 rounded-lg border border-gray-700 p-12 text-center">
            <div className="text-6xl mb-4">🏪</div>
            <h3 className="text-xl font-bold text-white mb-2">No Stores Yet</h3>
            <p className="text-gray-400 mb-6">
              Get started by adding your first store to the portfolio
            </p>
            <button
              onClick={handleAddStoreClick}
              className="px-6 py-3 bg-gradient-to-r from-blue-500 to-purple-600 text-white rounded-lg font-medium hover:from-blue-600 hover:to-purple-700 transition-all"
            >
              Add Your First Store
            </button>
          </div>
        )}
      </div>

      {/* Add Store Modal */}
      {showAddModal && (
        <AddStoreModal
          onClose={handleModalClose}
          onSuccess={handleStoreAdded}
        />
      )}
    </div>
  );
}

/**
 * ALTERNATIVE PATTERNS
 */

// Pattern 1: With React Router
export function PortfolioWithRouter() {
  const navigate = useNavigate();

  return (
    <AddStoreModal
      onClose={() => navigate('/portfolio')}
      onSuccess={(store) => {
        // Redirect to new store page
        navigate(`/store/${store.id}`);
      }}
    />
  );
}

// Pattern 2: With URL State
export function PortfolioWithURLState() {
  const [searchParams, setSearchParams] = useSearchParams();
  const showModal = searchParams.get('action') === 'add-store';

  return (
    <>
      <button onClick={() => setSearchParams({ action: 'add-store' })}>
        Add Store
      </button>

      {showModal && (
        <AddStoreModal
          onClose={() => setSearchParams({})}
          onSuccess={(store) => {
            setSearchParams({ store: store.id });
          }}
        />
      )}
    </>
  );
}

// Pattern 3: With Context
const StoreContext = createContext(null);

export function StoreProvider({ children }) {
  const [stores, setStores] = useState([]);
  const [showAddModal, setShowAddModal] = useState(false);

  const addStore = (store) => {
    setStores((prev) => [...prev, store]);
  };

  return (
    <StoreContext.Provider value={{ stores, addStore, setShowAddModal }}>
      {children}
      {showAddModal && (
        <AddStoreModal
          onClose={() => setShowAddModal(false)}
          onSuccess={addStore}
        />
      )}
    </StoreContext.Provider>
  );
}

// Pattern 4: With Toast Notifications
export function PortfolioWithToasts() {
  return (
    <AddStoreModal
      onClose={() => console.log('Closed')}
      onSuccess={(store) => {
        // Using react-hot-toast
        toast.success(
          `${store.store_name} added successfully!`,
          {
            icon: '🎉',
            duration: 4000,
          }
        );

        // Or using react-toastify
        toast.success(`${store.store_name} added successfully!`, {
          position: 'top-right',
          autoClose: 3000,
        });
      }}
    />
  );
}

// Pattern 5: With Error Handling
export function PortfolioWithErrorHandling() {
  const [error, setError] = useState<string | null>(null);

  const handleStoreAdded = async (store) => {
    try {
      setError(null);

      // Additional validation or processing
      if (!store.id) {
        throw new Error('Invalid store data received');
      }

      // Update UI
      console.log('Store added:', store);

      // Analytics tracking
      analytics.track('Store Added', {
        platform: store.platform,
        niche: store.niche,
      });

    } catch (err) {
      setError(err.message);
      console.error('Failed to add store:', err);
    }
  };

  return (
    <>
      {error && (
        <div className="p-4 bg-red-500/10 border border-red-500 rounded-lg text-red-400">
          {error}
        </div>
      )}

      <AddStoreModal
        onClose={() => setError(null)}
        onSuccess={handleStoreAdded}
      />
    </>
  );
}

// Pattern 6: With Loading Overlay
export function PortfolioWithLoading() {
  const [isProcessing, setIsProcessing] = useState(false);

  const handleStoreAdded = async (store) => {
    setIsProcessing(true);

    try {
      // Additional async operations
      await fetchStoreDetails(store.id);
      await syncProducts(store.id);

      console.log('Store fully configured:', store);
    } catch (error) {
      console.error('Post-add processing failed:', error);
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <>
      <AddStoreModal
        onClose={() => {}}
        onSuccess={handleStoreAdded}
      />

      {isProcessing && (
        <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center">
          <div className="bg-gray-900 rounded-lg p-8 text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto mb-4"></div>
            <p className="text-white">Configuring your store...</p>
          </div>
        </div>
      )}
    </>
  );
}

/**
 * USAGE NOTES:
 *
 * 1. State Management:
 *    - Keep modal visibility in parent state
 *    - Update stores array on successful add
 *    - Consider optimistic updates vs refetching
 *
 * 2. Error Handling:
 *    - Modal handles API errors internally
 *    - Parent can add additional error handling
 *    - Consider toast/notification for UX
 *
 * 3. Navigation:
 *    - onSuccess can trigger navigation
 *    - Use router or state to redirect user
 *    - Consider staying on current page vs navigating
 *
 * 4. Analytics:
 *    - Track when modal opens
 *    - Track successful store additions
 *    - Track errors and failures
 *
 * 5. Performance:
 *    - Modal is conditionally rendered
 *    - Only mounted when showAddModal is true
 *    - Unmounts when closed to free resources
 */
