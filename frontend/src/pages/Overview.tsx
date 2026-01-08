// 
// OVERVIEW - Multi-Platform E-commerce Store Connection
// Removed redundant "Ask Oi" button (use floating Oi button)
// 

import { useState, useEffect } from 'react';
import { 
  Zap, Plus, Store, Loader2, ExternalLink, RefreshCw,
  Package, ShoppingCart, DollarSign, Users, TrendingUp,
  AlertCircle, CheckCircle2, X, Unplug, Link2, HelpCircle,
  ChevronLeft, Globe
} from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { useDashboardContext } from '../contexts/OiContext';

// ============================================================================
// TYPES & API
// ============================================================================

type Platform = 'shopify' | 'woocommerce';

interface ConnectedStore {
  id: string;
  platform: Platform;
  store_name: string;
  store_url: string;
  domain?: string;
  currency?: string;
  status: string;
  connected_at?: string;
}

interface StoreStats {
  products_count: number;
  orders_count: number;
  customers_count: number;
  revenue_7d: number;
  revenue_30d: number;
  orders_7d: number;
  orders_30d: number;
  avg_order_value: number;
}

interface PlatformConfig {
  id: Platform;
  name: string;
  icon: string;
  color: string;
  description: string;
  comingSoon?: boolean;
}

const PLATFORMS: PlatformConfig[] = [
  {
    id: 'shopify',
    name: 'Shopify',
    icon: 'shopify',
    color: 'bg-[#95BF47]',
    description: 'Connect your Shopify store via OAuth'
  },
  {
    id: 'woocommerce',
    name: 'WooCommerce',
    icon: 'woocommerce',
    color: 'bg-[#7f54b3]',
    description: 'Connect any WordPress + WooCommerce store'
  }
];

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000';

function getToken(): string | null {
  return localStorage.getItem('ospra_token') || sessionStorage.getItem('ospra_token');
}

async function api<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const res = await fetch(`${API}${endpoint}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });
  const data = await res.json();
  if (!res.ok) {
    const errorMsg = data.detail || data.error || data.message || 'Request failed';
    throw new Error(typeof errorMsg === 'string' ? errorMsg : JSON.stringify(errorMsg));
  }
  return data;
}

// ============================================================================
// PLATFORM LOGOS
// ============================================================================

function PlatformIcon({ platform, size = 'md' }: { platform: Platform; size?: 'sm' | 'md' | 'lg' }) {
  const sizeClasses = {
    sm: 'w-6 h-6',
    md: 'w-10 h-10',
    lg: 'w-14 h-14'
  };

  const imgSizes = {
    sm: 'w-4 h-4',
    md: 'w-6 h-6',
    lg: 'w-8 h-8'
  };
  
  const bgClasses = {
    shopify: 'bg-[#95BF47]',
    woocommerce: 'bg-[#96588a]'
  };

  const logoUrls = {
    shopify: 'https://cdn.simpleicons.org/shopify/white',
    woocommerce: 'https://cdn.simpleicons.org/woocommerce/white'
  };
  
  return (
    <div className={`${sizeClasses[size]} ${bgClasses[platform]} rounded-xl flex items-center justify-center shadow-lg`}>
      <img 
        src={logoUrls[platform]} 
        alt={platform} 
        className={`${imgSizes[size]} object-contain`}
      />
    </div>
  );
}

// ============================================================================
// COMPONENT
// ============================================================================

export default function Overview() {
  const { user } = useAuth();
  
  // Oi Context - register data so Oi can see it
  const { 
    registerPage, 
    selectStore, 
    registerMetrics,
    trackAction 
  } = useDashboardContext();
  
  const [stores, setStores] = useState<ConnectedStore[]>([]);
  const [selectedStore, setSelectedStore] = useState<ConnectedStore | null>(null);
  const [stats, setStats] = useState<StoreStats | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isConnecting, setIsConnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  
  // Modal state
  const [showModal, setShowModal] = useState(false);
  const [modalStep, setModalStep] = useState<'select-platform' | 'connect'>('select-platform');
  const [selectedPlatform, setSelectedPlatform] = useState<Platform | null>(null);
  const [storeDomain, setStoreDomain] = useState('');
  const [showHelp, setShowHelp] = useState(false);

  // Register page with Oi on mount
  useEffect(() => {
    registerPage('overview', 'store-connection');
  }, [registerPage]);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get('store_connected') === 'true') {
      setSuccess('Store connected successfully!');
      window.history.replaceState({}, '', window.location.pathname);
    }
    if (params.get('error')) {
      setError(decodeURIComponent(params.get('error') || 'Connection failed'));
      window.history.replaceState({}, '', window.location.pathname);
    }
    loadAllStores();
  }, []);

  // Register selected store with Oi
  useEffect(() => {
    if (selectedStore) {
      selectStore({
        id: selectedStore.id,
        platform: selectedStore.platform,
        store_name: selectedStore.store_name,
        store_url: selectedStore.store_url,
        currency: selectedStore.currency,
      });
      loadStats(selectedStore);
    } else {
      selectStore(null);
      setStats(null);
    }
  }, [selectedStore, selectStore]);

  // Register metrics with Oi when stats change
  useEffect(() => {
    if (stats) {
      registerMetrics({
        revenue_7d: stats.revenue_7d,
        revenue_30d: stats.revenue_30d,
        orders_7d: stats.orders_7d,
        orders_30d: stats.orders_30d,
        products_count: stats.products_count,
        customers_count: stats.customers_count,
        avg_order_value: stats.avg_order_value,
      });
    } else {
      registerMetrics(null);
    }
  }, [stats, registerMetrics]);

  const loadAllStores = async () => {
    setIsLoading(true);
    const allStores: ConnectedStore[] = [];
    
    try {
      // Load Shopify stores
      try {
        const shopifyRes = await api<{ stores: any[] }>('/api/shopify/stores');
        if (shopifyRes.stores) {
          allStores.push(...shopifyRes.stores.map(s => ({ ...s, platform: 'shopify' as Platform })));
        }
      } catch (err) {
        console.log('No Shopify stores or endpoint unavailable');
      }
      
      // Load WooCommerce stores
      try {
        const wooRes = await api<{ stores: any[] }>('/api/woocommerce/stores');
        if (wooRes.stores) {
          allStores.push(...wooRes.stores.map(s => ({ ...s, platform: 'woocommerce' as Platform })));
        }
      } catch (err) {
        console.log('No WooCommerce stores or endpoint unavailable');
      }
      
      setStores(allStores);
      if (allStores.length > 0) {
        setSelectedStore(allStores[0]);
      } else {
        setSelectedStore(null);
      }
      
      // Track the load action
      trackAction('stores_loaded', { count: allStores.length });
      
    } catch (err: any) {
      console.error('Load stores error:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const loadStats = async (store: ConnectedStore) => {
    try {
      const endpoint = store.platform === 'shopify' 
        ? `/api/shopify/stores/${store.id}/stats`
        : `/api/woocommerce/stores/${store.id}/stats`;
      const res = await api<{ stats: StoreStats }>(endpoint);
      setStats(res.stats);
    } catch (err) {
      console.error('Load stats error:', err);
      setStats(null);
    }
  };

  const handleConnect = async () => {
    if (!storeDomain.trim() || !selectedPlatform) {
      setError('Enter your store domain');
      return;
    }
    
    setIsConnecting(true);
    setError(null);
    
    // Track the connect attempt
    trackAction('store_connect_attempt', { platform: selectedPlatform });
    
    try {
      if (selectedPlatform === 'shopify') {
        const res = await api<{ 
          success: boolean; 
          message?: string; 
          oauth_required?: boolean;
          authorization_url?: string;
        }>('/api/shopify/connect', {
          method: 'POST',
          body: JSON.stringify({ shop_domain: storeDomain.trim() }),
        });
        
        if (res.oauth_required && res.authorization_url) {
          window.open(res.authorization_url, '_blank');
          closeModal();
          setSuccess('Complete authorization in the new tab, then refresh this page.');
          return;
        }
        
        setSuccess(res.message || 'Store connected!');
      } else if (selectedPlatform === 'woocommerce') {
        const res = await api<{ 
          success: boolean; 
          message?: string;
          authorization_url?: string;
        }>('/api/woocommerce/connect', {
          method: 'POST',
          body: JSON.stringify({ store_url: storeDomain.trim() }),
        });
        
        if (res.authorization_url) {
          window.open(res.authorization_url, '_blank');
          closeModal();
          setSuccess('Complete authorization in the new tab.');
          return;
        }
        
        setSuccess(res.message || 'Store connected!');
      }
      
      closeModal();
      await loadAllStores();
    } catch (err: any) {
      setError(err?.message || String(err));
    } finally {
      setIsConnecting(false);
    }
  };

  const handleDisconnect = async (store: ConnectedStore) => {
    if (!confirm(`Disconnect ${store.store_name}?`)) return;
    
    // Track disconnect
    trackAction('store_disconnect', { platform: store.platform, store_name: store.store_name });
    
    try {
      const endpoint = store.platform === 'shopify'
        ? `/api/shopify/stores/${store.id}`
        : `/api/woocommerce/stores/${store.id}`;
      await api(endpoint, { method: 'DELETE' });
      setSuccess('Store disconnected');
      const remaining = stores.filter(s => !(s.id === store.id && s.platform === store.platform));
      setStores(remaining);
      setSelectedStore(remaining[0] || null);
      setStats(null);
    } catch (err: any) {
      setError(err?.message || String(err));
    }
  };

  const closeModal = () => {
    setShowModal(false);
    setModalStep('select-platform');
    setSelectedPlatform(null);
    setStoreDomain('');
    setShowHelp(false);
  };

  const selectPlatform = (platform: Platform) => {
    setSelectedPlatform(platform);
    setModalStep('connect');
  };

  const getGreeting = () => {
    const h = new Date().getHours();
    if (h < 12) return 'Good morning';
    if (h < 18) return 'Good afternoon';
    return 'Good evening';
  };

  const firstName = user?.name?.split(' ')[0] || 'there';

  const getStoreUrl = (store: ConnectedStore) => {
    if (store.platform === 'shopify') {
      return `https://${store.store_url}`;
    }
    return store.store_url.startsWith('http') ? store.store_url : `https://${store.store_url}`;
  };

  return (
    <div className="space-y-6 animate-fade-in">
      
      {/* Alerts */}
      {error && (
        <div className="flex items-center gap-3 p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          <span className="text-sm flex-1">{error}</span>
          <button onClick={() => setError(null)}><X className="w-4 h-4" /></button>
        </div>
      )}
      
      {success && (
        <div className="flex items-center gap-3 p-4 rounded-xl bg-green-500/10 border border-green-500/20 text-green-400">
          <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
          <span className="text-sm flex-1">{success}</span>
          <button onClick={() => setSuccess(null)}><X className="w-4 h-4" /></button>
        </div>
      )}

      {/* Header */}
      <div className="glass-card-static p-6">
        <div className="flex items-start gap-4">
          <div className="relative">
            <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-blue-500 via-purple-500 to-cyan-500 flex items-center justify-center shadow-lg shadow-blue-500/20">
              <Zap className="w-6 h-6 text-white" />
            </div>
            <div className="absolute -bottom-1 -right-1 w-4 h-4 rounded-full bg-green-500 border-2 border-[#0a0a0f]" />
          </div>
          
          <div className="flex-1">
            <h1 className="text-xl font-semibold text-white mb-1">
              {getGreeting()}, {firstName}
            </h1>
            <p className="text-white/60 text-sm">
              {stores.length === 0 
                ? "Connect your e-commerce store to get started."
                : `${stores.length} store${stores.length > 1 ? 's' : ''} connected.`
              }
            </p>
          </div>
          
          <button 
            onClick={loadAllStores}
            className="p-2 rounded-xl text-white/40 hover:text-white/80 hover:bg-white/[0.04]"
            title="Refresh stores"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Content */}
      {isLoading ? (
        <div className="glass-card-static p-12 text-center">
          <Loader2 className="w-8 h-8 text-white/40 animate-spin mx-auto mb-4" />
          <p className="text-white/60 text-sm">Loading...</p>
        </div>
      ) : stores.length === 0 ? (
        <div className="glass-card-static p-12 text-center">
          <div className="w-16 h-16 rounded-2xl bg-white/[0.04] border border-dashed border-white/10 flex items-center justify-center mx-auto mb-4">
            <Store className="w-8 h-8 text-white/30" />
          </div>
          <h2 className="text-lg font-medium text-white mb-2">No stores connected</h2>
          <p className="text-white/50 text-sm max-w-md mx-auto mb-6">
            Connect your Shopify or WooCommerce store to see real-time data and insights.
          </p>
          <button 
            onClick={() => setShowModal(true)}
            className="px-6 py-3 rounded-xl bg-blue-500 text-white text-sm font-medium hover:bg-blue-600 inline-flex items-center gap-2"
          >
            <Plus className="w-4 h-4" />
            Add E-commerce Store
          </button>
        </div>
      ) : (
        <>
          {/* Store selector */}
          <div className="flex gap-2 overflow-x-auto pb-2">
            {stores.map((store) => (
              <button
                key={`${store.platform}-${store.id}`}
                onClick={() => setSelectedStore(store)}
                className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm whitespace-nowrap transition-all
                  ${selectedStore?.id === store.id && selectedStore?.platform === store.platform
                    ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30' 
                    : 'bg-white/[0.04] text-white/60 border border-white/[0.06] hover:bg-white/[0.06]'
                  }`}
              >
                <PlatformIcon platform={store.platform} size="sm" />
                {store.store_name}
              </button>
            ))}
            <button
              onClick={() => setShowModal(true)}
              className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm whitespace-nowrap bg-white/[0.02] text-white/40 border border-dashed border-white/10 hover:border-white/20 hover:text-white/60"
            >
              <Plus className="w-4 h-4" />
              Add Store
            </button>
          </div>

          {/* Stats */}
          {stats && (
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              <StatCard label="Revenue (7d)" value={`$${stats.revenue_7d.toLocaleString()}`} icon={DollarSign} />
              <StatCard label="Orders (7d)" value={stats.orders_7d.toString()} icon={ShoppingCart} />
              <StatCard label="Products" value={stats.products_count.toString()} icon={Package} />
              <StatCard label="Customers" value={stats.customers_count.toString()} icon={Users} />
            </div>
          )}

          {/* Store info */}
          {selectedStore && (
            <div className="glass-card-static p-5">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-sm font-medium text-white flex items-center gap-2">
                  <PlatformIcon platform={selectedStore.platform} size="sm" />
                  {selectedStore.store_name}
                  <span className="text-xs px-2 py-0.5 rounded-full bg-white/[0.06] text-white/40 capitalize">
                    {selectedStore.platform}
                  </span>
                </h2>
                <div className="flex items-center gap-2">
                  <a 
                    href={getStoreUrl(selectedStore)}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs px-3 py-1.5 rounded-lg bg-white/[0.04] text-white/60 hover:text-white hover:bg-white/[0.08] flex items-center gap-1.5"
                  >
                    <ExternalLink className="w-3 h-3" />
                    Visit Store
                  </a>
                  <button
                    onClick={() => handleDisconnect(selectedStore)}
                    className="text-xs px-3 py-1.5 rounded-lg bg-red-500/10 text-red-400 hover:bg-red-500/20 flex items-center gap-1.5"
                  >
                    <Unplug className="w-3 h-3" />
                    Disconnect
                  </button>
                </div>
              </div>
              
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
                <div>
                  <div className="text-white/40 text-xs mb-1">Domain</div>
                  <div className="text-white/80">{selectedStore.domain || selectedStore.store_url}</div>
                </div>
                <div>
                  <div className="text-white/40 text-xs mb-1">Platform</div>
                  <div className="text-white/80 capitalize">{selectedStore.platform}</div>
                </div>
                <div>
                  <div className="text-white/40 text-xs mb-1">Status</div>
                  <div className="flex items-center gap-1 text-green-400">
                    <span className="w-2 h-2 rounded-full bg-green-400" />
                    {selectedStore.status}
                  </div>
                </div>
                <div>
                  <div className="text-white/40 text-xs mb-1">Connected</div>
                  <div className="text-white/80">
                    {selectedStore.connected_at 
                      ? new Date(selectedStore.connected_at).toLocaleDateString()
                      : 'Just now'
                    }
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* 30-day stats */}
          {stats && (
            <div className="glass-card-static p-5">
              <div className="flex items-center gap-2 mb-4">
                <TrendingUp className="w-4 h-4 text-white/60" />
                <h2 className="text-sm font-medium text-white">30-Day Performance</h2>
              </div>
              <div className="grid grid-cols-3 gap-6">
                <div>
                  <div className="text-2xl font-semibold text-white">${stats.revenue_30d.toLocaleString()}</div>
                  <div className="text-xs text-white/40 mt-1">Revenue</div>
                </div>
                <div>
                  <div className="text-2xl font-semibold text-white">{stats.orders_30d}</div>
                  <div className="text-xs text-white/40 mt-1">Orders</div>
                </div>
                <div>
                  <div className="text-2xl font-semibold text-white">${stats.avg_order_value.toFixed(2)}</div>
                  <div className="text-xs text-white/40 mt-1">Avg Order</div>
                </div>
              </div>
            </div>
          )}
        </>
      )}

      {/* Connect Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
          <div className="glass-card-static p-6 w-full max-w-lg">
            
            {/* Modal Header */}
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                {modalStep === 'connect' && (
                  <button 
                    onClick={() => { setModalStep('select-platform'); setSelectedPlatform(null); setStoreDomain(''); setShowHelp(false); }}
                    className="p-1 rounded-lg text-white/40 hover:text-white/80 hover:bg-white/[0.04]"
                  >
                    <ChevronLeft className="w-5 h-5" />
                  </button>
                )}
                <h3 className="text-lg font-medium text-white">
                  {modalStep === 'select-platform' ? 'Add E-commerce Store' : `Connect ${selectedPlatform === 'shopify' ? 'Shopify' : 'WooCommerce'}`}
                </h3>
              </div>
              <button onClick={closeModal} className="text-white/40 hover:text-white/80">
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Step 1: Select Platform */}
            {modalStep === 'select-platform' && (
              <>
                <p className="text-white/60 text-sm mb-6">
                  Choose your e-commerce platform to connect.
                </p>
                
                <div className="space-y-3">
                  {PLATFORMS.map((platform) => (
                    <button
                      key={platform.id}
                      onClick={() => !platform.comingSoon && selectPlatform(platform.id)}
                      disabled={platform.comingSoon}
                      className={`w-full p-4 rounded-xl border transition-all text-left flex items-center gap-4
                        ${platform.comingSoon 
                          ? 'bg-white/[0.02] border-white/[0.04] opacity-50 cursor-not-allowed'
                          : 'bg-white/[0.04] border-white/[0.08] hover:bg-white/[0.08] hover:border-white/[0.15]'
                        }`}
                    >
                      <div className={`w-12 h-12 rounded-xl ${platform.color} flex items-center justify-center shadow-lg`}>
                        <img 
                          src={platform.id === 'shopify' 
                            ? 'https://cdn.simpleicons.org/shopify/white'
                            : 'https://cdn.simpleicons.org/woocommerce/white'
                          } 
                          alt={platform.name}
                          className="w-6 h-6 object-contain"
                        />
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <span className="text-white font-medium">{platform.name}</span>
                          {platform.comingSoon && (
                            <span className="text-xs px-2 py-0.5 rounded-full bg-white/[0.06] text-white/40">Coming Soon</span>
                          )}
                        </div>
                        <p className="text-white/50 text-sm mt-0.5">{platform.description}</p>
                      </div>
                      {!platform.comingSoon && (
                        <ChevronLeft className="w-5 h-5 text-white/30 rotate-180" />
                      )}
                    </button>
                  ))}
                </div>

                <div className="mt-6 p-4 rounded-xl bg-blue-500/10 border border-blue-500/20">
                  <div className="flex items-start gap-3">
                    <Globe className="w-5 h-5 text-blue-400 flex-shrink-0 mt-0.5" />
                    <div>
                      <p className="text-blue-400 text-sm font-medium">More platforms coming soon</p>
                      <p className="text-white/50 text-xs mt-1">
                        Amazon, BigCommerce, Etsy, eBay, TikTok Shop and more are on the roadmap.
                      </p>
                    </div>
                  </div>
                </div>
              </>
            )}

            {/* Step 2: Connect Store */}
            {modalStep === 'connect' && selectedPlatform && (
              <>
                {selectedPlatform === 'shopify' ? (
                  <>
                    <p className="text-white/60 text-sm mb-4">
                      Enter your Shopify store domain. You'll be redirected to Shopify to authorize Ospra.
                    </p>
                    
                    <div className="mb-4">
                      <label className="block text-sm font-medium text-white/70 mb-2">Store Domain</label>
                      <div className="flex">
                        <input 
                          type="text"
                          value={storeDomain}
                          onChange={(e) => setStoreDomain(e.target.value)}
                          onKeyDown={(e) => e.key === 'Enter' && handleConnect()}
                          placeholder="your-store-name"
                          className="flex-1 px-4 py-3 bg-white/[0.04] border border-white/[0.08] rounded-l-xl text-white placeholder-white/30 focus:outline-none focus:border-green-500/50"
                          autoFocus
                        />
                        <span className="px-4 py-3 bg-white/[0.02] border border-l-0 border-white/[0.08] rounded-r-xl text-white/40 text-sm flex items-center">
                          .myshopify.com
                        </span>
                      </div>
                    </div>

                    <button
                      onClick={() => setShowHelp(!showHelp)}
                      className="text-green-400 text-sm hover:text-green-300 mb-4 flex items-center gap-1"
                    >
                      <HelpCircle className="w-4 h-4" />
                      {showHelp ? 'Hide help' : 'How do I find my store domain?'}
                    </button>

                    {showHelp && (
                      <div className="mb-4 p-4 rounded-xl bg-green-500/10 border border-green-500/20 text-sm space-y-3">
                        <p className="text-white/80 font-medium">Finding your Shopify store domain:</p>
                        <div className="space-y-2 text-white/60">
                          <div className="flex gap-2">
                            <span className="text-green-400 font-medium">1.</span>
                            <span>Log in to your Shopify admin panel</span>
                          </div>
                          <div className="flex gap-2">
                            <span className="text-green-400 font-medium">2.</span>
                            <span>Look at your browser URL - it will look like:</span>
                          </div>
                          <div className="ml-5 px-3 py-2 bg-black/30 rounded-lg font-mono text-xs text-white/80">
                            https://admin.shopify.com/store/<span className="text-green-400">your-store-name</span>
                          </div>
                          <div className="flex gap-2">
                            <span className="text-green-400 font-medium">3.</span>
                            <span>Copy just the <span className="text-green-400">highlighted part</span> after /store/</span>
                          </div>
                        </div>
                      </div>
                    )}
                  </>
                ) : (
                  <>
                    <p className="text-white/60 text-sm mb-4">
                      Enter your WooCommerce store URL. You'll be redirected to your WordPress site to authorize Ospra.
                    </p>
                    
                    <div className="mb-4">
                      <label className="block text-sm font-medium text-white/70 mb-2">Store URL</label>
                      <input 
                        type="text"
                        value={storeDomain}
                        onChange={(e) => setStoreDomain(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && handleConnect()}
                        placeholder="mystore.com"
                        className="w-full px-4 py-3 bg-white/[0.04] border border-white/[0.08] rounded-xl text-white placeholder-white/30 focus:outline-none focus:border-purple-500/50"
                        autoFocus
                      />
                      <p className="text-white/40 text-xs mt-2">
                        Enter just the domain (e.g., mystore.com) or full URL
                      </p>
                    </div>

                    <button
                      onClick={() => setShowHelp(!showHelp)}
                      className="text-purple-400 text-sm hover:text-purple-300 mb-4 flex items-center gap-1"
                    >
                      <HelpCircle className="w-4 h-4" />
                      {showHelp ? 'Hide help' : 'How does WooCommerce connection work?'}
                    </button>

                    {showHelp && (
                      <div className="mb-4 p-4 rounded-xl bg-purple-500/10 border border-purple-500/20 text-sm space-y-3">
                        <p className="text-white/80 font-medium">WooCommerce OAuth:</p>
                        <div className="space-y-2 text-white/60">
                          <div className="flex gap-2">
                            <span className="text-purple-400 font-medium">1.</span>
                            <span>Enter your store URL (e.g., mystore.com)</span>
                          </div>
                          <div className="flex gap-2">
                            <span className="text-purple-400 font-medium">2.</span>
                            <span>You'll be redirected to your WordPress admin</span>
                          </div>
                          <div className="flex gap-2">
                            <span className="text-purple-400 font-medium">3.</span>
                            <span>Log in and click "Approve" to grant Ospra access</span>
                          </div>
                          <div className="flex gap-2">
                            <span className="text-purple-400 font-medium">4.</span>
                            <span>You'll be redirected back here automatically</span>
                          </div>
                        </div>
                      </div>
                    )}
                  </>
                )}
                
                <div className="flex gap-3">
                  <button
                    onClick={closeModal}
                    className="flex-1 px-4 py-3 rounded-xl bg-white/[0.06] text-white text-sm font-medium hover:bg-white/[0.1]"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleConnect}
                    disabled={isConnecting || !storeDomain.trim()}
                    className={`flex-1 px-4 py-3 rounded-xl text-white text-sm font-medium flex items-center justify-center gap-2 disabled:opacity-50
                      ${selectedPlatform === 'shopify' 
                        ? 'bg-green-500 hover:bg-green-600' 
                        : 'bg-purple-500 hover:bg-purple-600'
                      }`}
                  >
                    {isConnecting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Link2 className="w-4 h-4" />}
                    {isConnecting ? 'Connecting...' : 'Connect'}
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function StatCard({ label, value, icon: Icon }: { label: string; value: string; icon: any }) {
  return (
    <div className="glass-card-static p-4">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs text-white/50">{label}</span>
        <Icon className="w-4 h-4 text-white/30" />
      </div>
      <div className="text-2xl font-semibold text-white">{value}</div>
    </div>
  );
}
